# resume-vpm.ps1 — Auto-resume Claude Code session for the autonomous build.
#
# Schedule via Windows Task Scheduler (run every hour). When Claude Code hits
# its usage limit, the next firing after the limit resets will succeed; other
# attempts log a one-line skip and exit.
#
# Setup:
#   $env:VPM_PROJECT_DIR = "C:\path\to\valorant-pricing-model"
#   New-ScheduledTaskAction -Execute "powershell.exe" `
#       -Argument "-NoProfile -ExecutionPolicy Bypass -File $PWD\scripts\ops\resume-vpm.ps1"
#   New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) `
#       -RepetitionInterval (New-TimeSpan -Hours 1)
#   Register-ScheduledTask -TaskName "ResumeVPM" -Action <action> -Trigger <trigger>
#
# The --dangerously-skip-permissions flag is intentional: unsupervised execution
# requires bypassing permission prompts. Restrict the desktop's network and
# filesystem accordingly.

$projectDir = if ($env:VPM_PROJECT_DIR) { $env:VPM_PROJECT_DIR } else { "$HOME\projects\vpm" }
$lockFile   = "$projectDir\.claude-running.lock"
$logFile    = "$projectDir\.claude-resume.log"

# Bail if a session is already running (avoid duplicate concurrent sessions)
if (Test-Path $lockFile) {
    $age = (Get-Date) - (Get-Item $lockFile).LastWriteTime
    if ($age.TotalHours -lt 8) {
        "$(Get-Date -Format 's') skipped - lock present (age $([int]$age.TotalMinutes)m)" |
            Out-File -Append $logFile -Encoding utf8
        exit 0
    }
    # Stale lock (>8h) — likely orphaned by a crashed session, clear it
    Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
}

Set-Location $projectDir
"" | Out-File $lockFile -Encoding utf8

try {
    "$(Get-Date -Format 's') resume attempt START" | Out-File -Append $logFile -Encoding utf8

    # Pull any updates first (in case the operator pushed a fix from another machine)
    git pull origin main 2>&1 | Out-File -Append $logFile -Encoding utf8

    # Resume the most recent conversation in this directory.
    # If the session is at a usage limit, this errors out cleanly.
    # If a halted-at-operator-gate, the agent re-reads STATE.md and reports.
    claude --continue --dangerously-skip-permissions `
        -p "if you stopped due to usage limit, continue with /gsd-autonomous" `
        2>&1 | Out-File -Append $logFile -Encoding utf8

    "$(Get-Date -Format 's') resume attempt END" | Out-File -Append $logFile -Encoding utf8
} finally {
    Remove-Item $lockFile -Force -ErrorAction SilentlyContinue
}
