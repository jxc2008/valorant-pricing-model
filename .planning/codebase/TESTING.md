# Testing Patterns

**Analysis Date:** 2026-04-27

> **Status: aspirational.** No tests exist yet. `tests/` contains a single `.gitkeep` (`tests/.gitkeep`). No `pytest.ini`, no `pyproject.toml`, no `conftest.py`, no `tox.ini`, no CI workflow. The salvaged `reference/*.py` files have no test coverage either; what passes for verification there is `if __name__ == "__main__":` smoke blocks at the bottom of each module (`reference/odds_utils.py:144-176`, `reference/fair_value.py:202-227`).
>
> This document records the testing approach **specified by `roadmap.md` and `prd.md`** so the first PR that adds tests has clear targets. Anything tagged **`[gap]`** is not yet wired up and must be created before tests can run.

---

## Test Framework

### Runner

- **Specified:** `pytest` + `pytest-cov` for coverage + `hypothesis` for property-based tests (`roadmap.md` §0.2).
- **`[gap]`** Not installed. No `pytest` in any dependency manifest because no manifest exists yet — `roadmap.md` §0.2 calls for `pyproject.toml` managed by `uv`, and that file has not been created.
- **`[gap]`** No `pytest.ini`, no `[tool.pytest.ini_options]` in any `pyproject.toml`, no `conftest.py`. First testing PR must add at minimum a `pyproject.toml` with `pytest` configured to discover from `tests/`.

### Assertion library

- **Specified (implicit):** plain `assert` per pytest convention — pytest rewrites assertions for rich failure messages.
- **Specified:** `hypothesis` strategies for property-based assertions on the math layer (`roadmap.md` §5.1).

### Run commands

```bash
# Specified by roadmap.md §0.2 — not yet runnable
uv run pytest                           # Run all tests
uv run pytest --cov=src --cov-report=term-missing
uv run pytest tests/pricing/ -v         # Watch a specific layer

# Specified by CLAUDE.md "Code" rule 11 — not yet runnable
uv run mypy --strict src/pricing
```

---

## Test File Organization

### Location

- **Specified:** Separate `tests/` directory, mirroring `src/` package layout (`CLAUDE.md` "Repo layout"; `roadmap.md` §0.1).
- **`[gap]`** Subpackage layout (`tests/pricing/`, `tests/state/`, `tests/ingestion/`, `tests/quoting/`, `tests/sizing/`) is implied by symmetry with `src/` but not yet created.

### Naming

- **Specified (implicit):** Standard pytest discovery — files named `test_*.py`, functions `test_*`, classes `Test*`. No deviations specified.

### Structure

```
tests/                          # currently: tests/.gitkeep only
  pricing/
    test_dp.py                  # exercises src/pricing/dp.py
    test_blend.py               # exercises src/pricing/blend.py
    test_round_types.py         # exercises src/pricing/round_types.py
    test_round_conclusion.py    # exercises src/pricing/round_conclusion.py
    test_live_theo.py           # exercises src/pricing/live_theo.py — the canonical entry point
  state/
    test_match_state.py
  ingestion/
    test_arbiter.py
  quoting/
    test_mode.py
    test_kill_switches.py
    test_order_manager.py
  sizing/
    test_kelly.py
```

This mirrors the `src/` tree from `CLAUDE.md` "Repo layout" and the module breakdown in `roadmap.md` §1–§4.

---

## Test Structure

### Suite organization

- **Specified (implicit):** Standard pytest functions; no class wrappers required. Use `pytest.fixture` for shared setup. No specific style is mandated by `prd.md` / `roadmap.md` / `CLAUDE.md`.

### Patterns

- **Setup pattern:** Module-level `@pytest.fixture` for the heavy objects (e.g. a `TheoEngine` / `live_theo` instance loaded against `data/half_win_rates.json`, or the pre-computed DP table at `models/dp_table.pkl` per `roadmap.md` §1.1).
- **Teardown pattern:** Not specified. State engine is in-memory only (`CLAUDE.md` "Differences from `thunderedge/CLAUDE.md`": "No SQLite for live state"), so most tests need no teardown beyond the fixture going out of scope. JSONL event-log tests should use `tmp_path` to avoid touching the real `logs/` directory.
- **Assertion pattern:** Plain `assert`. For floating-point math, use `pytest.approx(expected, abs=1e-9)` or `math.isclose`.

---

## Mocking

- **`[gap]`** No mocking framework specified in `roadmap.md` or `prd.md`. Default to stdlib `unittest.mock` (`MagicMock`, `patch`) since pytest integrates with it natively; no need to add `pytest-mock` unless monkeypatch syntax becomes painful.

### What to mock

