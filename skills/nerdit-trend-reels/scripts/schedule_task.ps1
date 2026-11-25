<#
  Turns the Trend Reel timer on or off: registers (or replaces) the Task Scheduler task "NerdIT trend reel" for the
  current user, weekly on Monday, Wednesday, Friday and Sunday at -Time (default 11:30, after the 11:00 article
  run), or removes it with -Remove. Register only after the owner's OK on the pilot Reel.
  A start missed because the PC was off is skipped, not run at the next sign-in.
#>
param(
  [string]$Time = '11:30',
  [switch]$Remove
)

$name = 'NerdIT trend reel'

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
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday, Wednesday, Friday, Sunday -At $Time
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 3) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Output "registered: $name, Mon/Wed/Fri/Sun at $Time, runs $script"
