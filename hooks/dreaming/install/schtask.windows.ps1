# Registers the dreaming reconciliation sweep as a Windows Scheduled Task
# (runs every 30 minutes). OPTIONAL — the hooks already dream on compaction/end;
# this only catches sessions that crashed or were archived/deleted without a
# clean SessionEnd.
#
#   pwsh -File schtask.windows.ps1            # install
#   pwsh -File schtask.windows.ps1 -Remove    # remove
param([switch]$Remove)

$ErrorActionPreference = "Stop"
$TaskName  = "ClaudeDreamingReconcile"
$Reconcile = Join-Path (Split-Path $PSScriptRoot -Parent) "reconcile.py"
$Python    = (Get-Command python).Source

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task '$TaskName'."
    return
}

$action  = New-ScheduledTaskAction -Execute $Python -Argument "`"$Reconcile`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 30)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopOnIdleEnd -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Claude dreaming: reconcile crashed/archived sessions" -Force | Out-Null
Write-Host "Installed scheduled task '$TaskName' (every 30 min)."
