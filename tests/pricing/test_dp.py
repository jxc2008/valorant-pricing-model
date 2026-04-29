"""Property tests for src.pricing.dp — REQ-bo3-dp-engine + REQ-ot-handling.

Verifies acceptance criteria from roadmap §1.1, §1.4, §5.1:
  - DP value in [0, 1] for any reachable state (range invariant).
  - Symmetric inputs -> DP value == p^2(3-2p) (closed form from fair_value).
  - OT hard-stop: DP returns coinflip leaf at total=24, never iterates past.
  - Map terminals (a_map_score>=2 -> 1.0, b_map_score>=2 -> 0.0).
  - No range(26) loop or constant-p1/p2 dispatch (regression vs PRD §12.2 #3, #5).
  - `_advance_to_next_map` requires explicit `next_side_orient` arg; no
    hardcoded 'a_atk' literal (Blocker #3 / Warning #9 — regression vs PRD §12.2 #6).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

# Importing the salvage closed form via reference/ — confirm reference is on
# sys.path (Phase 0 pyproject.toml `[tool.hatch.build] sources` includes it).
from reference.fair_value import _bo3_series_prob
from src.config.constants import GUN_WIN_RATE
from src.pricing.dp import (
    BO3State,
    _advance_round,
    _series_value_cached,
    series_value,
)
from src.pricing.round_types import round_p_for_round

# --------------------------------------------------------------------------- #
# Test helpers — RoundPFn closures with explicit side-orient accessors        #
# --------------------------------------------------------------------------- #


class _ConstantRoundPFn:
    """Test fixture satisfying the RoundPFn Protocol with constant p, all-a_atk maps."""

    def __init__(
        self,
        p: float,
        side_orients: tuple[str, ...] = ("a_atk", "a_atk", "a_atk"),
    ) -> None:
        self._p = p
        self._sides = side_orients

    def __call__(self, state: BO3State) -> float:
        return self._p

    def next_side_orient_for(self, map_idx: int) -> str:
        if map_idx >= len(self._sides):
            return "a_atk"  # past series-clinch; never read but defensive
        return self._sides[map_idx]


def _root() -> BO3State:
    """Canonical 3-map root state used across tests."""
    return BO3State(
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(None, None, None),
    )


# --------------------------------------------------------------------------- #
# Test fixtures for the round_p_for_round dispatch (CR-05 regression)         #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _FakeMatchState:
    """Minimal MatchState shape required by round_p_for_round.

    The anti-eco branch in round_types.round_p_for_round (lines 146-153) does
    not read MatchState.team_a/team_b, but the gunround/pistol branches do. We
    only need anti-eco coverage for CR-05, but keep team_a/team_b for safety.
    """

    team_a: str = "TeamA"
    team_b: str = "TeamB"


class _FakeHalfRates:
    """Minimal HalfRates Protocol implementation. Anti-eco branch never reads
    these — returning 0.5 / None is sufficient for the CR-05 regression.
    """

    def team(self, team: str, map_name: str, side: str) -> float:
        return 0.5

    def team_entry(
        self, team: str, map_name: str, side: str
    ) -> dict[str, Any] | None:
        return None


# --------------------------------------------------------------------------- #
# 1. Range invariant                                                          #
# --------------------------------------------------------------------------- #


@given(p=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
@settings(max_examples=50, deadline=None)
def test_dp_value_in_unit_interval(p: float) -> None:
    """REQ-bo3-dp-engine acceptance: DP value in [0, 1] for any reachable state."""
    val = series_value(_root(), _ConstantRoundPFn(p))
    assert 0.0 <= val <= 1.0
    assert not math.isnan(val)


# --------------------------------------------------------------------------- #
# 2. Symmetric input matches p^2(3-2p) closed form                            #
# --------------------------------------------------------------------------- #


@given(p=st.floats(min_value=0.05, max_value=0.95))
@settings(max_examples=50, deadline=None)
def test_dp_symmetric_input_matches_closed_form(p: float) -> None:
    """REQ-bo3-dp-engine acceptance: under symmetric (state-independent) round_p,
    the BO3 series value equals ``_bo3_series_prob(per_map_prob)`` where
    per_map_prob is itself the DP value at a single-map decider root.

    Rationale: ``reference.fair_value._bo3_series_prob`` consumes a per-MAP win
    probability, but the DP consumes per-ROUND win probability. The two are
    related by the within-map race-to-13 (with OT-as-coinflip terminal at
    12-12). Under a constant round_p_fn, IID-maps + IID-rounds holds, so the
    per-map win prob is exactly ``series_value(decider_state, fn)`` — i.e., the
    DP value at a state where the current map clinches the series. Composing
    that through ``_bo3_series_prob`` reproduces the BO3 series value.

    This rewrite (relative to the plan's literal phrasing) corrects a math bug
    in the plan: ``_bo3_series_prob(round_p)`` would only equal the BO3 series
    value at the degenerate point round_p=0.5. Per Rule 1, the test is fixed
    inline — the closed-form fixture is still wired and the IID symmetry
    invariant is still being verified, just with the correct argument.
    """
    fn = _ConstantRoundPFn(p)

    # Single-map "decider" root: A and B each have 1 map already, so winning the
    # current map ends the series. series_value at this state equals per-map prob.
    decider_state = BO3State(
        map_idx=2,
        a_map_score=1,
        b_map_score=1,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(None, None, None),
    )
    per_map_prob = series_value(decider_state, fn)
    expected = _bo3_series_prob(per_map_prob)

    actual = series_value(_root(), fn)
    assert math.isclose(actual, expected, rel_tol=1e-9)


# --------------------------------------------------------------------------- #
# 3. OT hard-stop                                                             #
# --------------------------------------------------------------------------- #


def test_dp_ot_hardstop_returns_coinflip_leaf_symmetric() -> None:
    """At total=24 with p=0.5 and 0-0 in maps, DP returns 0.5 by symmetry.

    DEC-009 / CRule 5: OT collapses to 50/50 on next-map series outcomes.
    """
    state = BO3State(
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=12,
        b_round=12,
        side_orient="a_def",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(True, None, None),
    )
    val = series_value(state, _ConstantRoundPFn(0.5))
    assert math.isclose(val, 0.5, rel_tol=1e-9)


def test_dp_ot_hardstop_recurses_into_next_map_for_asymmetric_state() -> None:
    """At total=24 with A up 1-0 in maps, OT leaf is NOT flat 0.5 — it must
    recurse into asymmetric next-map series states.

    State: A is 1-0 in maps, this map is 12-12 (OT). If A wins OT, series
    goes to 2-0 (A clinches). If B wins OT, series goes to 1-1 (decider on map 3).

    Under p=0.5 in the decider (map 3 from 0-0), P(A wins decider) = 0.5
    (closed form: p^2(3-2p) at p=0.5 gives 0.5; for a single decider map
    starting fresh at 0-0, P(A wins map) under constant p=0.5 is 0.5).
    So the OT leaf returns 0.5 * 1.0 + 0.5 * 0.5 = 0.75.
    """
    state = BO3State(
        map_idx=0,
        a_map_score=1,
        b_map_score=0,
        a_round=12,
        b_round=12,
        side_orient="a_def",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(True, None, None),
    )
    val = series_value(state, _ConstantRoundPFn(0.5))
    # 0.5*P(A wins | map_score=2-0) + 0.5*P(A wins | map_score=1-1, decider at 0-0 under p=0.5)
    # = 0.5 * 1.0 + 0.5 * 0.5 = 0.75
    assert math.isclose(val, 0.75, rel_tol=1e-9)


def test_dp_ot_path_consults_round_p_fn_next_side_orient() -> None:
    """Blocker #3 / Warning #9: the OT path threads next_side_orient through the
    round_p_fn closure. Different `next_side_orient_for` values produce different
    BO3States at the next-map root. Verified by spying on the BO3State observed
    by `__call__` after the OT leaf fires.

    State construction: 12-12 in regulation on map 0, A up 1-0. The OT leaf
    advances to map 1; we then do at least ONE within-map round in map 1 (the
    `__call__` is invoked there with a state whose `side_orient` is the result
    of `next_side_orient_for(1)`).
    """
    seen_atk: list[BO3State] = []
    seen_def: list[BO3State] = []

    class _Spy:
        def __init__(self, observed: list[BO3State], next_sides: tuple[str, ...]) -> None:
            self._observed = observed
            self._next_sides = next_sides

        def __call__(self, state: BO3State) -> float:
            self._observed.append(state)
            return 0.5

        def next_side_orient_for(self, map_idx: int) -> str:
            if map_idx >= len(self._next_sides):
                return "a_atk"
            return self._next_sides[map_idx]

    state = BO3State(
        map_idx=0,
        a_map_score=1,
        b_map_score=0,
        a_round=12,
        b_round=12,
        side_orient="a_def",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(True, None, None),
    )
    # Clear cache so the OT recursion actually invokes __call__ on freshly-rooted
    # next-map states (caching across the two runs would short-circuit the spy).
    _series_value_cached.cache_clear()
    series_value(state, _Spy(seen_atk, next_sides=("a_atk", "a_atk", "a_atk")))
    _series_value_cached.cache_clear()
    series_value(state, _Spy(seen_def, next_sides=("a_atk", "a_def", "a_atk")))

    # In the b_won-OT-branch path, the next-map root must inherit the supplied side.
    # Under "a_atk" everywhere: every observed state at map_idx=1 has side_orient='a_atk'
    # at round=0 (i.e., before any within-map flip).
    atk_map1_root_sides = {
        s.side_orient for s in seen_atk
        if s.map_idx == 1 and s.a_round + s.b_round == 0
    }
    def_map1_root_sides = {
        s.side_orient for s in seen_def
        if s.map_idx == 1 and s.a_round + s.b_round == 0
    }
    assert atk_map1_root_sides == {"a_atk"}, atk_map1_root_sides
    assert def_map1_root_sides == {"a_def"}, def_map1_root_sides


# --------------------------------------------------------------------------- #
# 4. Terminals                                                                #
# --------------------------------------------------------------------------- #


def test_dp_terminal_a_clinched_returns_1() -> None:
    state = BO3State(
        map_idx=2,
        a_map_score=2,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(True, True, None),
    )
    assert series_value(state, _ConstantRoundPFn(0.5)) == 1.0


def test_dp_terminal_b_clinched_returns_0() -> None:
    state = BO3State(
        map_idx=2,
        a_map_score=0,
        b_map_score=2,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(False, False, None),
    )
    assert series_value(state, _ConstantRoundPFn(0.5)) == 0.0


# --------------------------------------------------------------------------- #
# 5. Memoization sanity                                                       #
# --------------------------------------------------------------------------- #


def test_dp_lru_cache_records_hits_on_repeat_call() -> None:
    """Repeated series_value with the same fn should hit the cache.

    NOTE: each series_value call registers a fresh round_p_id, so the cache key
    differs across calls. Hits accumulate WITHIN a single recursion (the same
    call recurses into many sub-states that share the round_p_id). Verify
    hits > 0 after a single root call.
    """
    _series_value_cached.cache_clear()
    series_value(_root(), _ConstantRoundPFn(0.6))
    info = _series_value_cached.cache_info()
    # A 3-map BO3 with within-map alternating recurrences produces hundreds of
    # state visits with substantial reuse — hits MUST be > 0.
    assert info.hits > 0
    assert info.currsize > 0


# --------------------------------------------------------------------------- #
# 6. Regression — DEC-009 / DEC-011 / PRD §12.2 #6 bug fixes                  #
# --------------------------------------------------------------------------- #


def _executable_dp_source() -> str:
    """Strip comments AND docstrings from src/pricing/dp.py for source-level
    regression checks.

    Module / function / class docstrings legitimately mention the bug patterns
    being regression-locked (e.g., the module docstring documents the fix for
    PRD §12.2 #3 by referencing ``range(26)``). Stripping them prevents the
    grep from tripping on documentation. Comments (``#`` prefix) are stripped
    too — this matches CLAUDE.md "no magic numbers in business logic" intent
    that targets executable code only.
    """
    import ast
    import io
    import tokenize

    src_path = Path("src/pricing/dp.py")
    src = src_path.read_text(encoding="utf-8")

    # 1. Remove all string-literal docstrings via AST surgery: walk the tree
    # and clear ``Expr(value=Constant(str))`` first-statement nodes from
    # Module / FunctionDef / AsyncFunctionDef / ClassDef bodies.
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(
            node, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
        ) and node.body:
            first = node.body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                # Replace the docstring with a no-op so unparse keeps shape.
                node.body[0] = ast.Expr(value=ast.Constant(value=...))
    src_no_docstrings = ast.unparse(tree)

    # 2. Strip ``#`` comments from the unparsed source.
    out = io.StringIO()
    prev_end = (1, 0)
    for tok in tokenize.generate_tokens(io.StringIO(src_no_docstrings).readline):
        if tok.type == tokenize.COMMENT:
            continue
        if tok.type in (tokenize.NL, tokenize.NEWLINE, tokenize.ENCODING):
            out.write(tok.string)
            continue
        # Pad whitespace between tokens to preserve column positions roughly.
        if tok.start[0] != prev_end[0]:
            out.write("\n")
            out.write(" " * tok.start[1])
        elif tok.start[1] > prev_end[1]:
            out.write(" " * (tok.start[1] - prev_end[1]))
        out.write(tok.string)
        prev_end = tok.end
    return out.getvalue()


def test_dp_source_does_not_loop_past_24() -> None:
    """DEC-009 / PRD §12.2 #3: must not contain `range(26)` or
    `range(WIN_THRESHOLD * 2)` as a loop bound that iterates past total=24.
    """
    code = _executable_dp_source()
    assert "range(26)" not in code
    assert "range(WIN_THRESHOLD * 2)" not in code


def test_dp_source_uses_explicit_ot_hardstop_constant() -> None:
    """DEC-009: OT hard-stop must use REGULATION_HALF * 2, not bare 24.

    CON-no-magic-numbers (CRule 12) — inline `24` is forbidden in business logic.
    """
    src = Path("src/pricing/dp.py").read_text(encoding="utf-8")
    assert "REGULATION_HALF * 2" in src


def test_dp_source_does_not_use_constant_p1_p2_dispatch() -> None:
    """DEC-011 / PRD §12.2 #5: must not contain audit-engine's
    `if total < REGULATION_HALF: p = p1` constant-per-half dispatch.
    """
    code = _executable_dp_source()
    # The audit engine's signature pattern (lines 189-194):
    assert "p = p1" not in code
    assert "p = p2" not in code


def test_dp_advance_to_next_map_takes_explicit_next_side_orient() -> None:
    """Blocker #3 / Warning #9 / PRD §12.2 #6: `_advance_to_next_map` must take
    `next_side_orient` as an explicit parameter — NO hardcoded 'a_atk' default
    inside the function body.

    Two-part verification:
      (a) function signature contains `next_side_orient: str` parameter.
      (b) function body does NOT assign side_orient to a literal 'a_atk' or 'a_def',
          and forwards the parameter through.

    The body extraction is AST-based (rather than line-pattern based) so the
    multi-line signature of ``_advance_to_next_map(state, a_won, next_side_orient)``
    is robustly skipped.
    """
    import ast

    src = Path("src/pricing/dp.py").read_text(encoding="utf-8")
    # (a) Signature includes the explicit parameter.
    assert "next_side_orient: str" in src

    # (b) AST-walk to the _advance_to_next_map FunctionDef and unparse its body.
    tree = ast.parse(src)
    fn_node: ast.FunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_advance_to_next_map":
            fn_node = node
            break
    assert fn_node is not None, "_advance_to_next_map function not found in dp.py"

    # Drop the docstring (first Expr/Constant str), then unparse remaining body.
    body_nodes = list(fn_node.body)
    if (
        body_nodes
        and isinstance(body_nodes[0], ast.Expr)
        and isinstance(body_nodes[0].value, ast.Constant)
        and isinstance(body_nodes[0].value.value, str)
    ):
        body_nodes = body_nodes[1:]
    body_code = "\n".join(ast.unparse(stmt) for stmt in body_nodes)

    assert 'side_orient="a_atk"' not in body_code
    assert "side_orient='a_atk'" not in body_code
    assert 'side_orient="a_def"' not in body_code
    assert "side_orient='a_def'" not in body_code
    # Body MUST forward the parameter through:
    assert "side_orient=next_side_orient" in body_code


# --------------------------------------------------------------------------- #
# 7. CR-05 regression — pistol_winner_a propagation through DP forward-pass   #
# --------------------------------------------------------------------------- #


def test_dp_anti_eco_uses_gun_win_rate_after_round_1_branch() -> None:
    """CR-05 (VERIFICATION.md gaps[0]): the DP forward-pass MUST update
    BO3State.pistol_winner_a when round 1 settles, so that round 2 (anti-eco)
    dispatches to GUN_WIN_RATE — not the defensive 0.5 fallback in
    round_types.round_p_for_round.

    Setup: fresh BO3 root with pistol_winner_a=(None, None, None) and the A-wins
    branch of round 1 applied. The resulting state has a_round=1, b_round=0 and
    the next round is round 2 (anti-eco). After the CR-05 fix, the propagated
    pistol_winner_a tuple is (True, None, None), so round_p_for_round dispatches
    to GUN_WIN_RATE.

    On current `main` this test FAILS — _advance_round propagates
    pistol_winner_a verbatim and the dispatch falls through to 0.5.
    """
    bo3 = BO3State(
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(None, None, None),
    )

    state_after_round_1_a = _advance_round(bo3, a_wins=True)
    # Verify the state-shape invariant: round counts advanced, pistol slot for
    # the current map populated, others untouched.
    assert state_after_round_1_a.a_round == 1
    assert state_after_round_1_a.b_round == 0
    assert state_after_round_1_a.pistol_winner_a[0] is True, (
        f"CR-05 not closed: pistol_winner_a[0] = "
        f"{state_after_round_1_a.pistol_winner_a[0]!r}, expected True"
    )
    assert state_after_round_1_a.pistol_winner_a[1] is None
    assert state_after_round_1_a.pistol_winner_a[2] is None

    # The A-wins state's next round is round 2 (anti-eco). Dispatch via
    # round_p_for_round directly — same path live_theo's _RoundPFnImpl uses.
    p_round_2 = round_p_for_round(
        state_after_round_1_a, _FakeMatchState(), _FakeHalfRates()  # type: ignore[arg-type]
    )
    assert math.isclose(p_round_2, GUN_WIN_RATE, rel_tol=1e-9), (
        f"CR-05: anti-eco round 2 should use GUN_WIN_RATE ({GUN_WIN_RATE}) "
        f"after A won round 1, got {p_round_2!r}"
    )


def test_dp_anti_eco_returns_complement_after_b_wins_round_1() -> None:
    """CR-05 mirror: B-wins branch of round 1 propagates pistol_winner_a[0] = False,
    and round 2 dispatches to 1 - GUN_WIN_RATE.
    """
    bo3 = BO3State(
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(None, None, None),
    )

    state_after_round_1_b = _advance_round(bo3, a_wins=False)
    assert state_after_round_1_b.a_round == 0
    assert state_after_round_1_b.b_round == 1
    assert state_after_round_1_b.pistol_winner_a[0] is False
    assert state_after_round_1_b.pistol_winner_a[1] is None
    assert state_after_round_1_b.pistol_winner_a[2] is None

    p_round_2 = round_p_for_round(
        state_after_round_1_b, _FakeMatchState(), _FakeHalfRates()  # type: ignore[arg-type]
    )
    assert math.isclose(p_round_2, 1.0 - GUN_WIN_RATE, rel_tol=1e-9), (
        f"CR-05 mirror: anti-eco round 2 should use 1-GUN_WIN_RATE "
        f"({1.0 - GUN_WIN_RATE}) after B won round 1, got {p_round_2!r}"
    )


def test_dp_advance_round_does_not_override_already_settled_pistol() -> None:
    """CR-05 invariant: when pistol_winner_a[map_idx] is already set (e.g., live
    ingestion has populated it), _advance_round MUST NOT override it on subsequent
    round-1 advances. Only None -> True/False is permitted; True/False is
    immutable through the DP forward-pass.

    (Construction note: an already-settled pistol_winner_a[0] paired with
    a_round=0, b_round=0 is theoretically reachable only if a caller hand-rolls
    such a state — it is not a state the DP itself produces. The test guards
    against a regression where `_advance_round` unconditionally overrides.)
    """
    bo3 = BO3State(
        map_idx=0,
        a_map_score=0,
        b_map_score=0,
        a_round=0,
        b_round=0,
        side_orient="a_atk",
        map_pool=("Lotus", "Bind", "Haven"),
        pistol_winner_a=(True, None, None),  # already-settled
    )

    state_after = _advance_round(bo3, a_wins=False)
    # B winning the "round 1" should NOT flip pistol_winner_a[0] from True -> False.
    assert state_after.pistol_winner_a[0] is True, (
        f"CR-05 invariant violated: _advance_round overrode an already-settled "
        f"pistol_winner_a[0] from True -> {state_after.pistol_winner_a[0]!r}"
    )
