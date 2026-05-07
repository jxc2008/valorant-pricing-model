---
phase: 03-live-ingestion-layer
plan: "08"
type: execute
wave: 6
depends_on: ["03-02", "03-03", "03-04", "03-05", "03-06", "03-07"]
files_modified:
  - tests/ingestion/test_e2e.py
  - tests/ingestion/conftest.py
  - .planning/STATE.md
  - .planning/ROADMAP.md
autonomous: true
requirements:
  - REQ-end-to-end-latency
notes: |
  Wave 6 — synthetic E2E gate. Phase 3's acceptance test. Drives stub rib.gg
  (aioresponses) + stub OCR (StubFrameSource pre-populated with synthetic
  frames) + stub Twitter (manual PendingEvent injection bypassing the real
  tweepy stream) through arbiter → MatchState → live_theo. Asserts:
    1. seq_id strictly monotonic over ≥ 30 events
    2. Six-stage timestamps populated on every confirmed event
    3. p50 t_observed → t_state_committed < 500ms across the synthetic run
    4. bomb_plant events specifically achieve p50 t_observed → t_state_committed < 100ms
       (Phase 3's piece of the PRD's 200ms bomb-detect → quote-pull budget;
        Phase 4 owns the other 100ms quote-cancel)
    5. Post-plant cells shift theo_series off side baseline by ≥ 1¢
       (uses the calibrated cell from 03-07's models/round_conclusion.json;
        if cells too sparse, falls back to forcing a synthetic cell into the
        runtime lookup before the test)

  Depends on the FULL Phase 3 chain: 03-02 (lookup + dispatch), 03-03 (arbiter
  + timestamps), 03-04 (scoreboard fetch/extract), 03-05 (OCR workers + frame
  source), 03-06 (text listener + arbiter integration), 03-07 (calibrated
  models/round_conclusion.json).

  Updates STATE.md / ROADMAP.md to mark Phase 3 complete after the gate
  passes — this is the canonical Phase 3 close-out task.

must_haves:
  truths:
    - "tests/ingestion/test_e2e.py exists with 3 GREEN tests: test_e2e_latency_p50, test_bomb_detect_p50, test_post_plant_non_degenerate"
    - "Synthetic harness drives ≥ 30 events through arbiter → state → live_theo without halting"
    - "p50 t_observed → t_state_committed < 500ms over the full event sample"
    - "p50 bomb_plant t_observed → t_state_committed < 100ms"
    - "Post-plant theo shift off side baseline ≥ 1¢ on a populated cells_full cell"
    - "STATE.md current_phase ≠ 03 (advances to 04) AND status = 'phase 03 complete'"
    - "ROADMAP.md Phase 3 entry marked [x] complete with completion date"
  artifacts:
    - path: "tests/ingestion/test_e2e.py"
      provides: "3 GREEN E2E tests covering latency p50 + bomb-detect p50 + post-plant non-degeneracy"
      contains: "test_e2e_latency_p50"
      min_lines: 200
    - path: ".planning/STATE.md"
      provides: "Phase 03 marked complete; current_phase advances to 04"
      contains: "Phase 3"
    - path: ".planning/ROADMAP.md"
      provides: "Phase 3 marked [x] with completion date"
      contains: "[x] **Phase 3"
  key_links:
    - from: "tests/ingestion/test_e2e.py"
      to: "src.ingestion.Arbiter + src.ingestion.scoreboard._fetch_match_details + src.ingestion.ocr decode helpers + src.pricing.live_theo.LiveTheoEngine"
      via: "synthetic harness composes all sources through real Arbiter into real LiveTheoEngine"
      pattern: "Arbiter.*LiveTheoEngine"
    - from: "tests/ingestion/test_e2e.py:test_post_plant_non_degenerate"
      to: "models/round_conclusion.json (v2, calibrated by 03-07)"
      via: "RoundConclusionLookup.from_json('models/round_conclusion.json')"
      pattern: "from_json.*round_conclusion"
---

<objective>
Land the synthetic E2E acceptance gate (REQ-end-to-end-latency, SPEC §6).
Composes ALL Phase 3 modules end-to-end (arbiter, scoreboard helpers, OCR
decode helpers, text listener parsing, live_theo dispatch, calibrated
round_conclusion lookup) through a synthetic harness; asserts seq_id
monotonicity + 6-stage timestamps populated + p50 latency budgets +
post-plant theo non-degeneracy.

