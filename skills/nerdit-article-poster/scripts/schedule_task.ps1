<#
  Turns the daily article run on or off: registers (or replaces) the Task Scheduler task
  "NerdIT article poster" for the current user, daily at -Time, or removes it with -Remove.
  Runs only while the owner is logged on (Chrome needs the desktop); a start missed because the PC was off
  runs as soon as it is on again.
#>
param(
  [string]$Time = '09:00',
  [switch]$Remove
)

$name = 'NerdIT article poster'

if ($Remove) {
  if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false
    Write-Output "removed: $name"
  } else {
    Write-Output "not registered: $name"
  }
  return
}

$script = Join-Path $PSScriptRoot 'scheduled_run.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Output "registered: $name, daily at $Time, runs $script"
