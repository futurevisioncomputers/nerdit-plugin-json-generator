<#
  The unattended Trend Reel run (see SKILL.md "Scheduled run"). Started by the Task Scheduler task that
  schedule_task.ps1 registers (Mon, Wed, Fri daily; Sun weekly). Takes a lock, waits for the article run (both drive
  the same Chrome and clipboard), wakes the Claude extension, runs Claude with a fixed prompt and tool allowlist,
  then shows the report's first line as a desktop notification. The Reel ends as a PENDING post: the owner approves.

  -DryRun: take the lock, print the command and paths, start nothing.
  -Kind daily|weekly: defaults to weekly on Sunday, daily otherwise.
#>
param(
  [switch]$DryRun,
  [ValidateSet('daily', 'weekly')][string]$Kind = $(if ((Get-Date).DayOfWeek -eq 'Sunday') { 'weekly' } else { 'daily' })
)

$home_ = if ($env:NERDIT_SOCIAL_HOME) { $env:NERDIT_SOCIAL_HOME } else { Join-Path $env:USERPROFILE '.nerdit-social' }
$runs = Join-Path $home_ 'trend-reels'
$logs = Join-Path $runs 'logs'
New-Item -ItemType Directory -Force $logs | Out-Null
$day = Get-Date -Format 'yyyy-MM-dd'
$log = Join-Path $logs "$day.log"
$report = Join-Path $runs 'last-report.md'
$lock = Join-Path $runs 'scheduled.lock'
$articleLock = Join-Path $home_ 'article-runs\scheduled.lock'

function Write-RunLog([string]$line) {
  $stamped = "$(Get-Date -Format 'HH:mm:ss') $line"
  Write-Output $stamped
  Add-Content -Path $log -Value $stamped -Encoding UTF8
}

# A desktop notification; clicking it opens $target (the Reel or the log).
function Show-Toast([string]$text, [string]$target) {
  try {
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml("<toast activationType='protocol' launch='$([Security.SecurityElement]::Escape(([Uri]$target).AbsoluteUri))'><visual><binding template='ToastGeneric'><text>NerdIT trend reel</text><text>$([Security.SecurityElement]::Escape($text))</text></binding></visual></toast>")
    $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show([Windows.UI.Notifications.ToastNotification]::new($xml))
  } catch {
    Write-RunLog "notification failed: $($_.Exception.Message)"
  }
}

function Test-FreshLock([string]$path) {
  (Test-Path $path) -and ((Get-Date) - (Get-Item $path).LastWriteTime).TotalHours -lt 3
}

