---
phase: 00-foundation
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - .python-version
  - uv.lock
  - src/__init__.py
  - src/pricing/__init__.py
  - src/state/__init__.py
  - src/ingestion/__init__.py
  - src/quoting/__init__.py
  - src/sizing/__init__.py
  - src/config/__init__.py
  - tests/__init__.py
  - tests/.gitkeep
  - tests/test_smoke.py
  - scripts/.gitkeep
  - data/.gitkeep
  - models/.gitkeep
  - logs/.gitkeep
  - .gitignore
autonomous: true
requirements: []
must_haves:
  truths:
    - "DEC-019 (project layout) — `src/{pricing,state,ingestion,quoting,sizing,config}/` directories all exist as importable Python packages"
    - "DEC-014 / CON-tooling-versions — Python 3.11 pinned via `pyproject.toml` and `.python-version`"
    - "DEC-014 / CON-mypy-strict-pricing — `uv run mypy --strict src/pricing/` exits 0 against the empty package skeleton"
    - "DEC-014 — `uv run ruff check .` exits 0 against the empty package skeleton"
    - "DEC-014 — `uv run pytest --collect-only` exits 0 (zero tests collected, no errors)"
    - "DEC-015 / CON-live-state-no-sqlite — `models/`, `logs/`, generated `data/*` artifacts are gitignored except for explicit allow-list"
    - "ROADMAP Phase 0 must-have #1 satisfied: `src/{pricing,state,ingestion,quoting,sizing,config}/` directory tree exists; `tests/`, `scripts/`, `data/`, `models/`, `reference/` siblings in place"
    - "ROADMAP Phase 0 must-have #2 satisfied: `pyproject.toml` declares Python 3.11 + uv-managed deps; `mypy --strict src/pricing/` runs (even on empty modules); `ruff` passes"
    - "`uv.lock` is committed for reproducibility per uv application-project convention; Phase 6 (CI/Docker) inherits a deterministic build with no rework"
    - "`tests/test_smoke.py` exists as a sentinel so `pytest --collect-only` exits 0 (not 5) on the empty skeleton; safe to delete once any other test file lands in `tests/`"
  artifacts:
    - path: "pyproject.toml"
      provides: "Python 3.11 pin, uv project config, pytest+pytest-cov+hypothesis dev deps, ruff config, mypy --strict on src/pricing config"
      contains: '[project], requires-python = ">=3.11,<3.12", [tool.ruff], [tool.mypy], overrides for src.pricing'
    - path: ".python-version"
      provides: "uv-readable python pin"
      contains: "3.11"
    - path: "uv.lock"
      provides: "uv-managed dependency lock file — committed for reproducibility (Phase 6 deployment will inherit it)"
    - path: "src/__init__.py"
      provides: "src package marker"
    - path: "src/pricing/__init__.py"
      provides: "pricing subpackage marker — replaces .gitkeep so mypy --strict has a real module"
    - path: "src/state/__init__.py"
      provides: "state subpackage marker"
    - path: "src/ingestion/__init__.py"
      provides: "ingestion subpackage marker"
    - path: "src/quoting/__init__.py"
      provides: "quoting subpackage marker"
    - path: "src/sizing/__init__.py"
      provides: "sizing subpackage marker"
    - path: "src/config/__init__.py"
      provides: "config subpackage marker"
    - path: "tests/__init__.py"
      provides: "tests package marker — pytest discoverable"
    - path: "tests/test_smoke.py"
      provides: "pytest sentinel so `--collect-only` exits 0 on the empty skeleton; trivially passing `test_smoke()`"
      contains: "def test_smoke() -> None: assert True"
  key_links:
    - from: "pyproject.toml [tool.mypy] override for module=src.pricing.*"
      to: "src/pricing/__init__.py"
      via: "mypy strict mode discovers src.pricing via project layout"
      pattern: 'module = "src\\.pricing\\.\\*"'
    - from: ".gitignore"
      to: "data/, models/, logs/"
      via: "explicit allow-list keeps half_win_rates.json + .gitkeep files committed"
      pattern: "!data/half_win_rates.json"
    - from: "pyproject.toml [tool.uv]"
      to: ".venv/"
      via: "uv sync materializes deps into .venv (gitignored)"
      pattern: "\\[tool\\.uv\\]"
---

<objective>
Establish the Phase 0 project skeleton: `pyproject.toml` with Python 3.11 + uv + pytest+hypothesis + ruff + mypy --strict on `src/pricing/`; convert every `src/*/` subdir from `.gitkeep`-only into a real importable Python package; ensure `tests/`, `scripts/`, `data/`, `models/`, `logs/` are committed placeholders; verify all four toolchain commands (`uv sync`, `uv run mypy --strict src/pricing/`, `uv run ruff check .`, `uv run pytest --collect-only`) pass on the empty skeleton.

