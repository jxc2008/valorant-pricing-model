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

CAVEAT (per RESEARCH Pitfall 3 / 03-CONTEXT.md): the synthetic harness runs
in <1s real time, so all latency ms values are tiny — these gates ALWAYS
pass for the synthetic harness. The gate verifies the INSTRUMENTATION
captures the right numbers, not that production hits the budget under live
load. The real-broadcast latency gate is Phase 5 paper-trade.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from src.ingestion import Arbiter, PendingEvent, mono_ns, wall_time
from src.pricing.data import HalfRates
from src.pricing.live_theo import LiveTheoEngine
from src.pricing.round_conclusion import RoundConclusionLookup, _Cell
from src.state.match_state import MatchState

# (att=3, def=2, time_bucket=0, side="atk", map="Lotus") — synthetic cell key.
# time_bucket=0 corresponds to time_left_s in [0, 5) per TIME_BUCKET_WIDTH_S=5.
# We inject only if absent from the calibrated lookup so the
# test_post_plant_non_degenerate gate has a known >=1c shift to verify against.
_POST_PLANT_TEST_CELL_KEY: tuple[int, int, int, str, str] = (3, 2, 0, "atk", "Lotus")
_POST_PLANT_TEST_TIME_LEFT_S: float = 2.0  # int(2.0 / 5.0) == 0 == time_bucket