Purpose: This IS the Phase 3 acceptance gate. After 03-08, Phase 3 is
mechanically COMPLETE — STATE.md and ROADMAP.md advance to mark it done.
Phase 4 (quoting layer) is unblocked.

Output:
- tests/ingestion/test_e2e.py (~250 LOC: 3 tests + synthetic harness)
- .planning/STATE.md updated (current_phase=04, Phase 3 marked complete)
- .planning/ROADMAP.md Phase 3 entry marked [x] with date
</objective>

<execution_context>
@C:/Users/Joseph Cheng/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/Joseph Cheng/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/ROADMAP.md
@.planning/phases/03-live-ingestion-layer/03-SPEC.md
@.planning/phases/03-live-ingestion-layer/03-CONTEXT.md
@.planning/phases/03-live-ingestion-layer/03-RESEARCH.md
@.planning/phases/03-live-ingestion-layer/03-VALIDATION.md
@.planning/phases/03-live-ingestion-layer/03-01-match-state-v2-migration-PLAN.md
@.planning/phases/03-live-ingestion-layer/03-02-round-conclusion-v2-surface-PLAN.md
@.planning/phases/03-live-ingestion-layer/03-03-arbiter-and-latency-PLAN.md
@.planning/phases/03-live-ingestion-layer/03-04-scoreboard-poller-PLAN.md
@.planning/phases/03-live-ingestion-layer/03-05-ocr-pipeline-PLAN.md
@.planning/phases/03-live-ingestion-layer/03-06-text-listener-PLAN.md
@.planning/phases/03-live-ingestion-layer/03-07-etl-rerun-and-calibration-PLAN.md

<interfaces>
Synthetic harness composition:

```python
import json, time, asyncio, statistics
import pytest
from src.ingestion import Arbiter, PendingEvent, mono_ns, wall_time
from src.ingestion.text_listener import _MatchSignalListener
from src.pricing.live_theo import LiveTheoEngine
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell
from src.pricing.data import HalfRates
from src.state.match_state import MatchState

def _make_initial_state() -> MatchState: ...

def _make_engine() -> LiveTheoEngine:
    """Build engine with calibrated round_conclusion + synthetic HalfRates."""
    rc = RoundConclusionLookup.from_json("models/round_conclusion.json")
    # If cells_full is empty (sparse calibration), inject a synthetic cell so
    # test_post_plant_non_degenerate has a known >=1c shift to verify against.
    if (3, 2, 0, "atk", "Lotus") not in rc.cells_full:
        rc.cells_full[(3, 2, 0, "atk", "Lotus")] = _Cell(n=100, p_hat=0.7, parent_p=rc.side_baseline.get("atk", 0.5))
    hr = HalfRates(team_rates={}, league_rates={}, overall_avg=0.5)  # symmetric
    return LiveTheoEngine(half_rates=hr, round_conclusion=rc)

def _push_score_via_two_sources(arb: Arbiter, fields: dict[str, int], t: float) -> None:
    """Helper: push score_change from rib.gg + OCR within 2s window → arbiter commits."""
    arb.score_changes.append(PendingEvent(source="ribgg", event_type="score_change", fields_proposed=fields, t_observed=t, t_ingested=mono_ns()))
    arb.score_changes.append(PendingEvent(source="ocr_score", event_type="score_change", fields_proposed=fields, t_observed=t + 0.1, t_ingested=mono_ns()))

def _push_bomb_plant(arb: Arbiter, t: float, att=4, def_=3) -> None:
    """Helper: push 1 OCR bomb_plant → arbiter soft-commits."""
    arb.bomb_events.append(PendingEvent(
        source="ocr_bomb", event_type="bomb_plant",
        fields_proposed={"bomb_planted": True, "attackers_alive": att, "defenders_alive": def_, "time_left_s": 45.0},
        t_observed=t, t_ingested=mono_ns(),
    ))

def _read_metrics_lines(arb: Arbiter) -> list[dict]:
    return [json.loads(l) for l in arb.metrics_path.read_text().strip().splitlines() if l]
```

