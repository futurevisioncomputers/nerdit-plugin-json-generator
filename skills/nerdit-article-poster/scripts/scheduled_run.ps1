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

# A desktop notification; clicking it opens $target (the report or the log).
function Show-Toast([string]$text, [string]$target) {
  try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml("<toast activationType='protocol' launch='$([Security.SecurityElement]::Escape(([Uri]$target).AbsoluteUri))'><visual><binding template='ToastGeneric'><text>NerdIT article poster</text><text>$([Security.SecurityElement]::Escape($text))</text></binding></visual></toast>")
    $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show([Windows.UI.Notifications.ToastNotification]::new($xml))
  } catch {
    Write-RunLog "notification failed: $($_.Exception.Message)"
  }
}

# A lock younger than 3 hours means another run is going; an older one is left over from a crash.
if ((Test-Path $lock) -and ((Get-Date) - (Get-Item $lock).LastWriteTime).TotalHours -lt 3) {
  Write-RunLog 'run in progress (lock held), exiting'
  exit 0
}
Set-Content -Path $lock -Value (Get-Date -Format o) -Encoding UTF8

try {
  # The installed plugin, loaded by --plugin-dir: the run skips the owner's user settings (their allow rules and hooks).
  $installed = Join-Path $env:USERPROFILE '.claude\plugins\installed_plugins.json'
  $pluginDir = $null
  if (Test-Path $installed) {
    $entry = (Get-Content -Path $installed -Raw -Encoding UTF8 | ConvertFrom-Json).plugins.'nerdit_content_creator@fv-analysis-marketplace'
    if ($entry) { $pluginDir = $entry[0].installPath }
  }
  if (-not $pluginDir -or -not (Test-Path $pluginDir)) { Write-RunLog 'NerdIT plugin not installed'; exit 1 }
  $runlog = (Join-Path $pluginDir 'skills\nerdit-article-poster\scripts\runlog.py') -replace '\\', '/'

  $fullPrompt = "$Prompt Run runlog exactly as: python $runlog <command> (this path, forward slashes, no quotes)."
  # Only these: Chrome, the skill, runlog (pinned path), and reading the plugin's recipes. No curl, no file writes
  # (runlog saves images and the report), no git, deploy, Firestore or mail. Everything else is denied (dontAsk).
  $allowed = @('mcp__claude-in-chrome', 'Skill', "Bash(python $runlog *)", 'Read(~/.claude/plugins/**)')
  # The prompt goes right after -p: --allowedTools takes every value after it. --add-dir: Chrome's file upload
  # takes only files the session may read ("only files this session is allowed to read can be uploaded"), and
  # runlog saves the article images under $runs. --model sonnet: the daily run follows a written recipe in
  # Chrome; the main model is not needed for it (owner, 2026-11-27: save Claude tokens).
  $claudeArgs = @('-p', $fullPrompt, '--model', 'sonnet', '--chrome', '--setting-sources', 'project', '--plugin-dir', $pluginDir,
    '--add-dir', $runs, '--permission-mode', 'dontAsk', '--disallowedTools', 'PowerShell', '--allowedTools') + $allowed

  if ($DryRun) {
    Write-Output 'claude args:'
    $claudeArgs | ForEach-Object { Write-Output $_ }
    Write-Output "log: $log"
    Write-Output "report: $report"
    Write-Output "lock: $lock"
    return
  }

  # Windows drops the bot's key presses while the PC is locked (2026-11-24: Ctrl+V pasted nothing, Ctrl+A typed
  # "a"); LogonUI runs only while the lock screen is up. Skip the day; the articles stay due for tomorrow.
  if (Get-Process LogonUI -ErrorAction SilentlyContinue) {
    Write-RunLog 'PC locked: run skipped (the bot cannot type while Windows is locked)'
    Show-Toast 'Skipped today: the PC was locked. The articles go out tomorrow.' $log
    exit 0
  }

  $chrome = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe' -ErrorAction SilentlyContinue).'(default)'
  if (-not $chrome) { $chrome = (Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe' -ErrorAction SilentlyContinue).'(default)' }
  if (-not $chrome) { Write-RunLog 'Chrome not found'; exit 1 }
  if (-not (Get-Process chrome -ErrorAction SilentlyContinue)) {
    Write-RunLog 'starting Chrome'
    Start-Process $chrome
    Start-Sleep -Seconds 20
  }
  # The Claude extension can sit disconnected with Chrome open (2026-11-25: "Browser extension is not connected"
  # until its page was opened); opening its options page wakes it. shortcut: leaves that one tab open each run.
  Start-Process $chrome 'chrome-extension://fcoeoabgfenejglbffodgkkbkcdhcgfn/options.html'
  Start-Sleep -Seconds 10

  Write-RunLog 'claude run starts'
  Show-Toast "Started $(Get-Date -Format 'HH:mm'). It posts in your Chrome: no copy-paste and no Chrome until the done message." $log
  $started = Get-Date
  Push-Location $runs
  try {
    & claude @claudeArgs 2>&1 | ForEach-Object { "$_" } | Add-Content -Path $log -Encoding UTF8
  } finally {
    Pop-Location
  }
  $minutes = [math]::Ceiling(((Get-Date) - $started).TotalMinutes)
  Write-RunLog "claude run ends (exit $LASTEXITCODE, $minutes min)"

  $line = if (Test-Path $report) { (Get-Content -Path $report -Encoding UTF8 -TotalCount 1) } else { 'No report written - see the log' }
  Show-Toast "Done in $minutes min. $line" $(if (Test-Path $report) { $report } else { $log })
} finally {
  Remove-Item -Path $lock -Force -ErrorAction SilentlyContinue
}