- **Kalshi client.** The `KalshiOrderManager` (`roadmap.md` §4.1, salvaged from `reference/market_maker.py:206-262`) wraps a `KalshiClient`. Tests must mock the client to avoid real API calls. The `dry_run` path in `reference/market_maker.py:214-222, 252-254` is a runtime dry-run, **not** a test substitute — tests still need a `MagicMock` so order-id assignment and error-streak counting can be observed without touching the network.
- **`KalshiAPIError` paths.** `reference/market_maker.py:243-246, 259-261, 356-358, 479-481` show the four call sites that catch the typed error. Each kill-switch test (`src/quoting/kill_switches.py`, `roadmap.md` §4.6) needs to inject a raised `KalshiAPIError` and verify that the API-error switch trips and all resting quotes are cancelled.
- **OCR / vision parser.** `roadmap.md` §3.3 ports `vision_parser.py` into `src/ingestion/ocr.py`. Tests must mock the frame-grab + tesseract/CNN inference path; checking real OCR accuracy is a separate offline calibration job, not a unit test.
- **Scoreboard scrapers.** `roadmap.md` §3.2 reuses `vlr_scraper.py` / `rib_scraper.py` patterns. Mock at the HTTP layer (e.g. `responses` or `httpx.MockTransport`) — never hit the real endpoints from a unit test.
- **Twitter / Discord listeners.** `roadmap.md` §3.4. Mock the streaming client.
- **Wall-clock time.** Anything involving the staleness kill switch (`KILL_STALENESS_S = 5.0`, `CLAUDE.md` "Domain constants") or the quote TTL (`reference/market_maker.py:67`) must inject a clock or `monkeypatch.setattr(time, "time", lambda: …)`. Do not write tests that `time.sleep()` real seconds.

### What NOT to mock

- **Pure math functions.** `src/pricing/dp.py`, `src/pricing/blend.py`, `src/pricing/round_types.py` are deterministic functions of their inputs. Test directly with concrete numbers; no mocking needed and no fixtures beyond the function arguments.
- **`src/sizing/kelly.py`.** Same — pure function (`roadmap.md` §4.5).
- **`MatchState` mutations.** In-memory dataclass with `seq_id` bumps (`roadmap.md` §3.1); test by constructing real `MatchState` instances. Use `tmp_path` only for the JSONL event-log assertions.

---

## Fixtures and Factories

### Specified test data

- `data/half_win_rates.json` — checked-in fixture (kept by `.gitignore` exception `!data/half_win_rates.json`). Real production input; can be loaded once per session for tests of `_get_rate` / `live_theo` against realistic distributions.
- `models/dp_table.pkl` — generated by `scripts/build_dp_table.py` (`roadmap.md` §1.1, "Run commands" in `CLAUDE.md`). Tests for `src/pricing/dp.py` should be able to run **without** this file (pure recursion + `lru_cache` works cold) but a session-scoped fixture should pre-warm it for `live_theo` integration tests.

### Factories

- **`[gap]`** No factory library specified. `MatchState` (`roadmap.md` §3.1, ~13 fields) is the most-constructed object; a `make_match_state(**overrides)` helper in `tests/conftest.py` will keep call sites short.
- **`[gap]`** No `freezegun` or `time-machine` is mentioned. If injecting wall-clock time (see "Mocking" above) gets repetitive, add one — but `monkeypatch` is enough for now.

### Location

- **Specified (implicit):** `tests/conftest.py` for shared fixtures, `tests/<package>/conftest.py` for package-scoped fixtures. Standard pytest layout.

---

## Coverage

### Requirements

- **Specified target:** "Aim for 80% line coverage on `src/pricing/`" (`roadmap.md` §5.1). No target stated for `src/state/`, `src/ingestion/`, `src/quoting/`, `src/sizing/`.
- **`[gap]`** No coverage gate enforced anywhere — no CI, no pre-commit, no `--cov-fail-under` configured in `pyproject.toml`. The 80% number is aspirational until CI lands.

### View coverage

```bash
# Specified — not yet runnable
uv run pytest --cov=src --cov-report=term-missing
uv run pytest --cov=src/pricing --cov-report=html  # for the math layer specifically
```

---

## Test Types

### Unit tests

- **Scope:** Single function or single class method. Heaviest concentration on `src/pricing/` (the math layer must be bulletproof since `mypy --strict` and the 80% coverage target both apply only here).
- **Approach:** Plain pytest functions, deterministic inputs, exact-or-approx float assertions.
- **Specified examples (`roadmap.md` §5.1):**
  - DP value is in [0, 1] for any state.
  - DP value is monotonic in `round_p`.
  - `theo_series` equals sum over outcomes derivable from `theo_map[]`.
  - Bradley-Terry blend is symmetric: `round_p(a, b) == 1 - round_p(b, a)`.