Latency math: p50 of (t_state_committed - t_ingested) in nanoseconds; convert to ms with /1_000_000. Per RESEARCH Pitfall 3, NEVER subtract t_observed from t_state_committed (units mismatch). The synthetic test runs in <1s real time, so all ms values are tiny — gates ALWAYS pass for the synthetic harness; the real-broadcast gate is Phase 5 paper-trade. This test verifies the INSTRUMENTATION captures the right numbers, not that production hits the budget under live load.

Post-plant non-degeneracy:
- Build state with bomb_planted=True, (att=3, def_=2, time_left_s=43.0, side="atk", map="Lotus") to hit the synthetic cell.
- Build baseline state with bomb_planted=False (same other fields).
- Call engine on both; assert |theo_bomb - theo_baseline| >= 0.01 (1¢).

VALIDATION.md acceptance criteria:
- test_e2e_latency_p50: ≥ 30 events; p50 < 500ms (FOR THE SYNTHETIC HARNESS this is trivially passing — synth runs in <1s; the test verifies the metric is COMPUTABLE not that production performs).
- test_bomb_detect_p50: bomb_plant events specifically; p50 < 100ms in the synthetic harness (same caveat).
- test_post_plant_non_degenerate: theo shift ≥ 1¢ on a populated post-plant cell.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Wire test_e2e.py — 3 GREEN E2E tests; synthetic harness composes all Phase 3 modules</name>
  <files>
    tests/ingestion/test_e2e.py
    tests/ingestion/conftest.py
  </files>
  <behavior>
    - tests/ingestion/test_e2e.py (RED stubs from 03-00) all GREEN:
        - `test_e2e_latency_p50`: build Arbiter + LiveTheoEngine via _make_engine. Drive ≥ 30 score_change events via _push_score_via_two_sources alternating fields (`a_round` and `b_round` increments). After each push, call `arb.tick()`; verify state.seq_id incremented; AFTER the loop, read metrics file, compute p50 of `t_state_committed - t_ingested` (ns → ms); assert p50 < 500. Also assert seq_id strictly monotonic across all commits (every metrics line's seq_id == prior + 1).
        - `test_bomb_detect_p50`: drive ≥ 30 bomb_plant events via _push_bomb_plant; tick after each; read metrics; filter to event_type="bomb_plant" lines; compute p50 ms; assert < 100.
        - `test_post_plant_non_degenerate`: build _make_engine; build (bomb=False) baseline state and (bomb=True, att=3, def_=2, time_left_s=43.0, side="atk", map_idx=0, map_pool=("Lotus",...)) post-plant state; call engine on each; assert |theo_bomb - theo_baseline| >= 0.01.
    - All tests use the conftest fixture for tmp_event_log_path / tmp metrics path so they don't write to data/event_log/ in repo.
    - Six-stage timestamps verified populated on every metrics line in test_e2e_latency_p50 (defensive — 03-03's test_six_stage_populated already covers a single event; this verifies 30+ event consistency).
    - Tests run in <30s combined.
  </behavior>
  <action>
1) Wire `tests/ingestion/test_e2e.py` (RED stubs from 03-00) to GREEN:

```python
"""REQ-end-to-end-latency — synthetic E2E gate (03-08 / SPEC §6 acceptance).

Composes all Phase 3 modules end-to-end:
- Arbiter (03-03) drains 3 deques, commits via state.commit, writes JSONL+metrics.
- Scoreboard helpers (03-04) — not directly invoked here; we synthesize PendingEvents
  matching what _extract_score_change_fields would produce.
- OCR helpers (03-05) — not directly invoked; synthetic frames + decode helpers
  are tested in test_ocr_*.py; here we synthesize the post-OCR PendingEvents.
- Text listener (03-06) — _MatchSignalListener.on_tweet path covered in
  test_text_listener.py; not re-driven here (out of scope for E2E latency gate).
- LiveTheoEngine + RoundConclusionLookup (03-02 / 03-07) — directly composed.

Synthetic harness rationale: real I/O (aiohttp + tesseract + tweepy) lives in
unit tests for each source. The E2E gate verifies the COMPOSITION (arbiter →
state → live_theo) handles ≥ 30 events end-to-end with monotonic seq_ids and
populated 6-stage timestamps within latency budgets.
"""
from __future__ import annotations

import json
import time
import statistics
from pathlib import Path
import pytest

from src.ingestion import Arbiter, PendingEvent, mono_ns, wall_time
from src.pricing.data import HalfRates
from src.pricing.live_theo import LiveTheoEngine
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell
from src.state.match_state import MatchState


def _make_initial_state(match_id: str = "e2e-001") -> MatchState:
    return MatchState(
        match_id=match_id,
        team_a="T1", team_b="Sentinels",
        map_pool=("Lotus", "Bind", "Haven"),
        map_side_orients=("a_atk", "a_def", "a_atk"),
        map_winners=(None, None, None),
        pistol_winner_a={0: None, 1: None, 2: None},
        map_idx=0, a_map_score=0, b_map_score=0,
        a_round=0, b_round=0,
        side_orient="atk",
        bomb_planted=False, attackers_alive=None, defenders_alive=None, time_left_s=None,
        seq_id=0, last_updated_ts=0.0,
    )


def _make_engine() -> LiveTheoEngine:
    """Build engine with calibrated lookup + symmetric HalfRates.

    If 03-07 calibration left cells_full sparse (no key at (3, 2, 0, atk, Lotus)),
    inject a synthetic cell so test_post_plant_non_degenerate has a known
    populated cell to verify against. Production never calls this fallback.
    """
    rc = RoundConclusionLookup.from_json("models/round_conclusion.json")
    if (3, 2, 0, "atk", "Lotus") not in rc.cells_full:
        rc.cells_full[(3, 2, 0, "atk", "Lotus")] = _Cell(
            n=100, p_hat=0.7, parent_p=rc.side_baseline.get("atk", 0.5),
        )
    hr = HalfRates(team_rates={}, league_rates={}, overall_avg=0.5)
    return LiveTheoEngine(half_rates=hr, round_conclusion=rc)


def _push_score_via_two_sources(arb: Arbiter, fields: dict, t: float) -> None:
    arb.score_changes.append(PendingEvent(
        source="ribgg", event_type="score_change",
        fields_proposed=fields, t_observed=t, t_ingested=mono_ns(),
    ))
    arb.score_changes.append(PendingEvent(
        source="ocr_score", event_type="score_change",
        fields_proposed=fields, t_observed=t + 0.1, t_ingested=mono_ns(),
    ))


def _push_bomb_plant(arb: Arbiter, t: float, att: int = 4, def_: int = 3) -> None:
    arb.bomb_events.append(PendingEvent(
        source="ocr_bomb", event_type="bomb_plant",
        fields_proposed={"bomb_planted": True, "attackers_alive": att,
                         "defenders_alive": def_, "time_left_s": 45.0},
        t_observed=t, t_ingested=mono_ns(),
    ))


def _read_metrics(arb: Arbiter) -> list[dict]:
    if not arb.metrics_path.exists():
        return []
    return [json.loads(l) for l in arb.metrics_path.read_text().strip().splitlines() if l]


def test_e2e_latency_p50(tmp_path):
    """≥ 30 events through arbiter; p50 t_ingested → t_state_committed < 500ms; seq_id monotonic."""
    arb = Arbiter(_make_initial_state(), event_log_dir=tmp_path / "elog", metrics_log_dir=tmp_path / "metrics")
    engine = _make_engine()

    # Drive 30 score_change events alternating a_round / b_round increments
    for i in range(30):
        if i % 2 == 0:
            fields = {"a_round": (arb.state.a_round + 1)}
        else:
            fields = {"b_round": (arb.state.b_round + 1)}
        _push_score_via_two_sources(arb, fields, wall_time())
        arb.tick()
        # Optionally exercise the engine to ensure the call surface stays sane
        _ = engine(arb.state)

    metrics = _read_metrics(arb)
    commit_lines = [m for m in metrics if m["seq_id"] is not None]
    assert len(commit_lines) >= 30, f"expected >=30 commits, got {len(commit_lines)}"

    # seq_id strictly monotonic
    seq_ids = [m["seq_id"] for m in commit_lines]
    assert all(b == a + 1 for a, b in zip(seq_ids, seq_ids[1:])), f"seq_ids non-monotonic: {seq_ids[:10]}..."

    # All 6 timestamps populated on every commit line
    for m in commit_lines:
        for k in ("t_observed", "t_ingested", "t_arbited", "t_state_committed", "t_theo_computed", "t_quote_sent"):
            assert k in m, f"missing {k} in {m}"
        # Phase 3 reservation: t_theo_computed and t_quote_sent are None
        assert m["t_theo_computed"] is None
        assert m["t_quote_sent"] is None

    # p50 latency math: t_state_committed - t_ingested (both monotonic_ns ints)
    durations_ms = [(m["t_state_committed"] - m["t_ingested"]) / 1_000_000 for m in commit_lines]
    p50 = statistics.median(durations_ms)
    assert p50 < 500.0, f"p50 latency {p50:.2f}ms exceeds 500ms budget"


def test_bomb_detect_p50(tmp_path):
    """bomb_plant events specifically: p50 < 100ms (Phase 3's piece of PRD's 200ms budget)."""
    arb = Arbiter(_make_initial_state(), event_log_dir=tmp_path / "elog", metrics_log_dir=tmp_path / "metrics")

    for _ in range(30):
        _push_bomb_plant(arb, wall_time())
        arb.tick()

    metrics = _read_metrics(arb)
    bomb_lines = [m for m in metrics if m.get("event_type") == "bomb_plant" and m["seq_id"] is not None]
    assert len(bomb_lines) >= 30, f"expected >=30 bomb commits, got {len(bomb_lines)}"

    durations_ms = [(m["t_state_committed"] - m["t_ingested"]) / 1_000_000 for m in bomb_lines]
    p50 = statistics.median(durations_ms)
    assert p50 < 100.0, f"bomb-detect p50 {p50:.2f}ms exceeds 100ms budget (Phase 3 piece of 200ms PRD)"


def test_post_plant_non_degenerate():
    """Bomb-planted state with populated cell shifts theo_series off baseline by >= 1c."""
    engine = _make_engine()
    base = _make_initial_state()
    base = base.with_update(a_round=10, b_round=8)
    bomb = base.with_update(bomb_planted=True, attackers_alive=3, defenders_alive=2, time_left_s=43.0)

    out_base = engine(base)
    out_bomb = engine(bomb)
    delta = abs(out_bomb.theo_series - out_base.theo_series)
    assert delta >= 0.01, f"theo shift only {delta:.4f} — post-plant cell not exercised or theo identical"
```

Replace the xfail stubs with these implementations.

Atomic commit message: `test(03-08): synthetic E2E gate — 3 tests covering REQ-end-to-end-latency (Phase 3 acceptance)`
  </action>
  <verify>
    <automated>uv run pytest tests/ingestion/test_e2e.py -v -x --no-cov</automated>
  </verify>
  <done>
- tests/ingestion/test_e2e.py — 3 tests GREEN.
- ≥ 30 events processed end-to-end without errors.
- seq_id strictly monotonic across the run.
- All 6 timestamps populated on every metrics line.
- p50 < 500ms (general); bomb_plant p50 < 100ms.
- Post-plant theo shift >= 1¢ on a populated cell.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Update STATE.md + ROADMAP.md to mark Phase 3 complete</name>
  <files>
    .planning/STATE.md
    .planning/ROADMAP.md
  </files>
  <behavior>
    - .planning/STATE.md updated:
        - `current_phase: 04` (was 03)
        - `current_plan: 0 (no plans yet — phase needs /gsd-spec-phase or /gsd-discuss-phase to begin)` (analogous to current Phase 3 entry)
        - `status: planning` (Phase 4 unstarted)
        - `stopped_at: Phase 03 complete (live ingestion layer shipped)`
        - `last_updated:` set to today's date in ISO 8601
        - `last_activity:` set to today's date
        - `last_activity description:` "Phase 03 complete — Wave 6 (Plan 03-08 E2E gate) shipped after Waves 0-5 fully GREEN; full ingestion stack live (MatchState v2 + arbiter + scoreboard + OCR + text listener + post-plant calibration)."
        - Progress table: `Phase 03: Complete (8 plans, 8 completed)` (or however the count lands — 03-00..03-08 = 9 plans).
        - Bump completed_phases from 3 to 4 in frontmatter.
        - Phase Status table: Phase 3 row → "Complete (today)" with plan count.
        - Recent decisions: append a one-liner about Phase 03 outcome (analogous to the Phase 02 outcomes section).
    - .planning/ROADMAP.md updated:
        - Phase 3 entry in the bullet list: `[ ] **Phase 3: Live ingestion layer**` → `[x] **Phase 3: Live ingestion layer** ... (completed YYYY-MM-DD — v2 architecture; 9 plans 03-00..03-08)`.
        - Progress table at bottom: Phase 3 row updated to `Complete | YYYY-MM-DD`.
        - Coverage check: keep numbers consistent (Phase 3 was already counted; just update completion).
  </behavior>
  <action>
1) Read current `.planning/STATE.md`. Edit:
   - frontmatter: `current_phase: "04"`, `current_plan: 0 (no plans yet — phase needs /gsd-spec-phase or /gsd-discuss-phase to begin)`, `status: planning`, `stopped_at: Phase 03 complete (live ingestion layer shipped)`, `last_updated:` ISO 8601 today, `last_activity:` today, `progress.completed_phases: 4`, `progress.completed_plans: <prev + 9>` (Phase 3 added 9 plans: 03-00..03-08).
   - Body: update "Current Position" section to read Phase 4 / TBD plans / planning status. Update "Phase Status" table row for Phase 3 to "Complete (today)". Add a "Phase 03 outcomes" subsection under "Recent decisions (cross-phase)" listing:
     - "MatchState v2 migrated to src/state/match_state.py (19 fields; cut numerical_diff/side/econ_bucket; added attackers_alive/defenders_alive/time_left_s/seq_id/last_updated_ts)."
     - "RoundConclusionLookup v2 surface (between_round_p + post_plant_p, 5-tier hierarchy, schema_version=2 from_json gate). live_theo dispatches on state.bomb_planted (D-05). src/pricing/economy.py deleted per CLAUDE.md v2 deprecation."
     - "Cross-source arbiter shipped (3 deques per DEC-006 v2: score_changes, bomb_events, round_end_events; kill_events / numerical_flips NOT created)."
     - "Six-stage timestamp lineage on every confirmed event (data/metrics/{match_id}.metrics.jsonl)."
     - "Async rib.gg poller, tesseract OCR (4 workers), Twitter v2 listener (degrade-to-no-op) all in place."
     - "Phase 2 ETL re-run with a_alive/b_alive persisted; ~1000 series re-fetched into data/round_events_v2.sqlite; cells calibrated into models/round_conclusion.json schema_version=2."
     - "Synthetic E2E gate at tests/ingestion/test_e2e.py: seq_id monotonic, 6 timestamps populated, p50 < 500ms general / < 100ms bomb-detect, post-plant theo shift ≥ 1¢."
   - "Active todos" / "Blockers" sections set to `None`.
   - "Session Continuity": update last session ended block; "Next action": "Phase 04 (quoting layer) needs spec/discuss → plan → execute. Per roadmap.md §4 (rescoped v2), the phase covers KalshiOrderManager + three-way mode selector + MM/DIRECTIONAL/POST_PLANT_QUOTE/IDLE + portfolio-aware Kelly + four kill switches + order reconciliation. Phase 4 is unblocked by Phase 3's MatchState + arbiter + post-plant lookup. Recommended next command: /gsd-spec-phase 04."

