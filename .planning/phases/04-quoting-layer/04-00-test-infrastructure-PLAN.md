---
phase: 04-quoting-layer
plan: "00"
type: execute
wave: 1
depends_on: []
files_modified:
  - pyproject.toml
  - tests/quoting/__init__.py
  - tests/quoting/conftest.py
  - tests/quoting/test_kalshi_auth.py
  - tests/quoting/test_order_manager.py
  - tests/quoting/test_market_data.py
  - tests/quoting/test_mode_selector.py
  - tests/quoting/test_mm_quoter.py
  - tests/quoting/test_directional_taker.py
  - tests/quoting/test_post_plant_quoter.py
  - tests/quoting/test_kill_switches.py
  - tests/quoting/test_fill_ledger.py
  - tests/quoting/test_reconciliation.py
  - tests/quoting/test_e2e.py
  - tests/sizing/__init__.py
  - tests/sizing/test_kelly_portfolio.py
  - src/config/constants.py
  - tests/config/test_constants.py
  - .gitignore
autonomous: true
requirements:
  - REQ-kalshi-order-manager
  - REQ-mode-selector
  - REQ-mm-quoter
  - REQ-directional-taker
  - REQ-post-plant-quoter
  - REQ-kelly-sizer
  - REQ-kill-switches
  - REQ-order-lifecycle-reconciliation
