# Registers the morpheus reconciliation sweep as a Windows Scheduled Task
# (runs every 30 minutes). OPTIONAL — the hooks already dream on compaction/end;
# this only catches sessions that crashed or were archived/deleted without a
# clean SessionEnd. Requires: pip install morpheus-dreaming
#
#   pwsh -File schtask.windows.ps1            # install
#   pwsh -File schtask.windows.ps1 -Remove    # remove
param([switch]$Remove)

$ErrorActionPreference = "Stop"
$TaskName = "ClaudeMorpheusReconcile"
$Python   = (Get-Command python).Source

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task '$TaskName'."
    return
}

$action  = New-ScheduledTaskAction -Execute $Python -Argument "-m morpheus reconcile"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 30)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -DontStopOnIdleEnd -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Description "Claude morpheus: reconcile crashed/archived sessions" -Force | Out-Null
Write-Host "Installed scheduled task '$TaskName' (every 30 min)."