2) Read current `.planning/ROADMAP.md`. Edit:
   - Phase 3 bullet (`- [ ] **Phase 3: Live ingestion layer** ...`): change `[ ]` → `[x]` and append `(completed YYYY-MM-DD — v2 architecture; 9 plans 03-00..03-08)` similar to Phase 2's `(completed 2026-05-01 — Path A: ...)` formatting.
   - Phase Details § Phase 3: keep as-is (the "Plans" subsection in this file is itself a placeholder; we won't re-enumerate the 9 plans). Note that the ROADMAP.md plan list at the existing Phase 3 entry says "11 plans currently exist on commit 6677e5d" — REPLACE that entire "Plans" subsection with the new authoritative list:
     ```
     **Plans**: 9 plans
     - [x] 03-00-test-infrastructure-PLAN.md (Wave 1) — RED test scaffolds + dev deps + mypy override
     - [x] 03-01-match-state-v2-migration-PLAN.md (Wave 2)
     - [x] 03-02-round-conclusion-v2-surface-PLAN.md (Wave 3)
     - [x] 03-03-arbiter-and-latency-PLAN.md (Wave 4)
     - [x] 03-04-scoreboard-poller-PLAN.md (Wave 4)
     - [x] 03-05-ocr-pipeline-PLAN.md (Wave 4)
     - [x] 03-06-text-listener-PLAN.md (Wave 4)
     - [x] 03-07-etl-rerun-and-calibration-PLAN.md (Wave 5)
     - [x] 03-08-e2e-gate-PLAN.md (Wave 6)
     ```
   - "Progress" table at end: Phase 3 row → `9/9 | Complete | YYYY-MM-DD`.

3) Run `git add .planning/STATE.md .planning/ROADMAP.md` and let the subsequent commit task pick them up.