def _make_initial_state(match_id: str = "e2e-001") -> MatchState:
    """Initial mid-game state — symmetric BO3 setup, side_orient=atk."""
    return MatchState(
        match_id=match_id,
        team_a="A", team_b="B",
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


def _make_asymmetric_half_rates() -> HalfRates:
    """Asymmetric HalfRates so post-plant dispatch override produces measurable theo shift.

    Mirrors tests/pricing/test_live_theo_dispatch.py::_make_half_rates pattern:
    with symmetric rates the DP delivers v(state_after_a_wins) ==
    v(state_after_b_wins) by symmetry, so p * v + (1-p) * v == v for any p
    and the bomb_planted dispatch override (p_round != side baseline) becomes
    structurally INVISIBLE in theo_series. We use TeamA at 0.55 / TeamB at
    0.45 — strong enough to break symmetry, mild enough that v_root stays
    below CONVICTION_CLIP_HIGH=0.99 (and thus v_a vs v_b stay well-separated)
    so the dispatch override's `(p_post - p_internal) * (v_a - v_b)` shift
    crosses the 1c gate. TeamA-at-0.6 used in test_live_theo_dispatch.py is
    too aggressive at most state points — v_root saturates near 0.99 and
    v_a-v_b collapses to <0.03, shrinking the post-plant shift below 1c.
    """
    return HalfRates(
        team_rates={
            f"{t}|{m}|{s}": {
                "wins": (0.55 if t == "A" else 0.45) * 1000.0,
                "total": 1000.0,
                "rate": 0.55 if t == "A" else 0.45,
                "used_fallback": False,
            }
            for t in ("A", "B")
            for m in ("Lotus", "Bind", "Haven")
            for s in ("atk", "def")
        },
        league_rates={
            f"{m}|{s}": {"wins": 50.0, "total": 100.0, "rate": 0.5}
            for m in ("Lotus", "Bind", "Haven")
            for s in ("atk", "def")
        },
        overall_avg=0.5,
    )


def _make_engine() -> LiveTheoEngine:
    """Build LiveTheoEngine with the calibrated round_conclusion + asymmetric rates.

    If the calibrated lookup at models/round_conclusion.json doesn't contain the
    synthetic test key (3, 2, 0, atk, Lotus) — which it normally doesn't because
    time_bucket=0 maps to time_left_s in [0, 5) and live broadcasts rarely
    catch a defuse with the bomb still planted at < 5s remaining — inject a
    synthetic cell with high p_hat so the post-plant dispatch override
    produces a clear theo shift versus the between-round baseline.

    Production never calls this fallback (Phase 4 builds the engine via
    LiveTheoEngine(half_rates, RoundConclusionLookup.from_json(...)) directly).
    """
    rc = RoundConclusionLookup.from_json("models/round_conclusion.json")
    if _POST_PLANT_TEST_CELL_KEY not in rc.cells_full:
        rc.cells_full[_POST_PLANT_TEST_CELL_KEY] = _Cell(
            n=100, p_hat=0.95, parent_p=rc.side_baseline.get("atk", 0.5),
        )
    return LiveTheoEngine(half_rates=_make_asymmetric_half_rates(), round_conclusion=rc)


def _push_score_via_two_sources(arb: Arbiter, fields: dict[str, Any], t: float) -> None:
    """Helper: push score_change from rib.gg + OCR within 2s window → arbiter commits.

    Fields shape MUST match across sources for the arbiter's signature
    grouping (tuple(sorted(fields_proposed.items()))) to fire the >=2-source
    rule per DEC-006 v2 — see 03-04 SUMMARY decision on full {a_round, b_round}
    fields_proposed shape.
    """
    arb.score_changes.append(PendingEvent(
        source="ribgg", event_type="score_change",
        fields_proposed=fields, t_observed=t, t_ingested=mono_ns(),
    ))
    arb.score_changes.append(PendingEvent(
        source="ocr_score", event_type="score_change",
        fields_proposed=fields, t_observed=t + 0.1, t_ingested=mono_ns(),
    ))


def _push_bomb_plant(arb: Arbiter, t: float, att: int = 4, def_: int = 3) -> None:
    """Helper: push 1 OCR bomb_plant → arbiter soft-commits per DEC-006 v2."""
    arb.bomb_events.append(PendingEvent(
        source="ocr_bomb", event_type="bomb_plant",
        fields_proposed={
            "bomb_planted": True,
            "attackers_alive": att,
            "defenders_alive": def_,
            "time_left_s": 45.0,
        },
        t_observed=t, t_ingested=mono_ns(),
    ))


def _read_metrics(arb: Arbiter) -> list[dict[str, Any]]:
    if not arb.metrics_path.exists():
        return []
    return [
        json.loads(line)
        for line in arb.metrics_path.read_text().strip().splitlines()
        if line
    ]


def test_e2e_latency_p50(tmp_path: Path) -> None:
    """≥ 30 events through arbiter; p50 t_ingested → t_state_committed < 500ms; seq_id monotonic."""
    arb = Arbiter(
        _make_initial_state(),
        event_log_dir=tmp_path / "elog",
        metrics_log_dir=tmp_path / "metrics",
    )
    engine = _make_engine()

    # Drive 30 score_change events alternating a_round / b_round increments.
    # Each iteration: push 2 sources within window → tick() → commit → exercise engine.
    for i in range(30):
        if i % 2 == 0:
            fields: dict[str, Any] = {"a_round": arb.state.a_round + 1}
        else:
            fields = {"b_round": arb.state.b_round + 1}
        _push_score_via_two_sources(arb, fields, wall_time())
        arb.tick()
        # Exercise the engine on every commit to keep the call surface honest.
        _ = engine(arb.state)

    metrics = _read_metrics(arb)
    commit_lines = [m for m in metrics if m["seq_id"] is not None]
    assert len(commit_lines) >= 30, f"expected >=30 commits, got {len(commit_lines)}"

    # seq_id strictly monotonic (increment exactly +1 per commit).
    seq_ids = [m["seq_id"] for m in commit_lines]
    assert all(b == a + 1 for a, b in zip(seq_ids[:-1], seq_ids[1:], strict=True)), (
        f"seq_ids non-monotonic: {seq_ids[:10]}..."
    )

    # All 6 timestamps populated on every commit line (defensive — 03-03's
    # test_six_stage_populated covers a single event; this verifies 30+ event
    # consistency).
    six_keys = (
        "t_observed",
        "t_ingested",
        "t_arbited",
        "t_state_committed",
        "t_theo_computed",
        "t_quote_sent",
    )
    for m in commit_lines:
        for k in six_keys:
            assert k in m, f"missing {k} in {m}"
        # Phase 3 reservation: t_theo_computed and t_quote_sent are None.
        assert m["t_theo_computed"] is None
        assert m["t_quote_sent"] is None

    # p50 latency math: t_state_committed - t_ingested (both monotonic_ns ints,
    # NEVER subtract from t_observed which is wall_time()) per RESEARCH Pitfall 3.
    durations_ms = [
        (m["t_state_committed"] - m["t_ingested"]) / 1_000_000 for m in commit_lines
    ]
    p50 = statistics.median(durations_ms)
    assert p50 < 500.0, f"p50 latency {p50:.2f}ms exceeds 500ms budget"


def test_bomb_detect_p50(tmp_path: Path) -> None:
    """bomb_plant events specifically: p50 < 100ms (Phase 3's piece of PRD's 200ms budget).

    Phase 3 owns 100ms of the 200ms PRD bomb-detect → quote-pull budget;
    Phase 4 owns the remaining 100ms quote-cancel.
    """
    arb = Arbiter(
        _make_initial_state(),
        event_log_dir=tmp_path / "elog",
        metrics_log_dir=tmp_path / "metrics",
    )

    for _ in range(30):
        _push_bomb_plant(arb, wall_time())
        arb.tick()

    metrics = _read_metrics(arb)
    bomb_lines = [
        m for m in metrics
        if m.get("event_type") == "bomb_plant" and m["seq_id"] is not None
    ]
    assert len(bomb_lines) >= 30, f"expected >=30 bomb commits, got {len(bomb_lines)}"

    durations_ms = [
        (m["t_state_committed"] - m["t_ingested"]) / 1_000_000 for m in bomb_lines
    ]
    p50 = statistics.median(durations_ms)
    assert p50 < 100.0, (
        f"bomb-detect p50 {p50:.2f}ms exceeds 100ms budget "
        "(Phase 3 piece of 200ms PRD)"
    )


def test_post_plant_non_degenerate() -> None:
    """Bomb-planted state with populated cell shifts theo_series off baseline by >= 1c.

    Uses the calibrated cell at (3, 2, 0, atk, Lotus) injected by _make_engine
    when absent from the calibrated lookup. Asymmetric HalfRates (_make_engine)
    breaks DP symmetry so the dispatch override produces measurable shift —
    see _make_asymmetric_half_rates docstring + tests/pricing/
    test_live_theo_dispatch.py::_make_half_rates for the symmetric-rates trap.

    State construction: time_left_s=2.0 → int(2.0 / TIME_BUCKET_WIDTH_S=5.0) ==
    0, hitting the synthetic cell at time_bucket=0. attackers_alive=3,
    defenders_alive=2, side_orient="atk", map="Lotus" complete the cell key.
    """
    engine = _make_engine()
    base = _make_initial_state()
    # Land at a mid-game state where side_orient is still "atk" so the lookup
    # key matches. With a_round + b_round = 6 (< REGULATION_HALF=12), the
    # _RoundPFnImpl._effective_side resolution stays on "a_atk" (= "atk") for
    # the per-round p_round computation.
    base = base.with_update(a_round=3, b_round=3)
    bomb = base.with_update(
        bomb_planted=True,
        attackers_alive=3,
        defenders_alive=2,
        time_left_s=_POST_PLANT_TEST_TIME_LEFT_S,
    )

    out_base = engine(base)
    out_bomb = engine(bomb)
    delta = abs(out_bomb.theo_series - out_base.theo_series)
    assert delta >= 0.01, (
        f"theo shift only {delta:.4f} — post-plant cell not exercised, "
        "or theo identical (verify _make_engine cell injection + asymmetric HalfRates)"
    )
