# External Integrations

**Analysis Date:** 2026-04-27

## APIs & External Services

**Trading venue (live, primary):**
- **Kalshi API v2** — only execution venue. Quote and order placement for Valorant BO3 series-winner and per-map markets.
  - SDK/Client: planned `src/quoting/order_manager.py` (`roadmap.md` §4.1) — extracted from `reference/market_maker.py` which currently imports `from scraper.kalshi_client import KalshiClient, KalshiAPIError` (`reference/market_maker.py:25`). The `KalshiClient` itself lives in the sibling `thunderedge/` repo and must be ported.
  - Auth: RSA PKCS1v15 / SHA-256 request signing per `CLAUDE.md` data-sources table. Private key stored in a `.key` / `.pem` file (`.gitignore` lines 5-6 exclude both); mounted as a Docker secret in production per `roadmap.md` §6.4 — **never** committed to image, **never** placed in env vars.
  - **No Kalshi sandbox.** Per `CLAUDE.md` data-sources note, the bot remains in `dry_run=True` (`reference/market_maker.py:84` `dry_run: bool = True` default; `CLAUDE.md` rule #13 requires explicit `--live` CLI flag at the entry point) until the paper-trading promotion gate from `roadmap.md` §5.3 is met (≥ 1 full event with Brier < 0.22 and zero ingestion-bug kill-switch trips).
  - Used by: planned `src/quoting/order_manager.py`, `src/quoting/mm.py`, `src/quoting/directional.py` (`roadmap.md` §4.1–§4.4).
  - Endpoints exercised in `reference/market_maker.py`: `client.get_market(ticker)` (line 354), `client.place_order(...)` (line 225), `client.cancel_order(order_id)` (line 256), `client.find_valorant_markets()` (line 477).
  - Order-lifecycle reconciliation per `roadmap.md` §4.7 will additionally fetch open-orders list every poll cycle.

**Round-event data (offline, primary):**
- **rib.gg internal API** — round-by-round events for the round-conclusion model. No public REST documentation; routes via the `FlynV/RIB.GG-Web-Scraper` GitHub project or the `{valorantr}` R package per `CLAUDE.md` data-sources table.
  - Auth: TBD. Likely none for read paths, or a session cookie scrape.
  - Phase-gated: `prd.md` §7.4 / `roadmap.md` §2.1 require a one-day API probe (`scripts/probe_round_events.py`) to confirm whether per-round timestamps, kill events, bomb plant/defuse, and mid-round numerical state are exposed before committing to the round-conclusion model. **Decision gate** for Phase 1.5.
  - Candidate endpoints listed in `roadmap.md` §2.1: `https://api.rib.gg/v2/matches/{id}`, `/matches/{id}/rounds`, `/matches/{id}/events`.

**Round-event data (offline, backup):**
- **bo3.gg API** — fallback match data source. Per `CLAUDE.md` data-sources table the **filter params are broken** (inherited issue from sibling `thunderedge/` CLAUDE.md) — use the slug endpoint only.
  - Candidate endpoint: `https://api.bo3.gg/api/v1/matches/{slug}` per `roadmap.md` §2.1.
  - Auth: none required for read endpoints (per current understanding).

**Live visual feed:**
- **YouTube low-latency stream** — primary visual feed for OCR. ~3s end-to-end latency per `prd.md` §5.1 latency budget table; lowest latency public source. Consumed frame-by-frame by the planned `src/ingestion/ocr.py` (`roadmap.md` §3.3) which ports `vision_parser.py` from the sibling repo.
  - No SDK; uses `yt-dlp` / `streamlink` (TBD) for stream URL resolution, then OpenCV / ffmpeg for frame capture.
  - Targets per `roadmap.md` §3.3: score banner @ 250ms, kill feed @ 100ms, bomb icon @ 500ms, round-end banner @ 100ms during round-end window.

**Live visual feed (alternates, lower priority):**
- **Kalshi embedded video** — ~3–10s latency, medium reliability (`prd.md` §5.1). Not preferred.
- **Twitch HLS** — ~5–15s latency, high reliability (`prd.md` §5.1). Backup only.

**Soft cross-confirmation (live):**
- **Twitter API v2** — match-thread reactions, ~1–3s post-event. Streaming filter on match hashtags / accounts.
  - Auth: bearer token (env var, name TBD).
  - Used by: planned `src/ingestion/text.py` (`roadmap.md` §3.4).
  - **Never sole-source** per `CLAUDE.md` data-sources table — soft signal that arbiter cross-confirms against CV/scoreboard before committing to state.
- **Discord** — match-thread channels, similar latency profile. No SDK chosen yet; likely `discord.py` or webhook scraping. Same "never sole-source" rule applies.

**Pre-match scoreboard scrapers (offline, low-priority):**
- **vlr.gg** — historical odds and rosters. Used to derive `data/half_win_rates.json` upstream in the sibling `thunderedge/worktrees/half-win-rate/` project per `CLAUDE.md` data-sources table. Not called from this repo at runtime; the JSON file is the consumption surface.
- **rib.gg / bo3.gg / vlr.gg live scoreboard polling** at 5-60s post round per `prd.md` §5.1 latency budget. Authoritative but slow. Planned `src/ingestion/scoreboard.py` per `roadmap.md` §3.2 reuses the `vlr_scraper.py` / `rib_scraper.py` patterns from the sibling repo.

## Data Storage

**Databases:**
- **SQLite** — planned for the dataset cache only per `roadmap.md` §0.3 ("Existing repo uses SQLite. Stick with it for the dataset cache."). **Not used for live state** — `roadmap.md` §0.3 and `CLAUDE.md` "Differences from `thunderedge/CLAUDE.md`" both explicitly forbid SQLite for live state.
  - Connection: local file path under `data/` (TBD). `.gitignore` line 35 excludes `data/*.db` and line 36 excludes `data/*.sqlite`.
  - Client: stdlib `sqlite3` (assumed; no ORM chosen).

**File-backed state:**
- **In-memory `MatchState` object** — single source of truth for live match state per `prd.md` §5.2 and `roadmap.md` §3.1. Versioned via monotonic `seq_id`.
- **JSONL event log** — every state mutation appended to disk for replay / debugging per `CLAUDE.md` "Differences" section ("in-memory + JSONL event log") and `roadmap.md` §3.1. Path under `logs/` (gitignored — `.gitignore` line 38).
- **`data/half_win_rates.json`** (66KB, present) — the only data file currently checked in. Consumed at startup by the planned DP per `prd.md` §6 Tier 1. Generated upstream by sibling `thunderedge/worktrees/half-win-rate/`. Allow-listed in `.gitignore` line 44 (`!data/half_win_rates.json`) so it survives the broader `data/*.json` exclusion on line 32.
- **`models/dp_table.pkl`** (planned, gitignored) — pre-computed BO3 DP cache, ~10MB, mmap'd on load per `roadmap.md` §1.1.
- **`models/round_conclusion.json`** (planned) — hierarchical lookup table per `roadmap.md` §1.5.
- **`data/round_events`** (planned table) — pulled from rib.gg API per `roadmap.md` §2.2 if the API path works.

**File Storage:**
- Local filesystem only. No S3 / GCS / Azure Blob.

**Caching:**
- In-process: `@functools.lru_cache(maxsize=None)` on the BO3 DP per `roadmap.md` §1.1.
- No Redis / Memcached / external cache.

## Authentication & Identity

**Auth Provider:**
- None. Single-tenant trading bot. No user accounts, no OAuth flow, no JWT.
- The only "auth" surface is **outbound** to Kalshi (RSA-signed requests) and Twitter API v2 (bearer token).

## Monitoring & Observability

**Error Tracking:**
- None checked in. No Sentry / Rollbar / Bugsnag config.
- Planned per `roadmap.md` §6.5: PagerDuty / SMS alerts on kill-switch trips and process crashes (channel TBD).

**Logs:**
- Stdlib `logging.getLogger(__name__)` is the pattern in `reference/fair_value.py:44`, `reference/theo_engine.py` (implicit via stdlib only), and `reference/market_maker.py:28`.
- Planned per `roadmap.md` §6.5: structured JSON logs to stdout, captured by Docker, shipped to Loki / Grafana Cloud free tier.
- `logs/` directory exists (only `.gitkeep`); contents gitignored per `.gitignore` line 38.

**Metrics:**
- Planned per `roadmap.md` §3.6: latency instrumentation with `t_observed`, `t_ingested`, `t_arbited`, `t_state_committed`, `t_theo_computed`, `t_quote_sent` timestamps per event, written to a metrics file. Grafana dashboard in `roadmap.md` §6.6 (theo vs market, fill rate, current inventory, kill-switch trip log, latency p50/p99, daily P&L).

## CI/CD & Deployment

**Hosting:**
- Hetzner CCX13 (recommended) or AWS t3.small per `roadmap.md` §6.2. US-East for Kalshi proximity.
- Docker container deployed via SSH / `docker pull` per `roadmap.md` §6.3.

**CI Pipeline:**
- GitHub Actions (planned per `roadmap.md` §6.3): build Docker image, push to GHCR, run tests. No `.github/workflows/` directory exists yet.
- Local dev runs `uv run` against `dry_run=True` with real Kalshi credentials in `.env`.

## Environment Configuration

**Required env vars (planned, none currently set in repo):**
- Kalshi credentials — pair of (key ID, private key file path). Names TBD; likely `KALSHI_API_KEY_ID` and `KALSHI_PRIVATE_KEY_PATH`. **Private key file is the actual secret** and is not an env var per `roadmap.md` §6.4.
- Twitter API v2 bearer token — name TBD; likely `TWITTER_BEARER_TOKEN`.
- rib.gg / bo3.gg tokens if Phase 2.1 probe shows any are needed.
- `BANKROLL_USD` (or equivalent) — wires into half-Kelly sizer per `roadmap.md` §4.5; value TBD per `prd.md` §9.1.

**Secrets location:**
- `.env` for non-sensitive config (`roadmap.md` §6.4). Excluded by `.gitignore` lines 2-3 (`.env`, `.env.*`).
- Kalshi private key file — separate `.key` / `.pem` file, gitignored (`.gitignore` lines 5-6), backed up to a password manager per `roadmap.md` §6.4.
- `valorant*.txt` is also gitignored (`.gitignore` line 7) — appears to be a precaution against accidentally checking in tournament-data scratch files.

## Webhooks & Callbacks

**Incoming:**
- None. The bot is a polling client, not a webhook receiver. No HTTP server stood up.

**Outgoing:**
- None directly from the bot. PagerDuty / SMS alerts on kill-switch trips (`roadmap.md` §6.5) are the closest analog — outbound notifications, not webhooks.

## Notable Gaps

- **rib.gg API access is unproven.** The Phase 2.1 probe (`scripts/probe_round_events.py`, `roadmap.md` §2.1) has not been written. If the API doesn't expose mid-round numerical state and bomb plant timestamps, Phase 1.5 (round-conclusion model) drops to either a 2-week OCR labeling project (`roadmap.md` §2.3 Path B) or full deferral (`roadmap.md` §2.4 Path C, mid-round theo returns fixed `p = 0.5`). This is the single largest unresolved integration risk.
- **No KalshiClient in this repo.** `reference/market_maker.py` imports `scraper.kalshi_client` from the sibling `thunderedge/` project. The Phase 4.1 work (`roadmap.md` §4.1) must port — not just import — the client into `src/quoting/order_manager.py`.
- **No `.env.example`** — `.gitignore` allow-lists it on line 4 but the file doesn't exist. Add when secrets are wired in so onboarding is self-documenting.
- **OT modeling decision affects Kalshi market scope.** `prd.md` §3 excludes OT modeling, and `prd.md` §12.2 bug #3 calls out the silent OT-as-coinflip in `reference/theo_engine.py:194`. This must be resolved before any market touches a series that goes to OT — either explicit hard-stop at total=24 with documented OT-coinflip leaf (`roadmap.md` §1.4 recommendation) or skip those markets entirely.

---

*Integration audit: 2026-04-27*