Purpose: This unblocks Phases 1, 2, 3 (which run in parallel). Without `pyproject.toml` and a passing toolchain on the empty skeleton, no downstream phase can land code that satisfies CON-mypy-strict-pricing. Per DEC-014 / DEC-019.

Output: A repo where `uv sync && uv run mypy --strict src/pricing/ && uv run ruff check . && uv run pytest --collect-only` is green from a clean clone.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/intel/constraints.md
@.planning/intel/decisions.md
@.planning/codebase/STACK.md
@.planning/codebase/STRUCTURE.md
@CLAUDE.md
@roadmap.md
@.gitignore

<interfaces>
<!-- No code interfaces yet — Phase 0 is bootstrap. The "interface" here is the toolchain
     contract: every downstream plan will assume `uv run mypy --strict src/pricing/`,
     `uv run ruff check .`, and `uv run pytest` work. This plan creates that contract. -->

Toolchain commands downstream plans depend on:
- `uv sync` — materializes deps into .venv from pyproject.toml + uv.lock
- `uv run mypy --strict src/pricing/` — strict type-check on math layer ONLY (CON-mypy-strict-pricing)
- `uv run ruff check .` — lint whole repo
- `uv run ruff format --check .` — formatter check
- `uv run pytest` — run test suite (Phase 0 has only `tests/test_smoke.py` as a sentinel; this plan verifies `--collect-only` succeeds with exit 0)