notes: |
  Wave 1 — RED-stub test infrastructure + dev deps + Phase 04 constants.
  Mirrors Phase 03 plan 03-00 pattern: lay every per-REQ test file as RED
  xfail stubs so subsequent plans (04-01..04-08) swap stubs for assertions
  atomically without context-window pressure. Adds 3 new dev deps
  (cryptography>=42, websockets>=12, hypothesis is already a dev dep).
  Adds 9 new constants to src/config/constants.py with TODO(phase-5-calibrate)
  markers AND extends tests/config/test_constants.py allow-list in the SAME
  commit (Phase 03 D-08 same-commit Rule-3 prophylactic — recurring
  blocking auto-fix when new constants land).

  Adds two `[[tool.mypy.overrides]]` blocks for `src.quoting.*` and
  `src.sizing.*` to extend strict typing per CRule 11 (Phase 03 SPEC
  established the pattern for src.state.*; Phase 04 RESEARCH §"User
  Constraints / Carry-forward" recommends adding the override).

  Adds `data/fills/` to `.gitignore` (per-strategy hypothetical-fill ledgers
  are runtime artifacts; mirrors Phase 03's `data/event_log/` + `data/metrics/`
  gitignore additions).

  RED-stub xfail pattern: `pytest.xfail("Plan 04-NN — not yet implemented")`
  runtime call inside the body, not `@pytest.mark.xfail` decorator. Phase 03
  D-01 carry-forward — wave-N executors flip stubs by replacing the body;
  decorator removal would leave dead `xfail` call lines.

must_haves:
  truths:
    - "tests/quoting/ + tests/sizing/ packages collect under pytest with 0 errors (xfail-stubs allowed)"
    - "uv-installed dev deps (cryptography, websockets) load without ImportError"
    - "mypy --strict src/quoting/ + src/sizing/ runs without 'unrecognized module' errors (empty modules pass)"
    - "Phase 04 constants importable from src.config.constants and present in tests/config/test_constants.py EXPECTED_NAMES allow-list"
  artifacts:
    - path: "tests/quoting/conftest.py"
      provides: "shared fixtures: make_match_state (re-exported from tests/ingestion/conftest), make_market_quote, fake_kalshi_session (aioresponses-mocked), tmp_fill_ledger_dir, fake_private_key (cryptography.rsa.generate_private_key for auth tests)"
      min_lines: 50
    - path: "tests/quoting/test_kalshi_auth.py"
      provides: "RED stub for REQ-kalshi-order-manager RSA-PSS sign_request"
      contains: "test_sign_request_returns_three_headers"
    - path: "tests/quoting/test_mode_selector.py"
      provides: "RED stubs for REQ-mode-selector — 6 rules in declared order + tie-break test"
      contains: "test_rule_1_kill_switch_dominates"
    - path: "tests/quoting/test_post_plant_quoter.py"
      provides: "RED stub for REQ-post-plant-quoter incl. 100ms quote-pull p50 latency assertion"
      contains: "test_quote_pull_p50"
    - path: "tests/sizing/test_kelly_portfolio.py"
      provides: "RED stub for REQ-kelly-sizer per-market + per-series cap (hypothesis-property)"
      contains: "test_aggregate_cap_binds"
    - path: "src/config/constants.py"
      provides: "9 new Phase 04 constants: TAKE_THRESHOLD, MM_MIN_EDGE, POST_PLANT_TAKE_THRESHOLD, MIN_HALF_SPREAD, SERIES_AGGREGATE_CAP_FRAC, RELATIVE_BRIER_EDGE_MIN, MIN_FILLS_PER_MATCH, KALSHI_BASE_URL, KALSHI_WS_URL"
      contains: "SERIES_AGGREGATE_CAP_FRAC"
    - path: "tests/config/test_constants.py"
      provides: "EXPECTED_NAMES + EXPECTED_TYPES allow-lists extended with the 9 new Phase 04 constants in same commit"
      contains: "SERIES_AGGREGATE_CAP_FRAC"
    - path: "pyproject.toml"
      provides: "[[tool.mypy.overrides]] strict on src.quoting.* AND src.sizing.* + cryptography>=42 + websockets>=12 dev deps"
      contains: "src.quoting.*"
  key_links:
    - from: "pyproject.toml [project].dependencies"
      to: "cryptography (RSA-PSS auth) + websockets (Kalshi WS)"
      via: "uv add cryptography websockets"
      pattern: "cryptography.*websockets"
    - from: "tests/quoting/test_*.py"
      to: "shared fixtures in tests/quoting/conftest.py"
      via: "pytest auto-discovery"
      pattern: "def test_"
    - from: "src/config/constants.py"
      to: "tests/config/test_constants.py EXPECTED_NAMES"
      via: "atomic same-commit allow-list extension (Phase 03 D-08)"
      pattern: "TAKE_THRESHOLD.*MM_MIN_EDGE.*POST_PLANT_TAKE_THRESHOLD"
---

<objective>
Wave 1 — establish the Phase 04 test scaffolding (RED stubs), dev deps, and
all 9 new constants in a single atomic commit so subsequent plans (04-01
through 04-08) can drop GREEN tests into pre-existing files without racing
the test runner. No `src/quoting/` or `src/sizing/` business code lands here
— this is pure infrastructure.

Purpose: Per VALIDATION.md sampling rate (`pytest tests/quoting/ tests/sizing/
-x` after every task commit), every per-REQ test file must exist as a RED
stub so executors can land `<automated>` verify commands as plain `pytest -k`
invocations. Without Wave 1 the executor stubs would race with
implementation, break the Nyquist sampling rate, and fail the per-task verify
gate.

Output: 13 empty test files (xfail-stubs only) + populated conftest + 3 dev
dep updates + 9 constants + 2 mypy override blocks + .gitignore additions.
NO `src/quoting/` or `src/sizing/` source code.
</objective>

<execution_context>
@C:/Users/Joseph Cheng/.claude/get-shit-done/workflows/execute-plan.md
@C:/Users/Joseph Cheng/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/04-quoting-layer/04-RESEARCH.md
@.planning/phases/04-quoting-layer/04-VALIDATION.md
@pyproject.toml
@src/config/constants.py
@tests/config/test_constants.py
@tests/ingestion/conftest.py

<interfaces>
<!-- Phase 03 contracts that Phase 04 tests will exercise -->
From src/state/match_state.py:
```python
@dataclass(frozen=True, slots=True)
class MatchState:
    # 7 static fields
    match_id: str
    team_a: str
    team_b: str
    map_pool: tuple[str, ...]
    map_side_orients: tuple[str, ...]
    map_winners: tuple[Optional[bool], ...]
    pistol_winner_a: dict[int, Optional[bool]]
    # 12 dynamic v2 fields
    map_idx: int
    a_map_score: int
    b_map_score: int
    a_round: int
    b_round: int
    side_orient: str
    bomb_planted: bool
    attackers_alive: Optional[int]   # populated only when bomb_planted=True
    defenders_alive: Optional[int]
    time_left_s: Optional[float]
    seq_id: int
    last_updated_ts: float

    def with_update(self, **fields_changed: Any) -> MatchState: ...
```

From src/pricing/data.py:
```python
@dataclass(frozen=True, slots=True)
class TheoOutput:
    theo_series: float                # P(team A wins series), clipped [0.01, 0.99]
    theo_map: tuple[float, ...]
    vega: float                       # = vega_between_round (Phase 1 D-10/D-11)
    confidence: float
```

From tests/ingestion/conftest.py (re-export pattern):
```python
@pytest.fixture
def make_match_state() -> Callable[..., MatchState]:
    def _make(**overrides: Any) -> MatchState: ...
    return _make
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add dev deps + 9 Phase 04 constants + mypy strict overrides + .gitignore + test_constants.py allow-list</name>
  <files>pyproject.toml, src/config/constants.py, tests/config/test_constants.py, .gitignore</files>
  <action>
Atomic commit covering 4 files:

(A) pyproject.toml:
  1. Add to `[project].dependencies` (NEW Phase 04 deps):
     - `cryptography>=42,<46`  (RSA-PSS signing for Kalshi auth — verified 2026-05-09 via docs.kalshi.com)
     - `websockets>=12,<14`    (Kalshi WS — auto ping/pong; aiohttp.ws_connect leaves heartbeat to caller)
     - `python-dotenv>=1`      (.env parsing for KALSHI_KEY_ID + KALSHI_KEY_PATH)
  2. Add two new `[[tool.mypy.overrides]]` blocks AFTER the existing `src.state.*` block:
     ```toml
     [[tool.mypy.overrides]]
     # Phase 04 SPEC §"Carry-forward" / RESEARCH §"User Constraints" — extend mypy --strict
     # from src/pricing/ + src/state/ to ALSO cover src/quoting/ (math + risk-control layer).
     module = "src.quoting.*"
     strict = true
     disallow_any_explicit = false
     warn_return_any = true

     [[tool.mypy.overrides]]
     # Phase 04 SPEC §"Carry-forward" — strict on src/sizing/ (pure-function Kelly sizer).
     module = "src.sizing.*"
     strict = true
     disallow_any_explicit = false
     warn_return_any = true
     ```

(B) src/config/constants.py — append a new "Phase 4 — quoting layer" section AT THE END
    (after the Phase 3 text-listener block). Each constant uses `Final[...]` and a
    triple-quoted docstring with `# TODO(phase-5-calibrate)` markers per RESEARCH §"Open
    Questions" — initial values are placeholder guesses justified inline:

    ```python
    # ----------------------------------------------------------------------- #
    # Phase 4 — quoting layer thresholds (DEC-001 v2 mode selector)            #
    # ----------------------------------------------------------------------- #

    TAKE_THRESHOLD: Final[int] = 5  # cents
    """Between-round directional-take threshold (cents).

    DIRECTIONAL_TAKE fires when |theo_cents - market.mid| > TAKE_THRESHOLD.
    Source: DEC-001 v2 (replaces VEGA_DIRECTIONAL_THRESHOLD), PRD §2.1.

    TODO(phase-5-calibrate): Initial guess; tune from observed market structure
    after 20+ live matches per PRD §9.3. RESEARCH §"Open Questions" #1 cites
    5c as defensible starting point at typical Kalshi yes_bid/yes_ask spreads.
    """

    MM_MIN_EDGE: Final[int] = 4  # cents
    """Minimum market spread (cents) for MM_BETWEEN_ROUND to engage.

    MM_BETWEEN_ROUND fires when market.spread > MM_MIN_EDGE.
    Source: DEC-001 v2 selection rule 5, PRD §2.1.

    TODO(phase-5-calibrate): Initial guess; needs to exceed 2 * MIN_HALF_SPREAD
    + slippage budget so MM has room to quote inside the market. RESEARCH §"Open
    Questions" #1.
    """

    POST_PLANT_TAKE_THRESHOLD: Final[int] = 3  # cents
    """Post-plant directional-take threshold (cents) — narrower than between-round
    because post-plant theo is a high-conviction state (DEC-007 v2).

    POST_PLANT_QUOTE quoter takes when |theo - market| > POST_PLANT_TAKE_THRESHOLD,
    otherwise quotes at theo +/- narrow spread.
    Source: PRD §5.4, REQ-post-plant-quoter.

    TODO(phase-5-calibrate): Initial guess.
    """

    MIN_HALF_SPREAD: Final[int] = 3  # cents
    """MM half-spread floor (cents). MUST beat Kalshi commission + slippage per CRule 7.

    Justification (RESEARCH Pitfall 4, verified 2026-05-09):
      - Kalshi taker fee at theo=50c: ceil(0.07 * 0.5 * 0.5 * 100) / 100 = 1.75c
      - Maker fee = 25% of taker = 0.44c (we quote post_only=True)
      - 3c half-spread + 0.44c maker fee = 2.56c net edge if theo is exact
      - Covers 1c of model slippage AND 1c of arbiter staleness slippage
    Spread formula: spread = max(MIN_HALF_SPREAD, k * sqrt(vega_between)) + staleness_penalty.
    Source: PRD §5.4, REQ-mm-quoter, RESEARCH §"Standard Stack" Kalshi fee curve.

    TODO(phase-5-calibrate): Calibrate down to 2c only after Phase 5 paper-trade
    shows 3c floor is tight (i.e., MM hypothetical fills are profitable net of fees
    AND well above MIN_FILLS_PER_MATCH).
    """

    # ----------------------------------------------------------------------- #
    # Phase 4 — portfolio Kelly v2 (DEC-023)                                   #
    # ----------------------------------------------------------------------- #

    SERIES_AGGREGATE_CAP_FRAC: Final[float] = 0.10
    """Per-series aggregate exposure cap (fraction of bankroll) — DEC-023 v2.

    Bounds correlated exposure across moneyline + map handicaps + round handicaps
    on the same series. PER_MARKET_CAP_FRAC alone (0.05) does NOT bound aggregate
    correlated exposure; this layer adds the safety floor.

    Sizer formula (DEC-023):
        f = max(0, KELLY_MULTIPLIER * f_full)
        f = min(f, PER_MARKET_CAP_FRAC)                              # 0.05
        headroom = max(0, SERIES_AGGREGATE_CAP_FRAC - exposure[s])  # 0.10
        f = min(f, headroom)
        return 0 if f == 0 else int(f * bankroll / ask)

    TODO(phase-5-calibrate): Defensive initial guess. Recompute from observed
    inter-market correlation after first paper-trade event. Full covariance-aware
    Kelly is REQ-portfolio-correlation-kelly (Phase 7).
    """

    # ----------------------------------------------------------------------- #
    # Phase 4 — promotion gate (DEC-020 v2 — referenced by fill ledger / kill #
    # switches; primary consumer is Phase 5 paper-trade evaluation)            #
    # ----------------------------------------------------------------------- #

    RELATIVE_BRIER_EDGE_MIN: Final[float] = 0.02
    """Promotion gate: Brier(model) must beat Brier(market_mid) by this margin
    over a 50-round window. Replaces v1 absolute Brier 0.22 floor (DEC-020 v2).

    Source: DEC-020 v2, PRD §8, ROADMAP §5.3-5.4.
    """

    MIN_FILLS_PER_MATCH: Final[int] = 3
    """Promotion gate: MM strategy is cut from production if hypothetical fills
    averaged over a paper-trade event fall below this. DIRECTIONAL_TAKE
    (and POST_PLANT_QUOTE) can promote independently per DEC-020 v2.

    Source: DEC-020 v2, PRD §8.

    TODO(phase-5-calibrate): Initial guess; tune from observed MM fill rates.
    """

    # ----------------------------------------------------------------------- #
    # Phase 4 — Kalshi endpoints                                               #
    # ----------------------------------------------------------------------- #

    KALSHI_BASE_URL: Final[str] = "https://api.elections.kalshi.com/trade-api/v2"
    """Kalshi REST base URL (verified 2026-05-09 via docs.kalshi.com)."""

    KALSHI_WS_URL: Final[str] = "wss://api.elections.kalshi.com/trade-api/ws/v2"
    """Kalshi WebSocket URL (verified 2026-05-09 via docs.kalshi.com/getting_started/quick_start_websockets)."""
    ```

    NOTE: do NOT delete `VEGA_DIRECTIONAL_THRESHOLD` here — that deletion happens
    atomically in plan 04-04 (mode-selector) along with its tests/config
    allow-list update (RESEARCH §"State of the Art" — same-commit Rule-3 pattern).

(C) tests/config/test_constants.py — extend `EXPECTED_NAMES` and `EXPECTED_TYPES`
    allow-lists with the 9 new constants. Add a new "Phase 4 — quoting" section
    block. Mirror the existing pattern (alphabetic-ish within section, type tuple).

(D) .gitignore — add:
    ```
    # Phase 4 — hypothetical-fill ledgers (per-strategy JSONL files)
    data/fills/
    !data/fills/.gitkeep
    ```
    AND ensure `data/fills/.gitkeep` is created (empty file) so the directory is
    git-tracked but its contents are not. Use the same glob pattern as Phase 03
    D-21 (`data/event_log/*` + explicit `!.gitkeep` allow-list — Phase 3 SUMMARY
    learned this caveat).

CRITICAL: This is a SINGLE commit per the RESEARCH §"State of the Art" same-commit
Rule-3 prophylactic. Splitting (B) and (C) across commits leaves CI red between them.
  </action>
  <verify>
    <automated>uv sync --dev &amp;&amp; uv run pytest tests/config/test_constants.py -x --no-cov &amp;&amp; uv run mypy --strict src/state/ src/pricing/</automated>
  </verify>
  <done>
- `pyproject.toml` declares `cryptography`, `websockets`, `python-dotenv` in `[project].dependencies` and includes `[[tool.mypy.overrides]]` blocks for `src.quoting.*` and `src.sizing.*` (strict=true).
- `src/config/constants.py` contains all 9 new constants with `Final[...]` annotations and `TODO(phase-5-calibrate)` markers where applicable.
- `tests/config/test_constants.py` `EXPECTED_NAMES` allow-list contains all 9 new names; `EXPECTED_TYPES` covers their types; the test passes.
- `.gitignore` excludes `data/fills/` content but allows `.gitkeep`.
- `uv sync` succeeds; `uv run pytest tests/config/test_constants.py -x` passes.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: RED-stub test files for tests/quoting/ + tests/sizing/ + populated conftest</name>
  <files>tests/quoting/__init__.py, tests/quoting/conftest.py, tests/quoting/test_kalshi_auth.py, tests/quoting/test_order_manager.py, tests/quoting/test_market_data.py, tests/quoting/test_mode_selector.py, tests/quoting/test_mm_quoter.py, tests/quoting/test_directional_taker.py, tests/quoting/test_post_plant_quoter.py, tests/quoting/test_kill_switches.py, tests/quoting/test_fill_ledger.py, tests/quoting/test_reconciliation.py, tests/quoting/test_e2e.py, tests/sizing/__init__.py, tests/sizing/test_kelly_portfolio.py</files>
  <behavior>
    - Every test file collects under pytest with 0 errors (xfail-stubs allowed)
    - Every test function calls `pytest.xfail("Plan 04-NN — not yet implemented")` inside its body (NOT a decorator) — Phase 03 D-01 carry-forward
    - `make_match_state` fixture re-exports the dict-update pattern from `tests/ingestion/conftest.py` so quoting tests can build `MatchState` instances by partial overrides
    - `make_market_quote` fixture builds a `MarketQuote(yes_bid, yes_ask, mid, spread)` namedtuple/dataclass for use BEFORE plan 04-01 ships the real class (test stubs can use the stand-in shape)
    - `fake_private_key` fixture generates a fresh RSA key per test (cryptography.hazmat.primitives.asymmetric.rsa.generate_private_key, public_exponent=65537, key_size=2048)
    - `tmp_fill_ledger_dir` fixture yields a `tmp_path / "fills"` Path
    - `fake_kalshi_session` fixture wraps `aioresponses` for REST endpoint mocking (already-installed dev dep from Phase 03)
  </behavior>
  <action>
Create 13 RED-stub test files plus an `__init__.py` per package.

(A) tests/quoting/__init__.py — empty file.

(B) tests/sizing/__init__.py — empty file.

(C) tests/quoting/conftest.py — populated fixture module (~80 lines):
    ```python
    """Phase 04 quoting/sizing shared fixtures.

    Used by every tests/quoting/test_*.py and tests/sizing/test_*.py per
    .planning/phases/04-quoting-layer/04-VALIDATION.md.

    Re-exports `make_match_state` from tests/ingestion/conftest.py so quoting
    tests can build MatchState instances without depending on the ingestion
    package layout. Adds Phase 04-specific fixtures: make_market_quote,
    fake_private_key, fake_kalshi_session, tmp_fill_ledger_dir.
    """
    from __future__ import annotations

    from collections.abc import Callable
    from dataclasses import dataclass
    from pathlib import Path
    from typing import Any

    import pytest

    # Re-export Phase 03 fixture so quoting tests can build MatchState instances.
    from tests.ingestion.conftest import make_match_state  # noqa: F401  (pytest fixture re-export)


    @dataclass(frozen=True, slots=True)
    class _StubMarketQuote:
        """Stand-in MarketQuote shape for use BEFORE plan 04-01 ships the real
        dataclass at src/quoting/market_data.py. Plans 04-04 onwards will swap
        this for the real import."""
        yes_bid: int       # cents 1-99
        yes_ask: int
        mid: int
        spread: int        # = yes_ask - yes_bid
        is_valid: bool = True


    @pytest.fixture
    def make_market_quote() -> Callable[..., _StubMarketQuote]:
        def _make(**overrides: Any) -> _StubMarketQuote:
            base = {"yes_bid": 48, "yes_ask": 52, "mid": 50, "spread": 4, "is_valid": True}
            base.update(overrides)
            return _StubMarketQuote(**base)
        return _make


    @pytest.fixture
    def fake_private_key() -> Any:
        """Fresh RSA key for auth-signing tests. Standard 2048-bit per Kalshi docs."""
        from cryptography.hazmat.primitives.asymmetric import rsa
        return rsa.generate_private_key(public_exponent=65537, key_size=2048)


    @pytest.fixture
    def tmp_fill_ledger_dir(tmp_path: Path) -> Path:
        d = tmp_path / "fills"
        d.mkdir(parents=True, exist_ok=True)
        return d


    @pytest.fixture
    def fake_kalshi_session():
        """aioresponses-mocked aiohttp ClientSession for Kalshi REST tests.

        Usage:
            async def test_x(fake_kalshi_session):
                with fake_kalshi_session as m:
                    m.post("https://api.elections.kalshi.com/trade-api/v2/portfolio/orders",
                           status=201, payload={"order": {"order_id": "abc"}})
                    ...
        """
        from aioresponses import aioresponses
        return aioresponses()
    ```

(D) Each of the 11 `tests/quoting/test_*.py` files — create with a module
    docstring referencing the requirement(s) it covers, then ONE-PER-RULE
    RED-stub test functions. The xfail call goes INSIDE the body:

    Example shape (mode_selector — fullest rule coverage):
    ```python
    """Plan 04-04 — REQ-mode-selector RED-stub tests.

    All 6 selection rules in declared order + tie-break + IDLE fall-through.
    Each test xfails until plan 04-04 ships src/quoting/mode_selector.py.

    Source: PRD §2.1 / DEC-001 v2 / RESEARCH §"Pattern 1" / Pitfall 3.
    """
    from __future__ import annotations

    import pytest


    def test_rule_1_kill_switch_dominates(make_match_state, make_market_quote) -> None:
        pytest.xfail("Plan 04-04 — src/quoting/mode_selector.py not yet implemented")


    def test_rule_2_bomb_planted_returns_post_plant_quote(make_match_state, make_market_quote) -> None:
        pytest.xfail("Plan 04-04 — src/quoting/mode_selector.py not yet implemented")


    def test_rule_3_mid_round_not_planted_returns_idle(make_match_state, make_market_quote) -> None:
        pytest.xfail("Plan 04-04 — src/quoting/mode_selector.py not yet implemented")


    def test_rule_4_take_threshold_returns_directional(make_match_state, make_market_quote) -> None:
        pytest.xfail("Plan 04-04 — src/quoting/mode_selector.py not yet implemented")


    def test_rule_5_mm_min_edge_returns_mm_between_round(make_match_state, make_market_quote) -> None:
        pytest.xfail("Plan 04-04 — src/quoting/mode_selector.py not yet implemented")


    def test_rule_6_fall_through_returns_idle(make_match_state, make_market_quote) -> None:
        pytest.xfail("Plan 04-04 — src/quoting/mode_selector.py not yet implemented")


    def test_tie_directional_dominates_mm(make_match_state, make_market_quote) -> None:
        """Pitfall 3: when BOTH rule 4 AND rule 5 conditions hold, declared
        order says rule 4 wins (DIRECTIONAL_TAKE). Pure-source-order priority."""
        pytest.xfail("Plan 04-04 — src/quoting/mode_selector.py not yet implemented")
    ```

    Apply the same pattern to all 11 files. Test names per VALIDATION.md
    "Phase Requirements → Test Map":

    - test_kalshi_auth.py:
        test_sign_request_returns_three_headers
        test_sign_request_rejects_query_string_path           # Pitfall 1 defensive assert
        test_sign_request_uses_pss_padding                    # Pitfall 2

    - test_order_manager.py:
        test_place_quote_dry_run                              # records DRY_* order_id, no network
        test_cancel_all_dry_run                               # clears _active_quotes
        test_error_streak_increments_on_failed_place          # salvaged from reference/market_maker.py
        test_client_order_id_uuid_set                         # RESEARCH §"Pattern 2" — UUID survives reconnect

    - test_market_data.py:
        test_market_quote_dataclass_shape                     # yes_bid, yes_ask, mid, spread, is_valid
        test_ws_subscribe_message_shape                       # orderbook_delta + ticker channels
        test_ws_disconnect_marks_invalid                      # Pitfall 7

    - test_mode_selector.py:                                  # 7 tests above

    - test_mm_quoter.py:
        test_spread_formula                                   # max(MIN_HALF_SPREAD, k*sqrt(vega))
        test_spread_floor_beats_fee                           # property — Pitfall 4
        test_writes_mm_between_round_ledger                   # Pattern 4 separate ledger
        test_pulls_quotes_on_2s_staleness                     # PRD §5.4

    - test_directional_taker.py:
        test_take_fires_at_threshold                          # |theo - mid| > TAKE_THRESHOLD
        test_kelly_sized                                      # consumes kelly_size from src.sizing.kelly
        test_writes_directional_ledger_only                   # Pattern 4 separate ledger

    - test_post_plant_quoter.py:
        test_defensive_quote_pull                             # bomb_planted False -> True triggers cancel-all-MM
        test_repricing_via_post_plant_lookup                  # uses live_theo's post_plant path
        test_take_or_quote_branch_at_threshold                # POST_PLANT_TAKE_THRESHOLD
        test_quote_pull_p50                                   # Phase 04's 100ms piece of 200ms PRD budget; Pitfall 6

    - test_kill_switches.py:
        test_staleness_trip_at_5s                             # KILL_SWITCH_STALENESS_S boundary
        test_staleness_no_trip_at_4_99s                       # boundary - just under
        test_deviation_trip_at_21c                            # KILL_SWITCH_DEVIATION_C boundary
        test_deviation_no_trip_at_19c                         # boundary
        test_brier_trip_above_0_30                            # KILL_SWITCH_BRIER_BOUND
        test_brier_no_trip_window_not_full                    # < KILL_SWITCH_BRIER_WINDOW
        test_api_error_streak_trip                            # error_streak >= 3
        test_api_error_no_trip_at_2                           # boundary
        test_aggregator_any_tripped                           # ANY trip -> returns True + name list
        test_aggregator_returns_empty_when_none_tripped

    - test_fill_ledger.py:
        test_per_strategy_ledger_separate_files               # MM, DIRECTIONAL, POST_PLANT separate
        test_simulate_mm_fill_buy_crossed                     # DEC-020 simple touched rule (buy)
        test_simulate_mm_fill_sell_crossed                    # touched rule (sell)
        test_simulate_mm_fill_not_touched                     # no fill
        test_jsonl_line_schema                                # 10-key shape
        test_directional_separate_ledger                      # writes ONLY to DIRECTIONAL file

    - test_reconciliation.py:
        test_cancel_orphans                                   # Kalshi-has, we-don't -> cancel
        test_drop_ghosts                                      # we-have, Kalshi-doesn't -> drop local
        test_dry_run_noop                                     # reconcile_once returns early in dry-run
        test_signs_path_without_query                         # Pitfall 1 — re-tested at reconcile site

    - test_e2e.py:
        test_full_pipe_match_state_through_quoter             # plan 04-08 owns
        test_kill_switch_trip_cancels_all_resting             # plan 04-08 owns
        test_separate_strategy_ledgers_after_synthetic_run    # plan 04-08 owns

(E) tests/sizing/test_kelly_portfolio.py:
    ```python
    """Plan 04-02 — REQ-kelly-sizer (v2 portfolio-aware) RED-stub tests.

    DEC-023 v2: half-Kelly + per-market cap (0.05) + per-series aggregate cap (0.10).
    Pure function in src/sizing/kelly.py.
    """
    from __future__ import annotations

    import pytest


    def test_v1_single_market_compat() -> None:
        """Identical to v1 single-market case when current_series_exposure == {}."""
        pytest.xfail("Plan 04-02 — src/sizing/kelly.py not yet implemented")


    def test_aggregate_cap_binds_at_exposure_010() -> None:
        pytest.xfail("Plan 04-02 — src/sizing/kelly.py not yet implemented")


    def test_returns_zero_when_aggregate_exceeded() -> None:
        pytest.xfail("Plan 04-02 — src/sizing/kelly.py not yet implemented")


    def test_per_market_cap_binds_at_005() -> None:
        pytest.xfail("Plan 04-02 — src/sizing/kelly.py not yet implemented")


    def test_never_full_kelly() -> None:
        """Property: result <= int(KELLY_MULTIPLIER * f_full * bankroll / ask)."""
        pytest.xfail("Plan 04-02 — src/sizing/kelly.py not yet implemented")


    def test_returns_zero_for_negative_edge() -> None:
        """If theo <= ask/100, sizer returns 0."""
        pytest.xfail("Plan 04-02 — src/sizing/kelly.py not yet implemented")


    def test_handles_ask_at_boundaries() -> None:
        """ask=0 or ask>=100 returns 0 — defensive guard."""
        pytest.xfail("Plan 04-02 — src/sizing/kelly.py not yet implemented")
    ```

CRITICAL — RED-stub xfail pattern (Phase 03 D-01 carry-forward):
- Use `pytest.xfail(...)` runtime call INSIDE the function body, NOT
  `@pytest.mark.xfail` decorator. Wave-N executors flip stubs by replacing the
  body; decorator removal would leave dead xfail-call lines.

CRITICAL — DO NOT touch src/quoting/ or src/sizing/ in this plan; they remain
empty `__init__.py` stubs (already created in Phase 0). Plans 04-01..04-08
populate them.
  </action>
  <verify>
    <automated>uv run pytest tests/quoting/ tests/sizing/ -x --no-cov -q</automated>
  </verify>
  <done>
- 13 quoting test files + 1 sizing test file + 2 `__init__.py` markers + 1 conftest module exist.
- `pytest tests/quoting/ tests/sizing/ -x --no-cov` reports 0 errors and N xfailed (one per stub function).
- Every stub uses `pytest.xfail("Plan 04-NN — ...")` runtime call (verified by grep: `rg "pytest.xfail" tests/quoting/ tests/sizing/`).
- `tests/quoting/conftest.py` defines `make_market_quote`, `fake_private_key`, `tmp_fill_ledger_dir`, `fake_kalshi_session` fixtures and re-exports `make_match_state`.
- No new files in `src/quoting/` or `src/sizing/` (verified by `git diff --stat src/quoting/ src/sizing/` showing 0 changes).
  </done>
</task>

</tasks>

<verification>
Phase-level checks after both tasks:

1. `uv sync --dev` succeeds (cryptography + websockets + python-dotenv installed).
2. `uv run pytest tests/quoting/ tests/sizing/ tests/config/ -x --no-cov` reports 0 errors, all stub tests xfail.
3. `uv run pytest tests/ -x --no-cov` (full suite) — Phase 03 GREEN tests stay green; Phase 04 stubs xfail; total errors == 0.
4. `uv run mypy --strict src/state/ src/pricing/` clean (Phase 03 baseline preserved).
5. `uv run mypy --strict src/quoting/ src/sizing/` runs without "unrecognized module" errors (empty modules pass; mypy override active).
6. `python -c "from src.config.constants import TAKE_THRESHOLD, MM_MIN_EDGE, POST_PLANT_TAKE_THRESHOLD, MIN_HALF_SPREAD, SERIES_AGGREGATE_CAP_FRAC, RELATIVE_BRIER_EDGE_MIN, MIN_FILLS_PER_MATCH, KALSHI_BASE_URL, KALSHI_WS_URL"` succeeds.
7. `git diff --stat` shows ONLY: pyproject.toml + uv.lock + src/config/constants.py + tests/config/test_constants.py + .gitignore + 16 new test files. No `src/quoting/*.py` (other than empty `__init__.py` already in tree) or `src/sizing/*.py` changes.
</verification>

<success_criteria>
- All Phase 04 RED-stub test files exist and collect under pytest.
- 9 new constants importable from `src.config.constants` and gated by `tests/config/test_constants.py` allow-list.
- `cryptography>=42`, `websockets>=12`, `python-dotenv>=1` installed via `uv sync`.
- `[[tool.mypy.overrides]]` blocks for `src.quoting.*` AND `src.sizing.*` declared in pyproject.toml.
- `data/fills/` excluded from git (with `.gitkeep` allow-list).
- Phase 03 test suite stays GREEN; Phase 04 stub suite reports 0 errors / N xfailed.
</success_criteria>

<output>
After completion, create `.planning/phases/04-quoting-layer/04-00-SUMMARY.md` documenting:
- Files created (paths + line counts).
- Dev deps installed (`uv tree | grep -E "cryptography|websockets|python-dotenv"`).
- Total xfailed test count (`pytest tests/quoting/ tests/sizing/ -x --no-cov | tail -1`).
- Any deviations from this plan with rationale.
- Forward links to plans 04-01 (auth + order manager), 04-02 (kelly sizer), 04-03 (kill switches) which Wave 2 will execute against this scaffolding.
</output>
