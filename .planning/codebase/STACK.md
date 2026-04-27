# Technology Stack

**Analysis Date:** 2026-04-27

## Languages

**Primary:**
- Python 3.11 (target — declared in `roadmap.md` §0.2; not yet enforced by any config file). All `reference/*.py` use modern syntax (`from __future__ import annotations` in `reference/fair_value.py`, `tuple[float, float]` PEP 604 unions in `reference/odds_utils.py`) consistent with 3.10+.

**Secondary:**
- None. The repo is Python-only.

## Runtime

**Environment:**
- CPython 3.11 (planned). No `.python-version`, `runtime.txt`, or `pyproject.toml` is present to pin this — declared only in `roadmap.md` §0.2.

**Package Manager:**
- `uv` (planned per `roadmap.md` §0.2 and §6.3 — "uv run against dry_run=True"). Not yet installed/configured.
- Lockfile: missing. No `uv.lock`, `requirements.txt`, `requirements-dev.txt`, `Pipfile.lock`, or `poetry.lock` exists.

## Frameworks

**Core:**
- None installed. `src/` is scaffolded as empty `.gitkeep` placeholders under `src/config/`, `src/ingestion/`, `src/pricing/`, `src/quoting/`, `src/sizing/`, `src/state/`. No application framework chosen yet (no FastAPI, Flask, Django, asyncio framework, or message-bus library).

**Testing:**
- `pytest` + `pytest-cov` + `hypothesis` (planned per `roadmap.md` §0.2 and §5.1 — property-based tests on the DP). Not yet installed. `tests/` contains only `.gitkeep`.