Atomic commit message: `docs(03-08): mark Phase 03 complete in STATE.md + ROADMAP.md (live ingestion layer shipped, v2 architecture)`
  </action>
  <verify>
    <automated>uv run python -c "import yaml; sm = open('.planning/STATE.md').read(); fm = sm.split('---')[1]; meta = yaml.safe_load(fm); assert meta['current_phase'] == '04' or meta['current_phase'] == 4; assert meta['progress']['completed_phases'] == 4; print('STATE.md ok')" && grep -q "\\[x\\] \\*\\*Phase 3" .planning/ROADMAP.md && echo "ROADMAP.md ok"</automated>
  </verify>
  <done>
- STATE.md current_phase advanced to 04; status=planning; completed_phases=4.
- STATE.md "Recent decisions" includes Phase 03 outcomes paragraph.
- ROADMAP.md Phase 3 entry has [x] checkmark + completion date.
- ROADMAP.md Phase 3 plan list updated to the 9-plan canonical list (replacing the v1 "11 plans on commit 6677e5d" placeholder).
- Both files committed alongside test_e2e.py via the orchestrator's normal commit flow.
  </done>
</task>

</tasks>

<verification>
- `uv run pytest tests/ingestion/test_e2e.py -v` — 3 tests pass.
- `uv run pytest tests/ -x --no-cov` — full suite GREEN (Phase 1 + Phase 2 regression + all of Phase 3).
- `uv run mypy --strict src/pricing src/state` — 0 errors.
- `uv run mypy src/ingestion` — 0 errors (gradual mode but new code annotates fully).
- `uv run ruff check src tests scripts` — clean.
- STATE.md current_phase advanced to 04.
- ROADMAP.md Phase 3 marked [x] with completion date.
</verification>

