<#
.SYNOPSIS
    Generate a self-signed HTTPS certificate (.pfx) for the FedProspector API and
    print the appsettings.Local.json snippet to paste.

.DESCRIPTION
    The API serves HTTPS on Kestrel using a self-signed cert (single-port public
    exposure, threat model = unauthenticated attackers only). This script creates a
    cert in the current-user store, exports it to a password-protected .pfx, and
    prints the Kestrel:Endpoints:Https:Certificate config you must add to the
    gitignored appsettings.Local.json.

    NOTHING produced here is committed: .pfx files and appsettings.Local.json are
    both gitignored. Keep the password out of source control.

.PARAMETER DnsName
    The public hostname (or IP) clients will use. Used as the cert subject/SAN.

.PARAMETER OutputPath
    Where to write the .pfx. Defaults to .\fedprospector.pfx next to this script's repo root.

.PARAMETER Password
    Password to protect the .pfx. If omitted you'll be prompted securely.

.EXAMPLE
    .\scripts\generate-selfsigned-cert.ps1 -DnsName my.public.host -OutputPath C:\certs\fedprospector.pfx
#>
param(
    [Parameter(Mandatory = $true)]
    [string]$DnsName,

    [string]$OutputPath = "$PSScriptRoot\..\fedprospector.pfx",

    [securestring]$Password
)

if (-not $Password) {
    $Password = Read-Host -AsSecureString -Prompt "Enter a password to protect the .pfx"
}

Write-Host "Creating self-signed certificate for '$DnsName'..." -ForegroundColor Green
$cert = New-SelfSignedCertificate `
    -DnsName $DnsName `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -KeyExportPolicy Exportable `
    -KeyUsage DigitalSignature, KeyEncipherment `
    -KeyAlgorithm RSA `
    -KeyLength 2048 `
    -NotAfter (Get-Date).AddYears(5) `
    -FriendlyName "FedProspector API ($DnsName)"

$OutputPath = [System.IO.Path]::GetFullPath($OutputPath)
Export-PfxCertificate -Cert $cert -FilePath $OutputPath -Password $Password | Out-Null
Write-Host "Exported PFX to: $OutputPath" -ForegroundColor Green

# Remove the cert from the user store; Kestrel loads it from the .pfx file.
Remove-Item "Cert:\CurrentUser\My\$($cert.Thumbprint)" -ErrorAction SilentlyContinue

$plainPwd = [System.Net.NetworkCredential]::new("", $Password).Password
$escapedPath = $OutputPath -replace '\\', '\\'

Write-Host ""
Write-Host "Add this to appsettings.Local.json (gitignored — never commit the .pfx or password):" -ForegroundColor Cyan
Write-Host @"
  "Kestrel": {
    "Endpoints": {
      "Https": {
        "Url": "https://0.0.0.0:5056",
        "Certificate": {
          "Path": "$escapedPath",
          "Password": "$plainPwd"
        }
      }
    }
  }
"@ -ForegroundColor White
Write-Host ""
Write-Host "Then port-forward your router's public port to this machine's TCP 5056." -ForegroundColor Yellow
