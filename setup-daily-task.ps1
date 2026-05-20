<#
    setup-daily-task.ps1 — THROWAWAY one-time scheduled-task registration.

    Run ONCE on the prod box from an elevated PowerShell prompt.
    Registers "FedProspect_DailyLoad" to run daily.ps1 at 6:00 AM and 6:00 PM.

    Delete this script (and remove from repo) after the task is registered.
#>

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$taskName   = "FedProspect_DailyLoad"
$scriptPath = "C:\git\fedProspect\daily.ps1"

if (-not (Test-Path $scriptPath)) {
    throw "daily.ps1 not found at $scriptPath. Deploy it first."
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""

$triggers = @(
    New-ScheduledTaskTrigger -Daily -At ([datetime]"06:00")
    New-ScheduledTaskTrigger -Daily -At ([datetime]"18:00")
)

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERNAME" `
    -LogonType S4U `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action -Trigger $triggers -Settings $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host "Registered '$taskName' to run daily at 6:00 AM and 6:00 PM." -ForegroundColor Green
Write-Host ""
Write-Host "Verify:  Get-ScheduledTaskInfo -TaskName $taskName" -ForegroundColor Yellow
Write-Host "Test:    Start-ScheduledTask -TaskName $taskName" -ForegroundColor Yellow
Write-Host "Remove:  Unregister-ScheduledTask -TaskName $taskName -Confirm:`$false" -ForegroundColor Yellow
