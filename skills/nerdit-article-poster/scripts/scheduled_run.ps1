<#
  The daily unattended article run (see SKILL.md "Scheduled run"). Started by the Task Scheduler task that
  schedule_task.ps1 registers. Takes a lock, makes sure Chrome is open, runs Claude with a fixed prompt and a
  fixed tool allowlist, logs its output, then shows the report's first line as a desktop notification.

  -DryRun: take the lock, print the command and paths, start nothing.
#>
param(
  [switch]$DryRun,
  [string]$Prompt = 'Use the nerdit-article-poster skill: scheduled run.'
)

$home_ = if ($env:NERDIT_SOCIAL_HOME) { $env:NERDIT_SOCIAL_HOME } else { Join-Path $env:USERPROFILE '.nerdit-social' }
$runs = Join-Path $home_ 'article-runs'
$logs = Join-Path $runs 'logs'
$reports = Join-Path $runs 'reports'
New-Item -ItemType Directory -Force $logs, $reports | Out-Null
$day = Get-Date -Format 'yyyy-MM-dd'
$log = Join-Path $logs "$day.log"
$report = Join-Path $reports "$day.md"
$lock = Join-Path $runs 'scheduled.lock'

function Write-RunLog([string]$line) {
  $stamped = "$(Get-Date -Format 'HH:mm:ss') $line"
  Write-Output $stamped
  Add-Content -Path $log -Value $stamped -Encoding UTF8
}

# A lock younger than 3 hours means another run is going; an older one is left over from a crash.
if ((Test-Path $lock) -and ((Get-Date) - (Get-Item $lock).LastWriteTime).TotalHours -lt 3) {
  Write-RunLog 'run in progress (lock held), exiting'
  exit 0
}
Set-Content -Path $lock -Value (Get-Date -Format o) -Encoding UTF8

try {
  # Exact strings confirmed by the Rollout spike; nothing that deploys, pushes, writes Firestore or sends mail.
  $allowed = @(
    'mcp__claude-in-chrome',
    'Skill',
    'Bash(python *runlog.py *)',
    'Bash(curl -sL *)',
    "Read($($home_ -replace '\\','/')/**)",
    "Write($($home_ -replace '\\','/')/**)"
  )
  $claudeArgs = @('-p', '--chrome', '--allowedTools') + $allowed + @($Prompt)

  if ($DryRun) {
    Write-Output ('claude ' + (($claudeArgs | ForEach-Object { if ($_ -match '\s') { "`"$_`"" } else { $_ } }) -join ' '))
    Write-Output "log: $log"
    Write-Output "report: $report"
    Write-Output "lock: $lock"
    return
  }

  if (-not (Get-Process chrome -ErrorAction SilentlyContinue)) {
    $chrome = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe' -ErrorAction SilentlyContinue).'(default)'
    if (-not $chrome) { $chrome = (Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe' -ErrorAction SilentlyContinue).'(default)' }
    if (-not $chrome) { Write-RunLog 'Chrome not found'; exit 1 }
    Write-RunLog 'starting Chrome'
    Start-Process $chrome
    Start-Sleep -Seconds 20
  }

  Write-RunLog 'claude run starts'
  Push-Location $runs
  try {
    & claude @claudeArgs 2>&1 | ForEach-Object { "$_" } | Add-Content -Path $log -Encoding UTF8
  } finally {
    Pop-Location
  }
  Write-RunLog "claude run ends (exit $LASTEXITCODE)"

  $line = if (Test-Path $report) { (Get-Content -Path $report -Encoding UTF8 -TotalCount 1) } else { 'No report written - see the log' }
  try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    $target = if (Test-Path $report) { $report } else { $log }
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml("<toast activationType='protocol' launch='$([Security.SecurityElement]::Escape(([Uri]$target).AbsoluteUri))'><visual><binding template='ToastGeneric'><text>NerdIT article poster</text><text>$([Security.SecurityElement]::Escape($line))</text></binding></visual></toast>")
    $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show([Windows.UI.Notifications.ToastNotification]::new($xml))
  } catch {
    Write-RunLog "notification failed: $($_.Exception.Message)"
  }
} finally {
  Remove-Item -Path $lock -Force -ErrorAction SilentlyContinue
}
