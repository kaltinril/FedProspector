<#
.SYNOPSIS
    Open the Windows Firewall for the FedProspector HTTPS port (inbound TCP).
    Must run elevated — it self-elevates via UAC if you don't.

.DESCRIPTION
    Adds an inbound "Allow" rule for the API's HTTPS port so other machines (LAN and
    internet, via your router port-forward) can reach https://<this-box>:<port>.
    Idempotent: if the rule already exists it does nothing. The rule name matches the
    one used by generate-selfsigned-cert.ps1 -OpenFirewall, so there are no duplicates.

.PARAMETER Port
    TCP port to allow inbound. Default 5056 (the API's single HTTPS port).

.EXAMPLE
    # In any PowerShell window (it will prompt for elevation if needed):
    .\scripts\open-firewall.ps1

.EXAMPLE
    .\scripts\open-firewall.ps1 -Port 5056
#>
[CmdletBinding()]
param(
    [int]$Port = 5056
)

$ErrorActionPreference = "Stop"

# --- Self-elevate if not running as Administrator ---
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()
    ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "Not elevated - relaunching as Administrator (accept the UAC prompt)..." -ForegroundColor Yellow
    Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList @(
        "-NoProfile", "-NoExit", "-File", "`"$PSCommandPath`"", "-Port", $Port
    )
    return
}

# --- Add (or confirm) the inbound rule ---
$ruleName = "FedProspector API HTTPS $Port"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

if ($existing) {
    Write-Host "Firewall rule '$ruleName' already exists - nothing to do." -ForegroundColor DarkGray
} else {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow `
        -Protocol TCP -LocalPort $Port -Profile Any | Out-Null
    Write-Host "Opened inbound TCP $Port ('$ruleName')." -ForegroundColor Green
}

Write-Host ""
Write-Host "Verify:  Get-NetFirewallRule -DisplayName '$ruleName' | Get-NetFirewallPortFilter" -ForegroundColor DarkGray