- **Specified Bradley-Terry test cases (`roadmap.md` §1.2):**
  - `round_p(0.5, 0.5) == 0.5`.
  - `round_p(0.7, 0.3) ≈ 0.84` (compounding edge).
  - `round_p(1.0, 0.0) == 1.0` (degenerate edge).
- **Specified DP test (`roadmap.md` §1.1):** "for any `state`, `0 ≤ value ≤ 1`. For symmetric inputs (equal `round_p` across all states), value equals the closed-form `p²(3-2p)` from `fair_value.py`." — i.e. cross-check the generalized DP against `reference/fair_value.py:77-79` `_bo3_series_prob` for the `(0,0,…,start)` state.

### Property-based tests (hypothesis)

- **Specified:** `hypothesis` for the four properties listed under "Unit tests" above (`roadmap.md` §5.1).
- **Strategy approach:** `st.floats(min_value=0.01, max_value=0.99)` for round probabilities (matching the `[0.01, 0.99]` clip from `CLAUDE.md` rule 6); `@given` decorators on test functions; use `@settings(max_examples=…)` sparingly to keep the suite fast.
- **Symmetry property:** Bradley-Terry must satisfy `round_p(a, b) + round_p(b, a) == 1` for all `a, b ∈ (0.01, 0.99)`. This is `roadmap.md` §5.1's last bullet rephrased.

### Integration tests

- **Scope:** `live_theo(state) → TheoOutput` end-to-end (`roadmap.md` §1.6) — exercises `src/pricing/dp.py`, `blend.py`, `round_types.py`, `round_conclusion.py`, and `src/config/constants.py` together. Realistic `MatchState` inputs from a checked-in fixture.
- **Quoting integration:** `KalshiOrderManager` + `MarketMaker` + `MatchState` + `live_theo` driven by a synthetic event stream, with the Kalshi client mocked. Verifies that mode flips (`src/quoting/mode.py`, `roadmap.md` §4.2) fire on the right `MatchState` transitions and that all four kill switches (`roadmap.md` §4.6) trip on their respective triggers.

### Backtest

- **Specified (`roadmap.md` §5.2):** Replay past season's matches against `live_theo` running on synthetic state derived from `match_round_data`. Compute Brier score per state-bucket (early-game, mid-game, post-plant, etc.). No fills — this validates the model alone.
- **Approach:** A `scripts/backtest.py` (not yet written) that streams historical events into `MatchState` and records `theo_series` at each tick. Output is a Brier histogram, not pass/fail.
- **Note:** Kalshi does not expose historical order-book replay (`roadmap.md` §5.2). Order-fill backtest is **explicitly skipped** in favor of paper trading; no test should attempt to replay against historical fills.

### Paper trading (validation gate)

- **Specified (`roadmap.md` §5.3):** Run the full bot with `dry_run=True` against live Kalshi matches. Track:
  - Hypothetical fills.
  - Hypothetical P&L.
  - Realized Brier score per round prediction.
  - Latency p50, p99 from event → quote.
- **Promotion gate:** ≥ 1 full event with Brier < 0.22 and zero kill-switch trips for ingestion bugs (model-trip kill switches are OK; bug-trip kill switches are not).
- **`[gap]`** No metrics-collection harness exists. The latency instrumentation pattern is sketched in `roadmap.md` §3.6 — every event should carry timestamps `t_observed`, `t_ingested`, `t_arbited`, `t_state_committed`, `t_theo_computed`, `t_quote_sent` — but no module owns the rollup yet.

### Calibration loop (post-launch)

- **Specified (`roadmap.md` §5.4):** After 100 matches of paper-trade data:
  - Re-fit `SHRINK_PRIOR` to minimize live Brier.
  - Re-tune `VEGA_DIRECTIONAL_THRESHOLD` against observed mode-flip optimality.
  - Re-tune kill-switch thresholds against observed false-positive rate.
- **Approach:** `scripts/calibrate.py` (not yet written) reading from the JSONL event log + paper-trade Brier history. Updates `src/config/constants.py` directly via PR — calibration is offline, never autonomous.

### E2E tests

- **Status:** Not used and not planned. The closest thing is paper trading against live Kalshi (`roadmap.md` §5.3), which is operational, not a CI test.

---

## CI / Pre-commit

- **`[gap]`** No `.github/workflows/`, no `.gitlab-ci.yml`, no `circle.yml`, no `.pre-commit-config.yaml`. The roadmap calls for CI in `roadmap.md` §6.3:
  > "CI (GitHub Actions): build Docker image, push to GHCR, run tests"
  but no workflow file has been written.