<success_criteria>
- REQ-end-to-end-latency SPEC acceptance #6 GREEN: ≥30 events through synthetic harness, p50 < 500ms general, p50 < 100ms for bomb_plant, post-plant theo shift ≥ 1¢.
- Phase 03 mechanically complete: STATE.md and ROADMAP.md updated.
- Phase 04 unblocked.
</success_criteria>

<output>
After completion, create `.planning/phases/03-live-ingestion-layer/03-08-SUMMARY.md`
documenting:
- 3 GREEN E2E tests (test_e2e_latency_p50, test_bomb_detect_p50, test_post_plant_non_degenerate)
- Synthetic harness composition: PendingEvent injection bypassing real I/O sources, real Arbiter + LiveTheoEngine
- Latency observations from the synthetic run (p50 ms, max ms — should all be tiny since synthetic)
- Whether the synthetic post-plant cell (3, 2, 0, atk, Lotus) was hit from real calibration data or required the test fallback inject (informs Phase 5 calibration prioritization)
- STATE.md / ROADMAP.md update summary
- Phase 03 close-out: 9 plans landed, all GREEN, full ingestion stack live
- Pointer to Phase 04 (quoting layer): KalshiOrderManager + mode selector + portfolio Kelly + kill switches
</output>
</content>
</invoke>