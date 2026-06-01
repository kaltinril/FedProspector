<#
.SYNOPSIS
    Provision the FedProspector API for public HTTPS exposure on the PROD server:
    create a self-signed cert (.pfx) and write the EXTERNAL machine-specific config
    file the API reads at startup. Idempotent and re-runnable.

.DESCRIPTION
    This is "the SSL creation script": run it ON THE PROD SERVER once after the first
    deploy, and re-run it whenever the public hostname/IP, port, or cert needs to
    change. It does everything in one shot:

      1. Ensures the cert directory and the external config folder exist.
      2. Creates (or reuses) a self-signed RSA-2048, 5-year cert and exports it to a
         password-protected .pfx OUTSIDE the repo.
      3. Builds/merges the EXTERNAL config file the API reads (default
         C:\fedprospector\config\fedprospector.local.json) with ConnectionStrings,
         Cors, AllowedHosts, and the Kestrel HTTPS endpoint + cert — WITHOUT
         destroying any existing values.

    Nothing this script produces is committed or copied by deploy.ps1: the .pfx and
    the external config live OUTSIDE the repo tree, so a deploy can never overwrite
    them. The API discovers the config file via its default path or the
    FEDPROSPECTOR_CONFIG environment variable (Program.cs).

    JWT is NOT handled here. The API reads Jwt:SecretKey from the Jwt__SecretKey
    environment variable (set by fed_prospector.py from .env). This script never
    writes a Jwt section.

.PARAMETER DnsName
    One or more hostnames/IPs clients will reach the box by. Each becomes a Subject
    Alternative Name on the cert (IPs as IPAddress entries, names as DNS entries) AND
    an entry in the API's AllowedHosts. Defaults to this deployment's external IP,
    internal LAN IP, and loopback. Re-run with new values after a public-IP change.

.PARAMETER Port
    HTTPS port to bind on 0.0.0.0. Default 5056.

.PARAMETER CertDir
    Directory (outside the repo) where fedprospector.pfx lives. Default C:\fedprospector\certs.

.PARAMETER ConfigPath
    Full path to the external config file the API reads. Default
    C:\fedprospector\config\fedprospector.local.json. The API can be pointed at a
    different path via the FEDPROSPECTOR_CONFIG environment variable.

.PARAMETER PfxPassword
    SecureString password protecting the .pfx. Optional. If omitted on first
    generation, a strong random password is generated and written into the config.
    On a re-run that reuses an existing cert, the password is recovered from the
    existing config file, so you normally don't need to supply it.

.PARAMETER Force
    Regenerate the cert even if one already exists at $CertDir\fedprospector.pfx.

.PARAMETER OpenFirewall
    Also add a Windows Firewall inbound rule for the HTTPS port (requires admin).

.EXAMPLE
    # Use the baked-in defaults (external IP + LAN IP + loopback):
    .\scripts\generate-selfsigned-cert.ps1

.EXAMPLE
    # Override after the public IP changes:
    .\scripts\generate-selfsigned-cert.ps1 -DnsName 198.51.100.7,192.168.0.173,localhost,127.0.0.1 -Force
#>
[CmdletBinding()]
param(
    # Names/IPs the cert is valid for AND the API's AllowedHosts. IPs become proper
    # IPAddress SAN entries; hostnames become DNS SAN entries. Defaults cover this
    # deployment's external + internal + loopback addresses — re-run with new values
    # (e.g. after a public-IP change) and it regenerates the cert + config.
    [string[]]$DnsName = @("206.162.3.86", "192.168.0.173", "localhost", "127.0.0.1"),

    [int]$Port = 5056,

    [string]$CertDir = "C:\fedprospector\certs",

    [string]$ConfigPath = "C:\fedprospector\config\fedprospector.local.json",

    [securestring]$PfxPassword,

    [switch]$Force,

    [switch]$OpenFirewall
)

$ErrorActionPreference = "Stop"

# --- Helper: set a property on a PSCustomObject, creating it if missing (PS 5.1 safe) ---
function Set-JsonProperty {
    param(
        [Parameter(Mandatory = $true)] $Object,
        [Parameter(Mandatory = $true)] [string]$Name,
        [Parameter(Mandatory = $true)] $Value
    )
    if ($null -eq $Object.PSObject.Properties[$Name]) {
        $Object | Add-Member -NotePropertyName $Name -NotePropertyValue $Value -Force
    } else {
        $Object.$Name = $Value
    }
}

