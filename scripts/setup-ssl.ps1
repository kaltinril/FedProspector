<#
.SYNOPSIS
    One-shot, idempotent HTTPS/SSL provisioner for the FedProspector API. Run this
    ON THE PROD BOX after a deploy.

.DESCRIPTION
    Option B serves the whole app (UI + API) from a single Kestrel HTTPS port. This
    script makes that port live by:
      1. Generating a self-signed .pfx (once) and remembering its password.
      2. Merging the Kestrel HTTPS endpoint + cert path/password + AllowedHosts into
         the existing appsettings.Local.json WITHOUT clobbering DB/JWT/other settings.
      3. (Optional) opening the Windows firewall for the port.

    WHY RE-RUN AFTER EACH DEPLOY: deploy.ps1 robocopies the whole repo, so dev's
    appsettings.Local.json overwrites prod's every deploy and wipes the Kestrel
    section. This script re-applies it. The cert (.pfx) and its password live OUTSIDE
    the repo tree (default C:\fedprospector\certs), so a deploy never touches them and
    re-running here just re-injects the same values. Safe to run repeatedly.

    NOTHING here is committed: the .pfx, the .pass file, and appsettings.Local.json are
    all gitignored / outside the repo.

.PARAMETER DnsName
    Public hostname or IP your 3 users will hit. Used as the cert subject/SAN and as
    AllowedHosts. Example: 73.12.34.56 or fedprospect.mydomain.

.PARAMETER Port
    HTTPS port Kestrel binds (on 0.0.0.0, so port-forwarding works). Default 5056.

.PARAMETER CertDir
    Folder (OUTSIDE the repo) to store the .pfx + password file. Default
    C:\fedprospector\certs. Deploy never copies here, so the cert survives deploys.

.PARAMETER AppSettingsPath
    Path to appsettings.Local.json. Defaults to the API project under this repo.

.PARAMETER PfxPassword
    Password for the .pfx. If omitted on first run, a strong random one is generated
    and saved to <CertDir>\fedprospector.pfx.pass for future re-runs.

.PARAMETER Force
    Regenerate the cert even if one already exists (new password too).

.PARAMETER OpenFirewall
    Add/replace an inbound TCP allow rule for the port (requires admin).

.EXAMPLE
    # First time on prod (also open the firewall):
    .\scripts\setup-ssl.ps1 -DnsName 73.12.34.56 -OpenFirewall

.EXAMPLE
    # After every subsequent deploy (re-applies the wiped Kestrel section):
    .\scripts\setup-ssl.ps1 -DnsName 73.12.34.56
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DnsName,

    [int]$Port = 5056,

    [string]$CertDir = "C:\fedprospector\certs",

    [string]$AppSettingsPath = "$PSScriptRoot\..\api\src\FedProspector.Api\appsettings.Local.json",

    [securestring]$PfxPassword,

    [switch]$Force,

    [switch]$OpenFirewall
)

$ErrorActionPreference = "Stop"

$CertDir        = [System.IO.Path]::GetFullPath($CertDir)
$AppSettingsPath = [System.IO.Path]::GetFullPath($AppSettingsPath)
$pfxPath        = Join-Path $CertDir "fedprospector.pfx"
$passPath       = "$pfxPath.pass"

New-Item -ItemType Directory -Path $CertDir -Force | Out-Null

# --- 1. Resolve the cert + its password ---------------------------------------
$needGen = $Force.IsPresent -or (-not (Test-Path $pfxPath))

