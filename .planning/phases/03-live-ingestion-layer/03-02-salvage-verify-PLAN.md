---
id: 03-02-salvage-verify
phase: 03
plan: 2
type: execute
wave: 0
depends_on: []
files_modified:
  - tests/ingestion/test_salvage_present.py
autonomous: false
requirements:
  - REQ-scoreboard-polling
  - REQ-ocr-pipeline
user_setup:
  - service: thunderedge-sibling-repo
    why: "Three salvage files (vlr_scraper.py, rib_scraper.py, vision_parser.py) live in the sibling thunderedge/worktrees/market-maker/ repo and must be copied into reference/ before Wave 2 ports them. SPEC.md and CONTEXT.md both forbid the planner/agent from cross-repo file access; the operator MUST do the copy."
    env_vars: []
    dashboard_config:
      - task: "Copy 3 files into reference/"
        location: "Local filesystem — operator action"
---

<objective>
Wave 0 checkpoint plan — verify the three salvage files have been copied from the sibling `thunderedge/` repo into this repo's `reference/` directory before Wave 2 plans (03-04 scoreboard, 03-05 OCR) attempt to port from them. The plan does NOT attempt the copy itself (per SPEC.md "User performs the copy").

Purpose: SPEC §boundaries.salvage-discipline mandates "copy `vlr_scraper.py` / `rib_scraper.py` / `vision_parser.py` from `thunderedge/` into `reference/` first, then port. (User performs the copy)". This plan provides the operator-facing checkpoint that gates Wave 2 — without these three files, the OCR plan (03-05) and scoreboard plan (03-04) cannot apply the RESEARCH §Salvage-Port Delta Checklist (lines 583-606).

Output: a single Wave-0 test asserting all three salvage files are present in `reference/`. The test is the gate — Wave 2 plans depend on this plan being GREEN.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/03-live-ingestion-layer/03-SPEC.md
@.planning/phases/03-live-ingestion-layer/03-CONTEXT.md
@.planning/phases/03-live-ingestion-layer/03-RESEARCH.md
@.planning/phases/03-live-ingestion-layer/03-PATTERNS.md
@.planning/phases/03-live-ingestion-layer/03-VALIDATION.md
@reference/
@CLAUDE.md
</context>

<tasks>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 1: OPERATOR — Copy three salvage files from thunderedge/ into reference/</name>
  <what-built>Pre-checkpoint: this plan WILL NOT attempt to copy the files. The operator must do this manually because the source files live in a sibling repo (`thunderedge/worktrees/market-maker/`) outside this repo's working tree, and SPEC.md + CONTEXT.md (line 114) both lock the discipline as "user does the copy."</what-built>
  <how-to-verify>
Operator action required (one-time, before Wave 2 starts):

1. Locate the three source files in the sibling `thunderedge/` repo. Likely paths (verify in your local checkout):
   - `thunderedge/worktrees/market-maker/<some_subdir>/vlr_scraper.py`
   - `thunderedge/worktrees/market-maker/<some_subdir>/rib_scraper.py`
   - `thunderedge/worktrees/market-maker/<some_subdir>/vision_parser.py`

2. Copy them VERBATIM (do NOT edit) into this repo's `reference/` directory:
   ```powershell
   # PowerShell (Windows):
   $src = "C:\path\to\thunderedge\worktrees\market-maker"
   Copy-Item "$src\vlr_scraper.py" "reference\vlr_scraper.py"
   Copy-Item "$src\rib_scraper.py" "reference\rib_scraper.py"
   Copy-Item "$src\vision_parser.py" "reference\vision_parser.py"
   ```
   ```bash
   # Bash (cross-platform):
   src=/path/to/thunderedge/worktrees/market-maker
   cp "$src/vlr_scraper.py" reference/vlr_scraper.py
   cp "$src/rib_scraper.py" reference/rib_scraper.py
   cp "$src/vision_parser.py" reference/vision_parser.py
   ```

3. Stage them in git:
   ```bash
   git add reference/vlr_scraper.py reference/rib_scraper.py reference/vision_parser.py
   ```
   They will be COMMITTED as read-only salvage (the existing `pyproject.toml:39` ruff exclude block already excludes `reference/` so they bypass lint; mypy excludes them too via the `files = ["src", "tests"]` scope on line 90).

4. Confirm the three files are present and non-empty:
   ```bash
   ls -la reference/vlr_scraper.py reference/rib_scraper.py reference/vision_parser.py
   ```
   Each should be > 1 KB (these are real implementation files from thunderedge, not stubs).

