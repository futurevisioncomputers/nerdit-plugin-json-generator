<#
  Turns the daily article run on or off: registers (or replaces) the Task Scheduler task
  "NerdIT article poster" for the current user, daily at -Time, or removes it with -Remove.
  Pick a time the PC is on, signed in, unlocked and not in use: the run drives the owner's own Chrome and
  clipboard. A start missed because the PC was off is skipped, not run at the next sign-in (the owner would be
  working then); the articles stay due for the next day.
#>
param(
  [string]$Time,
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

if (-not $Time) {
  Write-Output 'Give -Time HH:mm: a time the PC is on, unlocked and nobody is using it.'
  exit 1
}

$script = Join-Path $PSScriptRoot 'scheduled_run.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$script`""
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Output "registered: $name, daily at $Time, runs $script"