# --- 1. Ensure directories exist ---
$pfxPath = Join-Path $CertDir "fedprospector.pfx"
$configDir = Split-Path -Parent $ConfigPath
foreach ($dir in @($CertDir, $configDir)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Created directory: $dir" -ForegroundColor Green
    }
}

# --- 2. Cert: generate or reuse ---
$plainPwd = $null

if ((Test-Path $pfxPath) -and -not $Force) {
    Write-Host "Reusing existing certificate: $pfxPath" -ForegroundColor Cyan
    # Recover the password from the existing config so re-runs need neither -Force
    # nor a password.
    if ($PfxPassword) {
        $plainPwd = [System.Net.NetworkCredential]::new("", $PfxPassword).Password
    } elseif (Test-Path $ConfigPath) {
        try {
            $existingCfg = Get-Content $ConfigPath -Raw | ConvertFrom-Json
            $plainPwd = $existingCfg.Kestrel.Endpoints.Https.Certificate.Password
        } catch {
            $plainPwd = $null
        }
    }
    if ([string]::IsNullOrEmpty($plainPwd)) {
        throw "An existing .pfx was found at '$pfxPath' but its password could not be " +
              "recovered from '$ConfigPath' and none was supplied. Re-run with -Force to " +
              "regenerate the cert (a new random password will be created), or pass -PfxPassword."
    }
} else {
    if ($Force -and (Test-Path $pfxPath)) {
        Write-Host "Regenerating certificate (-Force): $pfxPath" -ForegroundColor Yellow
    } else {
        Write-Host "Creating self-signed certificate for: $($DnsName -join ', ')" -ForegroundColor Green
    }

    if ($PfxPassword) {
        $plainPwd = [System.Net.NetworkCredential]::new("", $PfxPassword).Password
    } else {
        # Generate a strong random alphanumeric password (no special chars to avoid
        # JSON/escaping surprises).
        $chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789".ToCharArray()
        $plainPwd = -join (1..32 | ForEach-Object { $chars | Get-Random })
        Write-Host "Generated a random .pfx password (stored in the config file)." -ForegroundColor Yellow
    }
    $securePwd = ConvertTo-SecureString -String $plainPwd -AsPlainText -Force

    # Build a Subject Alternative Name extension covering every supplied address:
    # IPs as IPAddress entries, hostnames as DNS entries. This makes the cert valid
    # for the LAN IP, the public IP, and loopback at once.
    $sanParts = foreach ($name in $DnsName) {
        $parsedIp = $null
        if ([System.Net.IPAddress]::TryParse($name, [ref]$parsedIp)) {
            "IPAddress=$name"
        } else {
            "DNS=$name"
        }
    }
    $sanExtension = "2.5.29.17={text}" + ($sanParts -join "&")
    $ekuExtension = "2.5.29.37={text}1.3.6.1.5.5.7.3.1"  # Server Authentication EKU

    $cert = New-SelfSignedCertificate `
        -Subject "CN=FedProspector API" `
        -TextExtension @($sanExtension, $ekuExtension) `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -KeyExportPolicy Exportable `
        -KeyUsage DigitalSignature, KeyEncipherment `
        -KeyAlgorithm RSA `
        -KeyLength 2048 `
        -NotAfter (Get-Date).AddYears(5) `
        -FriendlyName "FedProspector API"

    Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $securePwd | Out-Null
    Write-Host "Exported PFX to: $pfxPath" -ForegroundColor Green

    # Remove the cert from the user store; Kestrel loads it from the .pfx file.
    Remove-Item "Cert:\CurrentUser\My\$($cert.Thumbprint)" -ErrorAction SilentlyContinue
}