5. Reply "approved" to this checkpoint. The agent will then run Task 2 (the verification test) and commit it.

If you cannot locate the sibling repo OR the three files do not exist there: STOP. Reply with the error and we will redesign the salvage strategy (e.g., reconstruct from git history, fetch via `git archive`, or downgrade Phase 3 to write `src/ingestion/scoreboard.py` + `src/ingestion/ocr.py` from scratch — RESEARCH §Pattern 2/3/4 supports both paths).
  </how-to-verify>
  <resume-signal>Type "approved" once `ls reference/vlr_scraper.py reference/rib_scraper.py reference/vision_parser.py` shows all three files present and non-empty. OR type "blocked" with details if the files cannot be located.</resume-signal>
</task>

<task type="auto">
  <name>Task 2: Add tests/ingestion/test_salvage_present.py asserting the 3 files exist</name>
  <files>tests/ingestion/test_salvage_present.py</files>
  <read_first>
    - reference/ (run `ls reference/` and confirm the 3 files appear)
    - .planning/phases/03-live-ingestion-layer/03-SPEC.md §boundaries (line 87 — salvage discipline)
    - .planning/phases/03-live-ingestion-layer/03-CONTEXT.md `<canonical_refs>` lines 110-114 (read-only salvage targets)
    - .planning/phases/03-live-ingestion-layer/03-PATTERNS.md §Salvage-via-reference-then-port (lines 762-768)
  </read_first>
  <action>
Create `tests/ingestion/test_salvage_present.py`:

```python
"""Wave 0 gate: assert the three Phase 3 salvage files exist in reference/.

SPEC.md §boundaries.salvage-discipline (line 87) and CONTEXT.md `<canonical_refs>`
(lines 110-114) both lock the discipline: vlr_scraper.py, rib_scraper.py, and
vision_parser.py MUST be copied verbatim from the sibling thunderedge/ repo
into this repo's reference/ directory BEFORE Wave 2 plans port them into
src/ingestion/. The operator does the copy (cross-repo file access is out of
scope for the planner/agent); this test is the gate.

If this test FAILS: stop Wave 2; the operator did not complete the salvage
copy step. See the resume-signal in 03-02-salvage-verify-PLAN.md.

Sources
-------
- 03-SPEC.md §boundaries (line 87)
- 03-CONTEXT.md `<canonical_refs>` (lines 110-114)
- 03-PATTERNS.md §Salvage-via-reference-then-port (lines 762-768)
- 03-VALIDATION.md Manual-Only Verifications (lines 96-97)
"""
from __future__ import annotations

from pathlib import Path

import pytest

REFERENCE_DIR: Path = Path(__file__).resolve().parents[2] / "reference"

SALVAGE_FILES: tuple[str, ...] = (
    "vlr_scraper.py",
    "rib_scraper.py",
    "vision_parser.py",
)
"""Three Phase 3 salvage files mandated by SPEC §boundaries.

The Wave 2 source plans port these into src/ingestion/:
    rib_scraper.py + vlr_scraper.py -> src/ingestion/scoreboard.py
    vision_parser.py                 -> src/ingestion/ocr.py
applying the 8-item delta checklist in 03-RESEARCH.md §Salvage-Port Delta (lines 583-606).
"""

MIN_SALVAGE_BYTES: int = 1024
"""Sanity floor — these are real Python modules from thunderedge/, not stubs.
A file shorter than 1 KB suggests an empty placeholder slipped through."""


@pytest.mark.parametrize("name", SALVAGE_FILES)
def test_salvage_file_present_and_nonempty(name: str) -> None:
    """REQ-scoreboard-polling + REQ-ocr-pipeline gate: salvage files staged."""
    path = REFERENCE_DIR / name
    assert path.exists(), (
        f"Phase 3 salvage gate FAIL: {path} missing. "
        f"Operator must copy from thunderedge/worktrees/market-maker/ per "
        f"03-SPEC.md §boundaries.salvage-discipline. See "
        f".planning/phases/03-live-ingestion-layer/03-02-salvage-verify-PLAN.md."
    )
    size = path.stat().st_size
    assert size >= MIN_SALVAGE_BYTES, (
        f"Phase 3 salvage gate FAIL: {path} is suspiciously small "
        f"({size} bytes < {MIN_SALVAGE_BYTES} byte floor). "
        f"Likely a stub was committed by mistake; replace with the real "
        f"thunderedge/ source."
    )


def test_existing_salvage_files_still_present() -> None:
    """Regression: the 4 Phase 1/2/4 salvage files (already committed) stay put.

    Listed for completeness so a sloppy git operation in reference/ surfaces here
    as a single test failure instead of breaking pricing imports later.
    """
    legacy = (
        "fair_value.py",
        "market_maker.py",
        "odds_utils.py",
        "theo_engine.py",
    )
    for name in legacy:
        assert (REFERENCE_DIR / name).exists(), (
            f"Pre-existing salvage file {name} missing — git accident in reference/?"
        )
```