- **`[gap]`** No pre-commit hooks. When CI lands, mirror the same checks locally: `ruff check`, `ruff format --check`, `mypy --strict src/pricing`, `pytest`.
- **Recommendation for first CI PR (Phase 6 territory per `roadmap.md`):**
  1. `ruff check src tests scripts` — lint must pass.
  2. `ruff format --check src tests scripts` — format must pass.
  3. `mypy --strict src/pricing` — strict typing on the math layer (`CLAUDE.md` rule 11).
  4. `pytest --cov=src/pricing --cov-fail-under=80` — coverage gate matches `roadmap.md` §5.1.
  5. Docker build — non-blocking until Phase 6 deployment.

---

## Common Patterns

### Async testing

- **Specified status:** Not addressed in `roadmap.md` or `prd.md`. The architecture in `prd.md` §5 is presented as a synchronous pipeline `[Ingestion] → [State Engine] → [Theo Engine] → [Quoting / Orders]` with polling intervals, not async/await.
- **`[gap]`** If `src/ingestion/` ends up using `asyncio` (multiple parallel sources at different polling rates per PRD §5.1 makes it tempting), add `pytest-asyncio` and document the convention. Until that decision is made, write synchronous tests only.

### Error testing

- **Pattern:** `pytest.raises(ValueError, match="…regex…")` for the validation errors documented in CONVENTIONS.md (e.g. the existing `raise ValueError` sites in `reference/odds_utils.py:24, 61`; `reference/fair_value.py:71, 90`; `reference/theo_engine.py:240`). When porting / rewriting the salvaged code into `src/`, write the failing-input test first.
- **Pattern:** `pytest.raises(KalshiAPIError)` for quoting-layer error paths, but always against a mocked client — never against the real Kalshi API.

### Float comparisons

- **Pattern:** `pytest.approx(expected, abs=1e-9)` or `math.isclose(actual, expected, abs_tol=1e-9, rel_tol=1e-9)`. The DP and Bradley-Terry blends are deterministic so tight tolerances are appropriate. Avoid `==` on floats anywhere in `tests/pricing/`.

### Boundary-condition tests

- **`[CLAUDE.md]` rule 6 implication:** Every clip in `src/pricing/` (the `[0.01, 0.99]` boundary) must have a boundary test: input below 0.01, input above 0.99, input exactly at the boundary. The `reference/theo_engine.py:162, 325, 375, 382, 424` clips at `[0.05, 0.95]` and `[0.03, 0.97]` are bugs to NOT carry forward; tests should pin the new bounds.

### OT hard-stop test

- **`[CLAUDE.md]` rule 5 implication:** A test must construct a `BO3State` at `total = 23` (one round before the OT boundary) and verify that the DP terminates at `total = 24` with the documented OT-as-coinflip leaf rather than running to `range(26)` like `reference/theo_engine.py:179` does. This is the most important regression test against PRD §12.2 bug #3.

### Pistol / anti-eco tests

- **`[CLAUDE.md]` rule 4 implication:** Round 1 and round 13 must use `GUN_WIN_RATE` (not the side-baseline). Test fixture: a `MatchState` at `(round_score_a=0, round_score_b=0)` should emit a `round_p` derived from `GUN_WIN_RATE`, not from `_get_rate(...)`. Same for round 13.

---

## Test-Coverage Gaps to Watch

These are areas where the salvaged `reference/` code had bugs (PRD §12.2) that no test would have caught. The new `src/` rewrite must include explicit regression coverage for each:

| PRD §12.2 bug | Required regression test | Target module |
|---|---|---|
| Docstring drift on `series_theo_from_map_probs` | Test the formula matches the docstring exactly | `src/pricing/live_theo.py` |
| Three pricing entry points with inconsistent `signal_strength` | Single entry point exists; assert no `series_theo*` symbols exported | `src/pricing/live_theo.py` |
| Silent OT-as-coinflip past total = 24 | DP terminates at total = 24; OT leaf is documented constant | `src/pricing/dp.py` |
| Arithmetic-mean round blend | Bradley-Terry assertions per `roadmap.md` §1.2 | `src/pricing/blend.py` |
| Constant `p1`/`p2` ignoring pistol/anti-eco | Round 1/13 use `GUN_WIN_RATE`; rounds 2/3/14/15 use anti-eco lookup | `src/pricing/round_types.py` |
| `series_theo_no_sides` averages atk/def starts | New code uses realized veto outcome; no side-averaging code path | `src/pricing/live_theo.py` |
| Hardcoded `[0.05, 0.95]` / `[0.03, 0.97]` clips | Boundary tests pin `[0.01, 0.99]` from `src/config/constants.py` | `src/pricing/` |

---

*Testing analysis: 2026-04-27*