# --- 3. Build/merge the external config file (preserve existing values) ---
if (Test-Path $ConfigPath) {
    Write-Host "Merging into existing config: $ConfigPath" -ForegroundColor Cyan
    $config = Get-Content $ConfigPath -Raw | ConvertFrom-Json
} else {
    Write-Host "Creating new external config: $ConfigPath" -ForegroundColor Green
    $config = [PSCustomObject]@{}

    # One-time migration: lift ConnectionStrings + Cors from the in-repo
    # appsettings.Local.json if it still holds the prod values.
    $repoLocal = Join-Path $PSScriptRoot "..\api\src\FedProspector.Api\appsettings.Local.json"
    if (Test-Path $repoLocal) {
        Write-Host "Migrating ConnectionStrings/Cors from $repoLocal" -ForegroundColor Yellow
        $repoCfg = Get-Content $repoLocal -Raw | ConvertFrom-Json
        if ($repoCfg.PSObject.Properties['ConnectionStrings']) {
            Set-JsonProperty -Object $config -Name "ConnectionStrings" -Value $repoCfg.ConnectionStrings
        }
        if ($repoCfg.PSObject.Properties['Cors']) {
            Set-JsonProperty -Object $config -Name "Cors" -Value $repoCfg.Cors
        }
    }

    if ($null -eq $config.PSObject.Properties['ConnectionStrings']) {
        Write-Warning ("No in-repo appsettings.Local.json found to migrate. Writing a " +
                       "PLACEHOLDER ConnectionStrings.DefaultConnection — EDIT '$ConfigPath' " +
                       "and replace YOUR_PASSWORD before starting the API.")
        $cs = [PSCustomObject]@{
            DefaultConnection = "Server=localhost;Port=3306;Database=fed_contracts;User=fed_app;Password=YOUR_PASSWORD;SslMode=None;AllowPublicKeyRetrieval=True;MaxPoolSize=50;MinPoolSize=5"
        }
        Set-JsonProperty -Object $config -Name "ConnectionStrings" -Value $cs
    }
}

# AllowedHosts = every name/IP you reach the box by, semicolon-separated (ASP.NET
# host-filtering syntax). The port is ignored during matching.
Set-JsonProperty -Object $config -Name "AllowedHosts" -Value ($DnsName -join ";")

# Kestrel HTTPS endpoint + cert.
$kestrel = [PSCustomObject]@{
    Endpoints = [PSCustomObject]@{
        Https = [PSCustomObject]@{
            Url         = "https://0.0.0.0:$Port"
            Certificate = [PSCustomObject]@{
                Path     = $pfxPath
                Password = $plainPwd
            }
        }
    }
}
Set-JsonProperty -Object $config -Name "Kestrel" -Value $kestrel

# NOTE: no Jwt key is written — JWT stays in the Jwt__SecretKey environment variable.

# ConvertTo-Json escapes backslashes in the cert path correctly.
$config | ConvertTo-Json -Depth 32 | Set-Content -Path $ConfigPath -Encoding UTF8
Write-Host "Wrote external config: $ConfigPath" -ForegroundColor Green

# --- Optional firewall rule ---
if ($OpenFirewall) {
    $ruleName = "FedProspector API HTTPS $Port"
    if (-not (Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow `
            -Protocol TCP -LocalPort $Port | Out-Null
        Write-Host "Opened firewall for inbound TCP $Port." -ForegroundColor Green
    } else {
        Write-Host "Firewall rule '$ruleName' already exists." -ForegroundColor DarkGray
    }
}

# --- 4. Summary + next steps ---
Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Green
Write-Host "  Cert (.pfx):    $pfxPath"
Write-Host "  External config: $ConfigPath"
Write-Host "  Names/IPs:       $($DnsName -join ', ')"
Write-Host "  HTTPS endpoint:  https://0.0.0.0:$Port"
Write-Host ""
Write-Host "Next steps on this prod server:" -ForegroundColor Cyan
Write-Host "  1. Ensure ASPNETCORE_ENVIRONMENT=Production (persists across reboots):"
Write-Host "       setx ASPNETCORE_ENVIRONMENT Production"
Write-Host "  2. Port-forward your router's public TCP port to this box's TCP $Port."
if (-not $OpenFirewall) {
    Write-Host "  3. Open the Windows firewall for inbound TCP $Port (or re-run with -OpenFirewall as admin):"
    Write-Host "       New-NetFirewallRule -DisplayName 'FedProspector API HTTPS $Port' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port"
}
Write-Host "  4. Restart the C# API so it reloads config."
Write-Host ""
Write-Host "The API reads this config from '$ConfigPath'" -ForegroundColor DarkGray
Write-Host "(override the location with the FEDPROSPECTOR_CONFIG environment variable)." -ForegroundColor DarkGray