if ($needGen) {
    if ($PfxPassword) {
        $plainPwd = [System.Net.NetworkCredential]::new("", $PfxPassword).Password
    } else {
        $chars = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
        $plainPwd = -join (1..28 | ForEach-Object { $chars[(Get-Random -Maximum $chars.Length)] })
    }

    Write-Host "Generating self-signed certificate for '$DnsName' -> $pfxPath" -ForegroundColor Green
    $securePwd = ConvertTo-SecureString $plainPwd -AsPlainText -Force
    & "$PSScriptRoot\generate-selfsigned-cert.ps1" -DnsName $DnsName -OutputPath $pfxPath -Password $securePwd | Out-Null

    # Persist the password (outside the repo) so future re-runs don't need -Force.
    Set-Content -Path $passPath -Value $plainPwd -NoNewline -Encoding ASCII
    Write-Host "Saved PFX password to $passPath (keep this box's disk access locked down)." -ForegroundColor DarkGray
}
else {
    Write-Host "Reusing existing certificate at $pfxPath (use -Force to regenerate)." -ForegroundColor DarkGray
    if (Test-Path $passPath) {
        $plainPwd = (Get-Content $passPath -Raw).Trim()
    } elseif ($PfxPassword) {
        $plainPwd = [System.Net.NetworkCredential]::new("", $PfxPassword).Password
    } else {
        throw "Cert exists but no password file at '$passPath' and no -PfxPassword given. Re-run with -Force to regenerate, or pass -PfxPassword."
    }
}

# --- 2. Merge Kestrel HTTPS config into appsettings.Local.json -----------------
# Preserve every other setting (ConnectionStrings, Jwt, Cors, Serilog, ...).
if (Test-Path $AppSettingsPath) {
    $raw = Get-Content $AppSettingsPath -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) { $json = [pscustomobject]@{} }
    else { $json = $raw | ConvertFrom-Json }
} else {
    Write-Warning "No appsettings.Local.json at $AppSettingsPath. Creating one with only the Kestrel section."
    Write-Warning "The API still needs ConnectionStrings:DefaultConnection and Jwt:SecretKey to start — add those too."
    $json = [pscustomobject]@{}
}

$kestrel = @{
    Endpoints = @{
        Https = @{
            Url         = "https://0.0.0.0:$Port"
            Certificate = @{
                Path     = $pfxPath
                Password = $plainPwd
            }
        }
    }
}

$json | Add-Member -NotePropertyName Kestrel      -NotePropertyValue $kestrel -Force
$json | Add-Member -NotePropertyName AllowedHosts -NotePropertyValue $DnsName -Force

($json | ConvertTo-Json -Depth 32) | Set-Content -Path $AppSettingsPath -Encoding UTF8
Write-Host "Wrote Kestrel HTTPS endpoint (https://0.0.0.0:$Port) + AllowedHosts='$DnsName' into:" -ForegroundColor Green
Write-Host "  $AppSettingsPath" -ForegroundColor Green

# --- 3. Optional firewall rule -------------------------------------------------
if ($OpenFirewall) {
    $ruleName = "FedProspector HTTPS $Port"
    try {
        Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue |
            Remove-NetFirewallRule -ErrorAction SilentlyContinue
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow `
            -Protocol TCP -LocalPort $Port | Out-Null
        Write-Host "Firewall: inbound TCP $Port allowed ('$ruleName')." -ForegroundColor Green
    } catch {
        Write-Warning "Could not set firewall rule (run as Administrator?): $($_.Exception.Message)"
    }
}

# --- Done ----------------------------------------------------------------------
Write-Host ""
Write-Host "SSL setup complete. Next steps:" -ForegroundColor Cyan
Write-Host "  1. Run the API with ASPNETCORE_ENVIRONMENT=Production (enables Secure cookies, HSTS, HTTPS redirect; disables Swagger)." -ForegroundColor White
Write-Host "  2. Port-forward your router's public port -> this machine TCP $Port." -ForegroundColor White
Write-Host "  3. Restart the C# API to pick up the new config." -ForegroundColor White
Write-Host "  4. Users browse to https://$DnsName`:$Port and accept the one-time self-signed cert warning." -ForegroundColor White
Write-Host ""
Write-Host "  Re-run this script after every deploy (deploy overwrites appsettings.Local.json)." -ForegroundColor Yellow
