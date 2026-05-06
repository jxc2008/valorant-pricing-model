# Remote Desktop Setup — Autonomous Build

This guide configures a remote desktop to run the Phase 3+ build unsupervised.
Operator monitors via GitHub mobile app (commits + `.planning/STATE.md`).

## 1. System dependencies

- Python 3.11
- `uv` (package manager): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Tesseract 5.x system binary
  - Windows: `choco install tesseract` or download from UB-Mannheim
  - Linux: `sudo apt install tesseract-ocr`
  - Verify: `tesseract --version`
- Git
- Claude Code CLI: `npm install -g @anthropic-ai/claude-code`
- Anthropic account: `claude /login`

## 2. Clone and install

**Important:** clone to a non-OneDrive path. OneDrive sync conflicts with
concurrent writes to `.planning/`.

```bash
git clone https://github.com/jxc2008/valorant-pricing-model.git ~/projects/vpm
cd ~/projects/vpm
uv sync
```

## 3. Secrets

Transfer the following from a trusted source (password manager, encrypted USB):

- `.env` file at project root containing:
  - `TWITTER_BEARER_TOKEN=...`
  - `KALSHI_KEY_ID=...`
  - `KALSHI_KEY_PATH=/secure/path/to/kalshi-private.key`
- The Kalshi private key file at the path `KALSHI_KEY_PATH` references

Both are gitignored. Do not commit them.

## 4. Auto-push hook

The agent commits constantly. Without this hook, those commits sit on the
remote machine and never reach GitHub.

```bash
cat > .git/hooks/post-commit <<'EOF'
#!/bin/sh
git push origin main 2>&1 | logger -t vpm-autopush || true
EOF
chmod +x .git/hooks/post-commit
```

Auth: configure git to push without prompts. Easiest: SSH remote +
`ssh-agent` with key loaded, OR a fine-grained PAT in the credential cache.

## 5. Disable sleep

The machine must stay awake.

**Windows:**
```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
```

**Linux (GNOME):**
```bash
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'
```

## 6. Cron / Task Scheduler

Sets the auto-resume loop. Fires every hour; succeeds when Claude Code
usage budget is available, silently skips when it isn't.

**Windows (PowerShell as your user):**
```powershell
$projectDir = "C:\Users\$env:USERNAME\projects\vpm"
[Environment]::SetEnvironmentVariable("VPM_PROJECT_DIR", $projectDir, "User")

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File $projectDir\scripts\ops\resume-vpm.ps1"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) `
    -RepetitionInterval (New-TimeSpan -Hours 1) `
    -RepetitionDuration (New-TimeSpan -Days 60)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries
Register-ScheduledTask -TaskName "ResumeVPM" -Action $action -Trigger $trigger `
    -Settings $settings -RunLevel Limited
```

**Linux (crontab -e):**
```cron
# Every hour, resume the autonomous build
0 * * * * VPM_PROJECT_DIR=$HOME/projects/vpm $HOME/projects/vpm/scripts/ops/resume-vpm.sh
```

## 7. Kick off the build

Open Claude Code in the project directory:

```bash
cd ~/projects/vpm
claude
```

Paste the contents of `scripts/ops/START_PROMPT.txt` as the first message.
The agent will run `/gsd-autonomous` and start building. From this point,
the cron handles re-attaching after every usage-limit pause.

## 8. Monitor from your phone

Open the GitHub mobile app to your repo. Two views:

- **Commit log** — every atomic task = one commit. Each commit message
  identifies the phase and plan (e.g., `feat(03-04): arbiter tick loop`).
- **`.planning/STATE.md`** — current phase, current plan, `Stopped at:`
  field describing any halt.

When STATE.md shows the agent halted at an operator gate, log into the
desktop (or another machine with the repo cloned) to clear the gate.

## Operator-only gates that will halt the build

The agent will surface these via STATE.md and exit cleanly:

1. **Phase 03 OCR ROI calibration** — placeholders work; agent should not halt
   for this. Operator recalibrates against live broadcast frames later.
2. **Phase 04 first Kalshi auth test** — should pass via `.env`. Halts only
   on auth failure.
3. **End of Phase 5.2** — GO/NO-GO on entering paper trading.
4. **Phase 5.3 entry** — calendar-bound; needs a live VCT event.
5. **Phase 6 deployment** — bankroll, VM, key handling, --live flag.

## Killing the build

If something goes wrong and you need to stop the cron:

**Windows:** `Unregister-ScheduledTask -TaskName "ResumeVPM" -Confirm:$false`
**Linux:** `crontab -e` and remove the line

The currently-running Claude Code session (if any) won't be killed by
removing the cron — terminate it manually with Ctrl+C in its terminal,
or `taskkill` / `pkill claude`.

## Coordination caveat

Don't run `/gsd-autonomous` from this machine AND the desktop simultaneously.
They'll race on `.planning/STATE.md` commits. Pick one driver; the other
machine pulls-only for observation.