This test is in `tests/ingestion/` so it lives with the Phase 3 test suite. It is parametrized over the 3 salvage filenames (one assertion per file for clearer failure output).

The test runs FAST (3 stat calls) and goes into the quick-feedback band (`pytest tests/ -x -k "not benchmark and not e2e"`). It will FAIL until the operator completes Task 1.
  </action>
  <verify>
    <automated>pytest tests/ingestion/test_salvage_present.py -x</automated>
  </verify>
  <done>tests/ingestion/test_salvage_present.py exists; all 3 parametrized variants + the legacy-regression test PASS (which proves the operator completed Task 1 successfully); the test is included in the default `pytest tests/` run; ruff + mypy clean.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| sibling repo -> this repo | Operator manually copies 3 files from `thunderedge/` outside this repo's git tree. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-03-02-01 | T (Tampering) | salvage source files | mitigate | Files are committed as-is to `reference/` after the operator copy; subsequent Wave 2 plans READ them as shape templates (not as importable modules). The 1 KB floor in `MIN_SALVAGE_BYTES` rejects accidental stub commits. |
| T-03-02-02 | I (Information disclosure) | salvage files may contain hardcoded credentials from the sibling repo | mitigate | Operator instructed in Task 1 to copy verbatim with the expectation that `reference/` is reviewed before commit. The Wave 2 ports apply the salvage-port delta checklist (RESEARCH lines 583-606) which explicitly drops hardcoded secrets, replaces `print()`, and removes module-level state — that step also gates against accidentally pushing credentials past the salvage layer. |
| T-03-02-03 | E (Elevation of privilege) | reference/ files might be `import`-able | accept | `pyproject.toml:39` already adds `reference/` to ruff's `extend-exclude`; the `[tool.mypy]` `files = ["src", "tests"]` scope on line 90 already keeps mypy from scanning them. Python CAN import them via `import reference.vlr_scraper`, but no production code in `src/` does so (Wave 2 ports patterns by hand-reading, not importing). |
</threat_model>

<verification>
- `tests/ingestion/test_salvage_present.py` PASSES (4 assertions: 3 parametrized salvage + 1 legacy-regression).
- All 3 files appear in `git ls-files reference/` output.
- File sizes meet the `MIN_SALVAGE_BYTES = 1024` floor.
- Phase 1 + 2 regression: `pytest tests/ -x -k "not benchmark and not e2e"` GREEN.
</verification>

<success_criteria>
Wave 0 salvage gate is COMPLETE when:

1. `reference/vlr_scraper.py`, `reference/rib_scraper.py`, `reference/vision_parser.py` all exist and are >= 1 KB.
2. All three are committed to git (`git ls-files reference/` shows them).
3. `pytest tests/ingestion/test_salvage_present.py -x` PASSES.
4. The 4 legacy salvage files (`fair_value.py`, `market_maker.py`, `odds_utils.py`, `theo_engine.py`) are still present (no accidental deletion).
5. Wave 2 source plans (03-04 scoreboard, 03-05 OCR) can begin.
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-02-SUMMARY.md`:

```markdown
# 03-02 SUMMARY — salvage gate

**Status:** complete
**Wave:** 0 (checkpoint plan)
**Files modified:** tests/ingestion/test_salvage_present.py (NEW); reference/ now contains 3 new salvage files (operator-copied)

## Salvage files staged
- reference/vlr_scraper.py    — {bytes} bytes  (port -> src/ingestion/scoreboard.py via 03-04)
- reference/rib_scraper.py    — {bytes} bytes  (port -> src/ingestion/scoreboard.py via 03-04)
- reference/vision_parser.py  — {bytes} bytes  (port -> src/ingestion/ocr.py via 03-05)

## Wave 2 unblocked
- 03-04 (scoreboard) and 03-05 (ocr) can now proceed.
```
</output>