# A lock younger than 3 hours means another run is going; an older one is left over from a crash.
if (Test-FreshLock $lock) {
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
  $scripts = (Join-Path $pluginDir 'skills\nerdit-trend-reels\scripts') -replace '\\', '/'
  $names = @('runs.py', 'collect.py', 'script_check.py', 'transcript.py', 'compose.py', 'trend_captions.py')

  # --setting-sources project drops the user-scoped nerdit MCP (verified 2026-11-25), so pass it by file; the token
  # comes from ~/.claude.json into an env var the file names. It is never written to a file, the log or the args.
  $mcpConfig = "$scripts/nerdit-mcp.json"
  # Python reads it: PowerShell 5.1's ConvertFrom-Json rejects ~/.claude.json (project keys differing only in case).
  $token = & python -c "import json,pathlib;print(json.loads((pathlib.Path.home()/'.claude.json').read_text(encoding='utf-8'))['mcpServers']['nerdit']['headers']['X-Nerdit-Token'])" 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $token) { $token = $null }

  $fullPrompt = "Use the nerdit-trend-reels skill: scheduled run, kind $Kind. Run the scripts exactly as: python $scripts/<name>.py (these paths, forward slashes, no quotes)."
  # Only these: Chrome, the skill, the six pinned scripts, reading the plugin and run folders, writing run files,
  # fetching article pages for the two-outlet check, and the course catalogue. Everything else is denied (dontAsk).
  $allowed = @('mcp__claude-in-chrome', 'Skill') + ($names | ForEach-Object { "Bash(python $scripts/$_ *)" }) + @(
    'Read(~/.claude/plugins/**)', 'Read(~/.nerdit-social/trend-reels/**)', 'Write(~/.nerdit-social/trend-reels/**)',
    'Edit(~/.nerdit-social/trend-reels/**)', 'WebFetch', 'WebSearch', 'mcp__nerdit__catalogue_status')
  # WebSearch: Google News feed links open only an empty "Google News" page (2026-11-26), so the run finds each
  # story's original article by its headline and outlet first.
  # The prompt goes right after -p: --allowedTools takes every value after it. --model sonnet: the script and
  # facts are held by script_check.py and the two-outlet rule (owner, 2026-11-27: save Claude tokens).
  $claudeArgs = @('-p', $fullPrompt, '--model', 'sonnet', '--chrome', '--setting-sources', 'project', '--plugin-dir', $pluginDir,
    '--mcp-config', $mcpConfig, '--permission-mode', 'dontAsk', '--disallowedTools', 'PowerShell', '--allowedTools') + $allowed

  if ($DryRun) {
    Write-Output 'claude args:'
    $claudeArgs | ForEach-Object { Write-Output $_ }
    Write-Output "kind: $Kind"
    Write-Output "nerdit token found: $([bool]$token)"
    Write-Output "log: $log"
    Write-Output "report: $report"
    Write-Output "lock: $lock"
    return
  }

  # Windows drops the bot's key presses while the PC is locked; LogonUI runs only while the lock screen is up.
  if (Get-Process LogonUI -ErrorAction SilentlyContinue) {
    Write-RunLog 'PC locked: run skipped'
    Show-Toast 'Skipped today: the PC was locked. No Reel today.' $log
    exit 0
  }
  if (-not $token) { Write-RunLog 'nerdit MCP token not found in ~/.claude.json'; Show-Toast 'Skipped: the NerdIT catalogue connection is missing.' $log; exit 1 }

  # The article run (11:00) drives the same Chrome and clipboard: wait for it, up to 2 hours.
  $waited = 0
  while ((Test-FreshLock $articleLock) -and $waited -lt 120) {
    if ($waited -eq 0) { Write-RunLog 'article run in progress: waiting' }
    Start-Sleep -Seconds 120
    $waited += 2
  }
  if (Test-FreshLock $articleLock) {
    Write-RunLog 'article run still going after 2 hours: run skipped'
    Show-Toast 'Skipped today: the article run was still going after 2 hours.' $log
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
  # The Claude extension can sit disconnected with Chrome open; opening its options page wakes it (article runner,
  # plugin commit c0f5753). shortcut: leaves that one tab open each run.
  Start-Process $chrome 'chrome-extension://fcoeoabgfenejglbffodgkkbkcdhcgfn/options.html'
  Start-Sleep -Seconds 10

  Write-RunLog "claude run starts ($Kind)"
  Show-Toast "Started $(Get-Date -Format 'HH:mm') ($Kind). It works in your Chrome: no copy-paste and no Chrome until the done message." $log
  $started = Get-Date
  $env:NERDIT_MCP_TOKEN = $token
  # The run folder is the working directory, so Chrome's file upload accepts reel.mp4 from it.
  Push-Location $runs
  try {
    & claude @claudeArgs 2>&1 | ForEach-Object { "$_" } | Add-Content -Path $log -Encoding UTF8
  } finally {
    Pop-Location
    Remove-Item Env:NERDIT_MCP_TOKEN -ErrorAction SilentlyContinue
  }
  $minutes = [math]::Ceiling(((Get-Date) - $started).TotalMinutes)
  Write-RunLog "claude run ends (exit $LASTEXITCODE, $minutes min)"

  $line = if (Test-Path $report) { (Get-Content -Path $report -Encoding UTF8 -TotalCount 1) } else { 'No report written - see the log' }
  $latest = Get-ChildItem -Path $runs -Directory | Where-Object Name -like "$day-*" | Sort-Object Name -Descending | Select-Object -First 1
  $target = if ($latest -and (Test-Path (Join-Path $latest.FullName 'reel.mp4'))) { Join-Path $latest.FullName 'reel.mp4' } else { $log }
  Show-Toast "Done in $minutes min. $line" $target
} finally {
  Remove-Item -Path $lock -Force -ErrorAction SilentlyContinue
}