**Build/Dev:**
- `ruff` (planned per `roadmap.md` §0.2 — "lint + format, one tool, fast"). No `ruff.toml`, `.ruff.toml`, or `[tool.ruff]` section yet.
- `mypy --strict` (planned per `roadmap.md` §0.2 and `CLAUDE.md` rule #11 — strict typing on `src/pricing/` only). No `mypy.ini` or `[tool.mypy]` section yet.

## Key Dependencies

**Critical (referenced in salvaged code, not yet declared in any manifest):**
- Standard library only inside `reference/odds_utils.py`, `reference/fair_value.py`, `reference/theo_engine.py` — they use `json`, `math`, `os`, `logging`, `typing`, `dataclasses`, `datetime`, `time`, `uuid`, `re`. No third-party imports.
- `reference/market_maker.py` imports two modules that **do not live in this repo**:
  - `from scraper.kalshi_client import KalshiClient, KalshiAPIError` (line 25) — Kalshi REST client salvaged from the sibling `thunderedge/` project, will need to be ported into `src/quoting/order_manager.py` per `roadmap.md` §4.1.
  - `from backend.theo_engine import TheoEngine` (line 26) — old import path; will be replaced by `src/pricing/live_theo.py` per `CLAUDE.md` rule #1.

**Planned (named in `prd.md` / `roadmap.md`, not yet in any manifest):**
- `cryptography` — required for Kalshi API v2 RSA PKCS1v15 / SHA-256 request signing (`CLAUDE.md` data-sources table, `prd.md` §6.4).
- `requests` or `httpx` — REST calls to Kalshi, rib.gg, bo3.gg.
- `opencv-python` + `pytesseract` (or `easyocr`) — OCR pipeline in `src/ingestion/ocr.py` per `roadmap.md` §3.3 ("port `vision_parser.py`"). `roadmap.md` says "tesseract + small CNNs are fine" if no GPU.
- `tweepy` or raw Twitter API v2 client — text listeners in `src/ingestion/text.py` per `roadmap.md` §3.4.
- `xgboost` — possibly for round-conclusion model per `prd.md` §7.5 ("XGBoost or hierarchical lookup"); the locked-in choice in `CLAUDE.md` is the hierarchical lookup, so XGBoost is unlikely.

**Infrastructure (planned, not yet configured):**
- Docker — single multi-stage `Dockerfile` planned per `roadmap.md` §6.1, target image < 500MB. No `Dockerfile` or `docker-compose.yml` exists yet.
- GitHub Actions — CI pipeline planned per `roadmap.md` §6.3. No `.github/workflows/` directory exists.

## Configuration

**Environment:**
- `.env` is the planned non-sensitive config holder per `roadmap.md` §6.4. File does not exist yet; `.gitignore` lines 2-3 already exclude `.env` and `.env.*` (with `!.env.example` allow-list, but no example file is present).
- No `.env.example` template exists yet. Add one when secrets are wired in.

**Key configs required (per `prd.md` §6.4 and `CLAUDE.md` data-sources):**
- Kalshi private key file — **mounted as Docker secret, not env var, not in image** (`roadmap.md` §6.4). `.gitignore` line 5 excludes `*.key` and line 6 excludes `*.pem`.
- Kalshi API key ID / username (env var, name TBD).
- Twitter API v2 bearer token (env var, name TBD) — for `src/ingestion/text.py`.
- rib.gg / bo3.gg API tokens if any are required (TBD pending Phase 2.1 probe per `roadmap.md` §2.1).

**Build:**
- `pyproject.toml` planned per `roadmap.md` §0.2. Not present yet — this is the largest single configuration gap.
- No `tsconfig.json`, `Cargo.toml`, `go.mod`, `package.json`, or other manifest (project is Python-only).

**Constants (planned in `src/config/constants.py`, not yet written):**
- Per `CLAUDE.md` "Domain constants" and rule #12 ("No magic numbers in business logic. Every threshold lives in `src/config/constants.py`"):
  - `SHRINK_PRIOR = 15.0`, `SIGNAL_SCALE = 0.10`, `GUN_WIN_RATE = 0.822`, `REGULATION_HALF = 12`, `WIN_THRESHOLD = 13`
  - `KELLY_MULTIPLIER = 0.5`, `PER_MARKET_CAP_FRAC = 0.05` (TBD)
  - `KILL_STALENESS_S = 5.0`, `KILL_DEVIATION_C = 20`, `KILL_BRIER_BOUND = 0.30`, `KILL_BRIER_WINDOW = 50`
  - `VEGA_DIRECTIONAL_THRESHOLD = 0.04` (TBD)

## Platform Requirements

**Development:**
- Windows 11 host. Project lives at `C:\Users\josep\OneDrive\Desktop\Thunderedge\valorant-pricing-model\` — under OneDrive (`prd.md` §5.5 acknowledges "OneDrive filesystem quirks tolerated here since no live capital").
- Bash shell available (used by tooling). Git installed. Repo is initialized (`b7b6db6 Initial scaffolding` is the only commit).
- Python 3.11 + `uv` (planned, not yet installed).

**Production:**
- Cloud VM, US-East. Recommended: Hetzner CCX13 (~$20/mo, 2 vCPU, 8GB RAM) per `roadmap.md` §6.2; AWS t3.small as alternative. Target: ~10–20ms RTT to Kalshi API (`prd.md` §5.5).
- Docker container, slim Python runtime. Image deployed via `docker pull && docker run` from GHCR.
- Secrets mounted from a separate key file at runtime (not baked into image, not visible in `docker inspect`).

## Notable Gaps

- **No dependency manifest of any kind.** No `pyproject.toml`, `requirements.txt`, `setup.py`, `Pipfile`, `poetry.lock`, or `uv.lock`. Phase 0.2 of `roadmap.md` is unstarted — the very first build action is to create `pyproject.toml` and run `uv sync`.
- **No tooling configs.** No `ruff.toml`, `mypy.ini`, `pytest.ini`, or `pre-commit-config.yaml`.
- **No Dockerfile, no CI config.** Both deferred to Phase 6.
- **`src/` is empty.** Every package directory under `src/` contains only a `.gitkeep`. `tests/`, `scripts/`, `models/`, `logs/` are all empty placeholders.
- **`reference/market_maker.py` imports `scraper.kalshi_client` and `backend.theo_engine`** — these are external to this repo (live in the sibling `thunderedge/` project). The file will not import successfully here; it is read-only reference per `CLAUDE.md` "Read first" section.

---

*Stack analysis: 2026-04-27*