Package import contract (downstream plans rely on these import paths existing):
- `from src.config.constants import GUN_WIN_RATE`  — Plan 02 will populate
- `from src.pricing import ...`  — Phase 1 will populate
- `from src.state import ...`  — Phase 3 will populate
- `from src.quoting import ...`  — Phase 4 will populate
- `from src.sizing import ...`  — Phase 4 will populate
- `from src.ingestion import ...`  — Phase 3 will populate
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create pyproject.toml + .python-version with full uv/ruff/mypy/pytest config</name>
  <files>pyproject.toml, .python-version</files>
  <read_first>
    - .planning/intel/constraints.md (sections CON-tooling-versions, CON-mypy-strict-pricing, CON-package-layout)
    - .planning/intel/decisions.md (DEC-014, DEC-019)
    - roadmap.md (§0.2 Tooling)
    - CLAUDE.md (Critical rules #11 "mypy --strict on src/pricing/", #12 "no magic numbers")
    - .planning/codebase/STACK.md (Notable Gaps section — confirms no manifest exists today)
  </read_first>
  <action>
Create `.python-version` with the single line `3.11` (no newline-trailing requirement; uv tolerates either).

Create `pyproject.toml` with EXACTLY the following content (do not paraphrase, do not reorder sections):

```toml
[project]
name = "valorant-pricing-model"
version = "0.1.0"
description = "Live pricing engine for Valorant BO3 series + per-map Kalshi markets"
readme = "README.md"
requires-python = ">=3.11,<3.12"
authors = [
    { name = "jxc2008", email = "jxc2008@nyu.edu" },
]
dependencies = []

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "hypothesis>=6.100",
    "ruff>=0.6.0",
    "mypy>=1.11",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src"]

[tool.uv]
package = true

[tool.ruff]
line-length = 100
target-version = "py311"
extend-exclude = [
    "reference/",
    "models/",
    "logs/",
    ".venv/",
]

[tool.ruff.lint]
# Conservative starter set; tighten in later phases.
select = [
    "E",      # pycodestyle errors
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "UP",     # pyupgrade
    "N",      # pep8-naming
    "SIM",    # flake8-simplify
]
ignore = []

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["N802", "N803"]  # test fn / param names may be Pascal-ish
"scripts/**" = ["N999"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.pytest.ini_options]
minversion = "8.0"
testpaths = ["tests"]
addopts = [
    "--strict-markers",
    "--strict-config",
    "-ra",
]

[tool.coverage.run]
source = ["src/pricing"]
branch = true

[tool.coverage.report]
fail_under = 0  # Phase 0 has no tests; coverage gate is enforced in Phase 5 (CON-coverage-target = 80%).
show_missing = true
skip_covered = false

[tool.mypy]
# Default: gradual typing for non-pricing layers per CONVENTIONS.md.
python_version = "3.11"
files = ["src", "tests"]
exclude = ["reference/", "models/", "logs/", "scripts/"]
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
ignore_missing_imports = true

[[tool.mypy.overrides]]
# CON-mypy-strict-pricing: the math layer must type-check fully.
module = "src.pricing.*"
strict = true
disallow_any_explicit = false  # allow Any in narrow places if explicitly written
warn_return_any = true
```

Notes for the executor:
- Use the Write tool. Do not use heredoc.
- Do NOT add a `[tool.uv.sources]` section; we have no path-based deps.
- Do NOT add a top-level `[tool.uv].dev-dependencies` block — uv reads `[dependency-groups].dev` per PEP 735, which is what `uv sync` installs by default.
- The `package = true` under `[tool.uv]` makes uv install the project itself into .venv as editable, so `from src.pricing.constants import ...` resolves at runtime in Phase 2 onwards. Without this, `src/` is not on sys.path under `uv run`.
- Hatchling is the simplest PEP 517 build backend that ships with uv's defaults. We pin packages = ["src"] so the wheel includes the `src/` tree.

After writing both files, run `uv sync` to materialize .venv. Then run the four verification commands listed below.
  </action>
  <verify>
    <automated>test -f pyproject.toml &amp;&amp; test -f .python-version &amp;&amp; grep -q 'requires-python = ">=3.11,<3.12"' pyproject.toml &amp;&amp; grep -q 'pytest>=8' pyproject.toml &amp;&amp; grep -q 'pytest-cov>=5' pyproject.toml &amp;&amp; grep -q 'hypothesis>=6' pyproject.toml &amp;&amp; grep -q 'ruff>=0' pyproject.toml &amp;&amp; grep -q 'mypy>=1' pyproject.toml &amp;&amp; grep -q 'module = "src\.pricing\.\*"' pyproject.toml &amp;&amp; grep -q 'strict = true' pyproject.toml &amp;&amp; grep -q '^3\.11$' .python-version</automated>
  </verify>
  <done>
    `pyproject.toml` exists with Python 3.11 pin, dev-deps (pytest, pytest-cov, hypothesis, ruff, mypy), `[tool.ruff]` with line-length 100 / target py311 / extend-exclude reference+models+logs+.venv, `[tool.pytest.ini_options]` with testpaths=tests, `[tool.mypy]` default config + strict override on `src.pricing.*`. `.python-version` contains exactly `3.11`. `uv sync` succeeds (creates `.venv/` and `uv.lock`).
  </done>
</task>

<task type="auto">
  <name>Task 2: Convert src/* subdirs from .gitkeep to real Python packages + add tests/__init__.py + tests/test_smoke.py + ensure scripts/ data/ models/ logs/ have .gitkeep + tighten .gitignore</name>
  <files>src/__init__.py, src/pricing/__init__.py, src/state/__init__.py, src/ingestion/__init__.py, src/quoting/__init__.py, src/sizing/__init__.py, src/config/__init__.py, tests/__init__.py, tests/.gitkeep, tests/test_smoke.py, scripts/.gitkeep, data/.gitkeep, models/.gitkeep, logs/.gitkeep, .gitignore</files>
  <read_first>
    - .planning/codebase/STRUCTURE.md (Directory Layout — confirms intended subpackages and that src/* currently holds only .gitkeep)
    - .planning/intel/constraints.md (CON-package-layout, CON-live-state-no-sqlite)
    - .planning/intel/decisions.md (DEC-019)
    - .gitignore (current contents — to be extended, NOT replaced)
    - CLAUDE.md ("Repo layout" section)
  </read_first>
  <action>
**Step A — Create `src/__init__.py`** with the following content:
```python
"""Valorant live pricing model — top-level package.

See CLAUDE.md and prd.md for design intent. The single canonical pricing entry
point is `src.pricing.live_theo.live_theo` (DEC-010). The single source-of-truth
for thresholds and magic numbers is `src.config.constants` (DEC-016 / CLAUDE.md
rule 12).
"""
```

**Step B — Create `src/pricing/__init__.py`** with the following content:
```python
"""Pricing layer — DP, Bradley-Terry blend, round-conclusion lookup, live_theo.

This package is type-checked under `mypy --strict` (CON-mypy-strict-pricing).
Every threshold imported here MUST come from `src.config.constants` (CLAUDE.md
rule 12). The single canonical pricing entry point is `live_theo` per DEC-010 —
do not introduce parallel `series_theo_*` variants.
"""
```

**Step C — Create the remaining empty subpackage `__init__.py` files** with one-line module docstrings each (these are what makes `mypy --strict` work against an otherwise-empty package — without an `__init__.py` the package is implicit-namespace and mypy strict refuses to type-check it cleanly):

`src/state/__init__.py`:
```python
"""State engine — `MatchState` dataclass + JSONL event log (Phase 3)."""
```

`src/ingestion/__init__.py`:
```python
"""Ingestion layer — OCR, scoreboard polling, text listeners, cross-source arbiter (Phase 3)."""
```

`src/quoting/__init__.py`:
```python
"""Quoting layer — KalshiOrderManager, mode selector, MM, directional, kill switches (Phase 4)."""
```

`src/sizing/__init__.py`:
```python
"""Sizing layer — half-Kelly with per-market cap (Phase 4 / DEC-004)."""
```

`src/config/__init__.py`:
```python
"""Configuration layer — single home for all magic numbers (DEC-016 / CLAUDE.md rule 12).

See `src.config.constants` for the canonical threshold values.
"""
```

**Step D — Create `tests/__init__.py`** with the following content (makes `tests/` an importable package so `pytest` test discovery is unambiguous; per pytest docs the alternative `rootdir + conftest` works too, but `__init__.py` avoids the `import file mismatch` class of bug for our flat layout):
```python
"""pytest test suite for valorant-pricing-model."""
```

**Step E — Delete `src/pricing/.gitkeep`, `src/state/.gitkeep`, `src/ingestion/.gitkeep`, `src/quoting/.gitkeep`, `src/sizing/.gitkeep`, `src/config/.gitkeep` if they exist** (the new `__init__.py` files supersede them).

```bash
rm -f src/pricing/.gitkeep src/state/.gitkeep src/ingestion/.gitkeep src/quoting/.gitkeep src/sizing/.gitkeep src/config/.gitkeep
```

**Step F — Ensure non-package placeholder dirs have `.gitkeep`, AND create `tests/test_smoke.py`** (some `.gitkeep`s may already exist):
- `tests/.gitkeep` — keep alongside `tests/__init__.py`; pytest will collect from `tests/` even when it has only `__init__.py`, but `.gitkeep` makes the dir survive a future `__init__.py` deletion. (Belt + suspenders.)
- `scripts/.gitkeep`
- `data/.gitkeep`
- `models/.gitkeep`
- `logs/.gitkeep`

For each `.gitkeep`, if missing, create an empty file. Use Write with content `""` (empty string).

Then create `tests/test_smoke.py` with EXACTLY the following content (this is the sentinel that prevents `pytest --collect-only` from exiting 5 on the empty skeleton — pytest exit-code 5 means "no tests collected" and is treated as a failure by our verify chain):

```python
"""Smoke test — exists so `pytest --collect-only` exits 0 on the empty skeleton.

Replace with real tests as features land in Phases 1+. Safe to delete once
any other test file exists in `tests/`.
"""

def test_smoke() -> None:
    assert True
```

**Step G — Extend `.gitignore`** by appending the following lines AFTER the existing `desktop.ini` line (do NOT remove or reorder existing rules — the existing `.gitignore` already covers `.env*`, `*.key`, `__pycache__/`, `.venv/`, `data/*.json` allow-listing `half_win_rates.json`, `models/`, `logs/`):

```
# uv
.uv/

# Generated DP table + round events (Phase 1 / Phase 2 outputs)
models/dp_table.pkl
data/round_events*
data/round_events.sqlite

# Tooling caches not yet covered above
.tox/
.nox/
```

NOTE: `models/` is already wholesale gitignored on line 37 of the current `.gitignore`, so `models/dp_table.pkl` is technically redundant — included for documentation / readability. Same for `logs/`. This is intentional: the explicit lines name the actual artifacts a future grep will look for.

NOTE: `uv.lock` is COMMITTED to the repo (do NOT add it to `.gitignore`). Per uv's application-project convention, the lock file is checked in so every clone — and especially the Phase 6 CI / Docker build — resolves to the exact same dependency versions. This avoids rework when deployment lands.

**Step H — Verify the package skeleton is intact** by running:
```bash
uv run python -c "import src; import src.pricing; import src.state; import src.ingestion; import src.quoting; import src.sizing; import src.config; print('ok')"
```
This must print `ok`.

**Step I — Run the four toolchain verification commands** and confirm exit-code 0 for each:
```bash
uv sync
uv run mypy --strict src/pricing/
uv run ruff check .
uv run pytest --collect-only
```

`pytest --collect-only` should now report `1 test collected` (the `tests/test_smoke.py::test_smoke` sentinel) and exit 0. The sentinel was added in Step F precisely to avoid pytest's exit-5 ("no tests collected") failure on the empty skeleton.
  </action>
  <verify>
    <automated>test -f src/__init__.py &amp;&amp; test -f src/pricing/__init__.py &amp;&amp; test -f src/state/__init__.py &amp;&amp; test -f src/ingestion/__init__.py &amp;&amp; test -f src/quoting/__init__.py &amp;&amp; test -f src/sizing/__init__.py &amp;&amp; test -f src/config/__init__.py &amp;&amp; test -f tests/__init__.py &amp;&amp; test -f tests/test_smoke.py &amp;&amp; test -f scripts/.gitkeep &amp;&amp; test -f data/.gitkeep &amp;&amp; test -f models/.gitkeep &amp;&amp; test -f logs/.gitkeep &amp;&amp; ! test -f src/pricing/.gitkeep &amp;&amp; ! test -f src/config/.gitkeep &amp;&amp; ! grep -q '^uv\.lock$' .gitignore &amp;&amp; grep -q 'data/round_events' .gitignore &amp;&amp; uv run python -c "import src.pricing, src.state, src.ingestion, src.quoting, src.sizing, src.config" &amp;&amp; uv run mypy --strict src/pricing/ &amp;&amp; uv run ruff check . &amp;&amp; uv run pytest --collect-only -q</automated>
  </verify>
  <done>
    Every `src/*/` is a real Python package (has `__init__.py`, no leftover `.gitkeep`); `tests/__init__.py` and `tests/test_smoke.py` exist; `scripts/`, `data/`, `models/`, `logs/` have `.gitkeep` placeholders; `.gitignore` extended with `.uv/`, `models/dp_table.pkl`, `data/round_events*` (but NOT `uv.lock` — lock is committed); `uv run python -c "import src.pricing, ..."` succeeds; `uv run mypy --strict src/pricing/` exits 0; `uv run ruff check .` exits 0; `uv run pytest --collect-only` exits 0 (collects the `test_smoke` sentinel).
  </done>
</task>

</tasks>

<verification>
After both tasks complete, the following must ALL hold from a fresh shell at the repo root:

```bash
test -f pyproject.toml
test -f .python-version
test -d src/pricing && test -d src/state && test -d src/ingestion && test -d src/quoting && test -d src/sizing && test -d src/config
test -f src/pricing/__init__.py && test -f src/state/__init__.py && test -f src/ingestion/__init__.py && test -f src/quoting/__init__.py && test -f src/sizing/__init__.py && test -f src/config/__init__.py
test -f tests/__init__.py
test -f tests/test_smoke.py
! grep -q '^uv\.lock$' .gitignore   # uv.lock is COMMITTED, not gitignored
uv sync
uv run mypy --strict src/pricing/   # exit 0
uv run ruff check .                  # exit 0
uv run pytest --collect-only         # exit 0 (collects the test_smoke sentinel)
```

Echo `$?` after each `uv run` line — must be `0`. If any line fails, the plan is not done; do NOT advance to Plans 02 or 03.
</verification>

<success_criteria>
1. `pyproject.toml` declares Python 3.11, dev deps (pytest, pytest-cov, hypothesis, ruff, mypy), and `[tool.mypy]` strict override on `src.pricing.*`.
2. Every directory under `src/` is a real Python package (has `__init__.py`); no leftover `.gitkeep` files in those package dirs.
3. `tests/`, `scripts/`, `data/`, `models/`, `logs/` survive a clean clone (have `.gitkeep` or other tracked content); `tests/test_smoke.py` provides a passing sentinel test.
4. The four-command toolchain check (`uv sync`, `uv run mypy --strict src/pricing/`, `uv run ruff check .`, `uv run pytest --collect-only`) is green; pytest collects the `test_smoke` sentinel and exits 0.
5. `.gitignore` blocks `models/dp_table.pkl`, `data/round_events*`, `.uv/` in addition to existing rules; `data/half_win_rates.json` allow-list still respected (existing line 44 unchanged); `uv.lock` is COMMITTED (not gitignored) per uv application-project convention so Phase 6 deployment inherits a reproducible build.
</success_criteria>

<output>
After completion, create `.planning/phases/00-foundation/00-01-SUMMARY.md` covering:
- pyproject.toml contents (full text or diff vs. empty)
- list of files created and `.gitkeep` files removed (note: `tests/test_smoke.py` is created in Step F as the pytest sentinel; `uv.lock` is committed, not gitignored)
- exact `uv` / `mypy` / `ruff` / `pytest` versions resolved (paste `uv pip list`)
- the four verification command outputs
- any deviations from the action block (with rationale)
- explicit confirmation that downstream plans (02, 03) can rely on `from src.config import ...` resolving and `mypy --strict src/pricing/` continuing to pass when they add code
</output>
</output>
