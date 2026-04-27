# Coding Conventions

**Analysis Date:** 2026-04-27

> **State of the repo:** `src/**` is currently scaffolding only — every package directory under `src/` (`pricing/`, `state/`, `ingestion/`, `quoting/`, `sizing/`, `config/`) contains a single `.gitkeep` and no Python. The only Python in the tree is in `reference/` (read-only salvage from `thunderedge/worktrees/market-maker/backend/`). Therefore conventions below come from two distinct sources, and each rule is tagged:
>
> - **`[CLAUDE.md]`** — authoritative project rule from `CLAUDE.md` / `prd.md` / `roadmap.md`. Must be followed by all new code under `src/`.
> - **`[reference/]`** — observed style in `reference/*.py`. May be reused as a starting point for new code, but `reference/` is read-only and its bugs (PRD §12.2) must not be carried forward. Where it conflicts with `[CLAUDE.md]`, `[CLAUDE.md]` wins.
> - **`[gap]`** — not yet defined anywhere in the repo. Decide before first PR in this area lands.

---

## Naming Patterns

### Files

- **`[CLAUDE.md]`** Module names per `roadmap.md` §1.1–§4.7 are lowercase with underscores: `dp.py`, `blend.py`, `round_types.py`, `round_conclusion.py`, `live_theo.py`, `match_state.py`, `order_manager.py`, `kill_switches.py`. One module per concern.
- **`[CLAUDE.md]`** Constants live in exactly one place: `src/config/constants.py` (`CLAUDE.md` rule 12, `roadmap.md` §0.4).
- **`[CLAUDE.md]`** One-off probes and calibration runs go in `scripts/` with descriptive verb-prefixed names: `scripts/probe_round_events.py`, `scripts/build_dp_table.py` (`CLAUDE.md` "Run commands", `roadmap.md` §2.1).
- **`[reference/]`** Existing salvage uses lowercase-with-underscores (`odds_utils.py`, `fair_value.py`, `theo_engine.py`, `market_maker.py`). Consistent with the rule above.

### Functions

- **`[reference/]`** `snake_case` throughout. Public API functions are bare names (`series_fair_value`, `compute_fair_values`, `quote_prices`, `american_to_implied_prob`). Private helpers are prefixed with a single leading underscore (`_signal_strength`, `_get_rate`, `_round_win_prob`, `_markov_map_win`, `_solve_map_win_prob`, `_compute_quotes`, `_place_quote`, `_cancel_quote`, `_quotes_are_stale`, `_is_near_close`, `_parse_teams_from_title`, `_bo3_series_prob`, `_bo3`).
- **`[CLAUDE.md]`** The single canonical pricing entry point is `live_theo(state) -> TheoOutput` (`CLAUDE.md` rule 1, `roadmap.md` §1.6). Do not introduce parallel `series_theo_*` variants — that triplet in `reference/theo_engine.py` lines 281, 330, 390 is the bug being rewritten.

### Variables

- **`[reference/]`** `snake_case` for locals and parameters. Domain-meaningful short names are common in math sections: `p`, `q`, `a`, `b`, `mid`, `lo`, `hi`, `dp`, `dw`, `p1`, `p2`, `p3` (e.g. `reference/theo_engine.py:161`, `reference/fair_value.py:93-99`). Acceptable inside tight numerical blocks where the surrounding docstring/comment defines the symbol.
- **`[reference/]`** Module-level "constants" use `UPPER_SNAKE_CASE` (`REGULATION_HALF`, `WIN_THRESHOLD`, `SHRINK_PRIOR`, `SIGNAL_SCALE`, `MIN_ROUNDS_FULL_WEIGHT`, `PICKBAN_DELTA` — `reference/theo_engine.py:34-38`, `reference/fair_value.py:105`).
- **`[reference/]`** Class-private constants are `_UPPER_SNAKE_CASE` with a leading underscore (`_QUOTE_TTL`, `_THEO_MOVE_CANCEL`, `_CLOSE_BUFFER_MINUTES`, `_MAX_ERRORS_BEFORE_PAUSE`, `_ERROR_PAUSE_SECONDS` — `reference/market_maker.py:67-75`).
- **`[CLAUDE.md]`** Per `CLAUDE.md` rule 12, the class-private constant pattern from `market_maker.py` is **not** acceptable for new code: every threshold must live in `src/config/constants.py`, not as a class attribute.

### Types

- **`[reference/]`** PascalCase for classes and dataclasses (`TheoEngine`, `MarketMaker`, `Quote` — `reference/theo_engine.py:58`, `reference/market_maker.py:35,53`).
- **`[CLAUDE.md]`** `roadmap.md` §1.6 specifies `TheoOutput` (PascalCase dataclass), `roadmap.md` §3.1 specifies `MatchState` (PascalCase dataclass). Follow that pattern: PascalCase dataclasses for all state/output structs.

---

## Code Style

### Formatting

- **`[CLAUDE.md]`** `roadmap.md` §0.2 specifies `ruff` for both lint and format. **`[gap]`** No `ruff.toml`, `pyproject.toml`, or any other ruff configuration exists yet. Add one before the first `src/` PR; ruff defaults are an acceptable starting point.
- **`[reference/]`** 4-space indent. Lines mostly under 100 cols; longer lines are wrapped via parenthesised expressions, not backslash continuations (e.g. `reference/theo_engine.py:179-181`, `reference/market_maker.py:217-221`).
- **`[reference/]`** Two blank lines between top-level definitions; one blank line between methods (PEP 8 standard). Banner comments demarcate sections within a file: `# ── Vig removal ───` (`reference/fair_value.py:47`), `# --- Fetch market ---` (`reference/market_maker.py:352`). Section banners are optional but match the salvaged style; do not introduce competing styles.
- **`[reference/]`** Single quotes and double quotes are mixed across the salvaged files (`'atk'` in `theo_engine.py`, `"yes"` in `market_maker.py`). New code should pick one — ruff/black defaults to double; fine.

### Linting

- **`[CLAUDE.md]`** `ruff` handles lint + format (`roadmap.md` §0.2). One tool, fast.
- **`[CLAUDE.md]`** `mypy --strict` on `src/pricing/` only (`CLAUDE.md` rule 11, `roadmap.md` §0.2). The math layer must type-check fully; other layers (`ingestion/`, `quoting/`, `state/`, `sizing/`) are gradual-typed.
- **`[gap]`** No `mypy.ini`, `pyproject.toml [tool.mypy]`, or `ruff.toml` exists. Both must be created before the first Phase 1 PR.
- **`[gap]`** No pre-commit hook config (`.pre-commit-config.yaml` absent). Add one that runs `ruff check`, `ruff format --check`, and `mypy src/pricing` before the team grows beyond one person.

### Type hints

- **`[reference/]`** Function signatures are fully annotated for parameters and return types in all four salvaged files (`reference/odds_utils.py:7,37,70,92,124`; `reference/fair_value.py:49,56,77,82,108,169,174`; `reference/theo_engine.py:66,84,104,131,146,168,208,225,259,281,330,390`; `reference/market_maker.py:77,104,206,248,263,270,280,300,320,442,458`).
- **`[reference/]`** Return tuples are typed as `Tuple[float, float, str]` etc. (`reference/theo_engine.py:288,336,396`). Newer Python 3.11 syntax `tuple[float, float, str]` is also used (`reference/odds_utils.py:37`, `reference/fair_value.py:174`).
- **`[CLAUDE.md]`** `roadmap.md` §0.2 pins Python 3.11. Prefer 3.11+ built-in generics (`list[str]`, `dict[str, float]`, `tuple[int, int]`, `X | None`) over `typing.List`/`Dict`/`Tuple`/`Optional` in new code. The `typing` imports in `reference/theo_engine.py:23` and `reference/market_maker.py:23` reflect older code and need not be replicated.
- **`[CLAUDE.md]`** Under `mypy --strict`, every function in `src/pricing/` must have annotated parameters AND an annotated return type, no `Any`, no implicit `Optional`, no untyped decorators. Plan accordingly.

---

## Import Organization

### Order

- **`[reference/]`** Standard library first, then third-party, then local — separated by a blank line. Examples:
  - `reference/theo_engine.py:20-23` — `json`, `math`, `os`, then `from typing import …`.
  - `reference/market_maker.py:17-26` — stdlib block, blank line, then `from scraper.kalshi_client import …` and `from backend.theo_engine import …`.
  - `reference/fair_value.py:39-44` — `from __future__ import annotations`, blank, stdlib, blank, `from typing import …`.
- **`[CLAUDE.md]`** Local imports in new code use the `src.` package prefix per `CLAUDE.md` "Run commands" (`python -m src.main`). Cross-package imports look like `from src.config.constants import GUN_WIN_RATE`, not relative imports. Consistency with the `src/` package layout (`CLAUDE.md` "Repo layout") is required.

### Path aliases

- None used. No alias mechanism is configured and none is needed; `src/` is the single import root.

### `__future__` imports

- **`[reference/]`** `from __future__ import annotations` appears in `reference/fair_value.py:39` but not in the other three salvaged files. **`[gap]`** Pick one rule for new code. Recommendation: include it everywhere in `src/` for forward compatibility and to allow forward-referenced type hints in `dataclass` fields without quoting.

---

## Error Handling

- **`[reference/]`** Domain-validation errors raise `ValueError` with a message that names the offending input:
  - `reference/odds_utils.py:24` — `raise ValueError("Odds cannot be zero")`
  - `reference/odds_utils.py:61` — `raise ValueError("Total probability cannot be zero")`
  - `reference/fair_value.py:71` — `raise ValueError(f"Invalid odds: {team_a_odds} / {team_b_odds}")`
  - `reference/fair_value.py:90` — `raise ValueError(f"series_prob must be in (0,1), got {series_prob}")`
  - `reference/theo_engine.py:240` — `raise ValueError('map_pool must have at least 2 maps')`
- **`[reference/]`** Missing-resource errors raise `FileNotFoundError` with a remediation hint pointing at the script that produces the file (`reference/theo_engine.py:69-72`).
- **`[reference/]`** External API calls catch the typed exception (`KalshiAPIError`), log, and increment an error-streak counter rather than re-raising — see `reference/market_maker.py:243-246, 259-261, 356-358, 479-481`. Bare `except Exception:` is used only at the top of the run loop to keep the bot alive across one bad market (`reference/market_maker.py:493-496`).
- **`[reference/]`** A swallowed exception around timestamp parsing returns a safe default (`reference/market_maker.py:313-314`). Acceptable for pure-input parsing where the worst case is "treat market as not-near-close."
- **`[CLAUDE.md]`** New `src/quoting/` code must additionally trigger the four kill switches (`CLAUDE.md` rule 9, PRD §5.4): Kalshi API errors, ingestion staleness > 5s, |theo - market| > 20¢, rolling Brier > 0.30 over 50 rounds. The `_error_streak`/`_ERROR_PAUSE_SECONDS` pattern from `reference/market_maker.py:73-75, 362-369` is the seed for the API-error switch only — staleness, deviation, and Brier need fresh implementations under `src/quoting/kill_switches.py` (`roadmap.md` §4.6).

---

## Logging

- **`[reference/]`** `logging` from the standard library, one module-level logger per file: `logger = logging.getLogger(__name__)` (`reference/fair_value.py:44`, `reference/theo_engine.py` does not log, `reference/market_maker.py:28`).
- **`[reference/]`** `%`-style format strings, **not** f-strings, in log calls — args passed positionally so the formatter can defer string construction:
  - `reference/market_maker.py:217-221` — `logger.info("[DRY-RUN] Would place order: %s %s %s @ %dc x%d", quote.ticker, …)`.
  - `reference/market_maker.py:235-240, 257, 261, 397-401, 468-471`.
  - `reference/fair_value.py:162-165` — `logger.debug("fair_value: series=%.3f …", series_prob, map_p, …)`.
- **`[reference/]`** Log levels in use:
  - `debug` for routine per-tick decisions and quoting math (e.g. `reference/market_maker.py:134, 170, 195, 405, 410`).
  - `info` for state changes the operator should see (placed orders, cancelled orders, market open/close, run-loop start) (e.g. `reference/market_maker.py:217, 235, 253, 257, 372, 377, 397, 468, 485`).
  - `warning` for recoverable degradations (couldn't cancel an order, error-streak pause) (e.g. `reference/market_maker.py:261, 363-366, 500-503`).
  - `error` for failed operations (`reference/market_maker.py:245, 358, 481`).
  - `exception` (with traceback) for unexpected exceptions in the main loop (`reference/market_maker.py:494`).
- **`[reference/]`** Dry-run output is prefixed `[DRY-RUN]` in the log message itself (`reference/market_maker.py:218, 253`). Continue this convention so production logs are visually unambiguous.
- **`[CLAUDE.md]`** `roadmap.md` §6.5 specifies "structured JSON logs to stdout, captured by Docker." **`[gap]`** No structured-logging library is wired in yet. Recommendation for Phase 6: introduce `python-json-logger` or wire `logging.Formatter` to emit JSON. Until then, stdlib `logging` per the salvaged pattern is fine for Phases 1–5.
- **`[reference/]`** Smoke-test scripts at the bottom of modules use `logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")` inside `if __name__ == "__main__":` (`reference/fair_value.py:204-205`). Do not call `basicConfig` from library modules.

---

## Comments

### When to comment

- **`[reference/]`** Inline comments explain *why* and the *math*, not what the code is doing mechanically. Examples:
  - `reference/theo_engine.py:99-100` — explains the shrinkage math and what changing `n` does.
  - `reference/market_maker.py:139-140` — explains the contract-sizing intent.
  - `reference/market_maker.py:146, 161` — explain the trading direction implied by each branch.
  - `reference/fair_value.py:34-37` — explains the `0.04` PICKBAN_DELTA choice and that it can be tuned.
- **`[reference/]`** Long-form rationale lives in module-level docstrings, not at the top of functions (see "Docstrings" below).
- **`[CLAUDE.md]`** Any threshold or magic number that needs a "TBD — calibrate later" note (e.g. `VEGA_DIRECTIONAL_THRESHOLD`, `PER_MARKET_CAP_FRAC`) gets the comment in `src/config/constants.py` next to its definition (`roadmap.md` §0.4 shows the pattern). **Never** in business logic per `CLAUDE.md` rule 12.

### Docstrings

- **`[reference/]`** Module-level docstrings are mandatory and substantial:
  - `reference/fair_value.py:1-37` — full math derivation including the IID BO3 model and the inversion target.
  - `reference/theo_engine.py:1-18` — describes the four-step pricing pipeline and the rate-fallback chain.
  - `reference/market_maker.py:1-15` — names the risk controls enforced.
  - `reference/odds_utils.py:1-5` — short module docstring; acceptable for a small utility module.
- **`[reference/]`** Function docstrings use plain prose with explicit `Args:`/`Returns:`/`Examples:` sections — Google-style. See `reference/odds_utils.py:7-22`, `reference/odds_utils.py:37-67`, `reference/theo_engine.py:84-91, 104-112, 281-303`. No reStructuredText, no Sphinx markers.
- **`[reference/]`** `Examples:` sections include inline expected outputs (`reference/odds_utils.py:17-21, 51-53, 81-84, 107-111`). Useful as cheap doctests, though no doctest runner is configured.
- **`[reference/]`** Class docstrings document constructor `Args:` (`reference/theo_engine.py:59-64`, `reference/market_maker.py:54-64`).
- **`[CLAUDE.md]`** When carrying anything over from `reference/theo_engine.py`, fix the docstring drift documented in PRD §12.2 (line 343-348 of the original — the docstring lies about the formula). Code and docstring must agree in `src/`.

---

## Function Design

### Size

- **`[reference/]`** Functions are typically 5–40 lines. The two largest in the salvage are `_compute_quotes` (~95 lines, `reference/market_maker.py:104-200` — heavy branching for quote placement) and `update_market` (~115 lines, `reference/market_maker.py:320-436` — orchestrates a full quoting cycle). Both have clear linear flow segmented by `# ---` banner comments.
- **`[CLAUDE.md]`** No explicit cap. The "one canonical implementation per concept" preference (`CLAUDE.md` Preferences) implies preferring decomposition over duplication when a function grows beyond ~50 lines.

### Parameters

- **`[reference/]`** Positional for the obvious required inputs; keyword arguments with defaults for tuning knobs:
  - `reference/theo_engine.py:66` — `__init__(self, rates_path: str = _DEFAULT_RATES_PATH)`.
  - `reference/market_maker.py:77-85` — eight init params, six with defaults including `dry_run: bool = True`.
  - `reference/fair_value.py:108-112` — `pickban_adjust: bool = True` as keyword default.
- **`[reference/]`** Long parameter lists wrap one-per-line with the closing paren and return type on a new line (`reference/theo_engine.py:281-288, 330-336, 390-396`; `reference/market_maker.py:104-110, 320-329`).
- **`[CLAUDE.md]`** Per `CLAUDE.md` "Differences from `thunderedge/CLAUDE.md`": dry-run is a CLI flag at the entry point (`python -m src.main --match <ticker>` defaults to dry, `--live` opts in), **not** a constructor argument. Do not replicate the `dry_run: bool = True` constructor pattern from `reference/market_maker.py:84` in new `src/quoting/` code — pass it down from `main.py` after CLI parsing.

### Return values

- **`[reference/]`** Single scalar where natural (`reference/fair_value.py:56,82`; `reference/odds_utils.py:7,70,92`).
- **`[reference/]`** Tuple of related scalars when callers always need both (`reference/odds_utils.py:37` returns `(p_over_vigfree, p_under_vigfree)`; `reference/theo_engine.py:281` returns `(final_theo, data_w, conf)`; `reference/fair_value.py:174` returns `(yes_bid_cents, yes_ask_cents)`).
- **`[reference/]`** `dict` for grouped optional outputs from a high-level helper (`reference/fair_value.py:108` returns a 5-key dict). Acceptable for orchestration outputs but not for low-level math.
- **`[CLAUDE.md]`** New high-level outputs use `@dataclass` instead of dict — `roadmap.md` §1.6 specifies `TheoOutput` as a dataclass with fields `theo_series`, `theo_map`, `vega`, `confidence`. Type-checkability under `mypy --strict` requires this.

---

## Module Design

### Exports

- **`[reference/]`** No `__all__` declared; everything not prefixed with `_` is implicitly public. Continue this — explicit `__all__` is unnecessary noise unless wildcard imports are used (they are not).
- **`[reference/]`** Modules expose either a class (`TheoEngine`, `MarketMaker`) plus optional helpers, or a flat collection of functions (`odds_utils.py`, `fair_value.py`).

### Barrel files

- **`[reference/]`** None observed. The salvaged code imports specific names from specific modules (`from backend.theo_engine import TheoEngine` — `reference/market_maker.py:26`).
- **`[CLAUDE.md]`** Recommend keeping it that way — no `src/pricing/__init__.py` re-exports. `mypy --strict` and ruff are easier to reason about with explicit module paths, and it matches the "one canonical implementation per concept" preference.

### Smoke-test blocks

- **`[reference/]`** Three of four salvaged files end with `if __name__ == "__main__":` smoke tests that exercise the module's main API with hard-coded inputs and `print()` results (`reference/odds_utils.py:144-176`; `reference/fair_value.py:202-227`). Useful for hand-verification during development.
- **`[CLAUDE.md]`** For new code, prefer dedicated `scripts/` runners (per `CLAUDE.md` "Repo layout" — `scripts/` is for "one-off probes, calibration runs"). Smoke blocks at module bottom are tolerable for tiny utility modules but do not substitute for `tests/` (see TESTING.md).

---

## Project-Wide Critical Rules (from `CLAUDE.md`)

These are the rules every PR is graded against. Repeated here so a single document covers conventions:

| # | Rule | Source | Layer |
|---|------|--------|-------|
| 1 | Single canonical entry point: `live_theo(state) → (theo, vega, confidence)`. No `series_theo` triplet. | `CLAUDE.md` rule 1 | `src/pricing/` |
| 2 | BO3 series and per-map theos come from the same DP. | `CLAUDE.md` rule 2 | `src/pricing/` |
| 3 | Bradley-Terry round blend: `p = a*(1-b) / (a*(1-b) + (1-a)*b)`. Not arithmetic mean. | `CLAUDE.md` rule 3 | `src/pricing/blend.py` |
| 4 | Pistol + anti-eco modeled explicitly for rounds 1, 2, 3, 13, 14, 15. | `CLAUDE.md` rule 4 | `src/pricing/round_types.py` |
| 5 | OT is an explicit hard-stop at total = 24 with a documented OT-as-coinflip leaf. | `CLAUDE.md` rule 5 | `src/pricing/dp.py` |
| 6 | Conviction clips at `[0.01, 0.99]`. Not `[0.05, 0.95]` (the `reference/theo_engine.py:162, 325, 375, 382, 424` value). Document any tighter clip. | `CLAUDE.md` rule 6 | `src/pricing/` |
| 7 | Half-Kelly with per-market cap. `f = 0.5 × kelly_full`, capped at `PER_MARKET_CAP_FRAC`. Never full Kelly. | `CLAUDE.md` rule 7 | `src/sizing/kelly.py` |
| 8 | Hybrid mode: event-trigger with vega override. MM by default; flip to directional on listed events or vega > threshold. | `CLAUDE.md` rule 8 | `src/quoting/mode.py` |
| 9 | All four kill switches always-on (API errors, staleness > 5s, |theo − market| > 20¢, rolling Brier > 0.30 over 50 rounds). No flag to disable individual switches. | `CLAUDE.md` rule 9 | `src/quoting/kill_switches.py` |
| 10 | Tiered ingestion confirmation per PRD §5.1. Score updates need ≥ 2 sources within 2s. | `CLAUDE.md` rule 10 | `src/ingestion/arbiter.py` |
| 11 | `mypy --strict` on `src/pricing/`. The math layer must type-check. | `CLAUDE.md` rule 11 | `src/pricing/` |
| 12 | No magic numbers in business logic. Every threshold lives in `src/config/constants.py`. | `CLAUDE.md` rule 12 | All `src/` |
| 13 | Dry-run by default. Live trading requires explicit `--live` flag at the entry point. | `CLAUDE.md` rule 13 | `src/main.py` (entry point) |

---

## Authoritative Constants

All thresholds below MUST live in `src/config/constants.py` per `CLAUDE.md` rule 12. Listed here for convention reference; do not duplicate in business logic.

```python
# Pricing                              # Source
SHRINK_PRIOR              = 15.0       # CLAUDE.md "Domain constants"; reference/theo_engine.py:37
SIGNAL_SCALE              = 0.10       # CLAUDE.md; reference/theo_engine.py:38
GUN_WIN_RATE              = 0.822      # CLAUDE.md; pistol-win modeling, prd.md §6 Tier 1
REGULATION_HALF           = 12         # CLAUDE.md; reference/theo_engine.py:34
WIN_THRESHOLD             = 13         # CLAUDE.md; reference/theo_engine.py:35

# Sizing
KELLY_MULTIPLIER          = 0.5        # CLAUDE.md rule 7
PER_MARKET_CAP_FRAC       = 0.05       # CLAUDE.md; TBD — depends on bankroll (prd.md §9.1)

# Kill switches (all always-on, no disable flags)
KILL_STALENESS_S          = 5.0        # CLAUDE.md rule 9, PRD §5.4
KILL_DEVIATION_C          = 20         # CLAUDE.md rule 9, PRD §5.4
KILL_BRIER_BOUND          = 0.30       # CLAUDE.md rule 9, PRD §5.4
KILL_BRIER_WINDOW         = 50         # CLAUDE.md rule 9, PRD §5.4

# Mode flip
VEGA_DIRECTIONAL_THRESHOLD = 0.04      # CLAUDE.md; TBD — calibrate after 20+ matches
```

Naming convention for these constants: `UPPER_SNAKE_CASE`. The `KILL_SWITCH_*` prefix used in `roadmap.md` §0.4 (e.g. `KILL_SWITCH_STALENESS_S`) and the shorter `KILL_*` form in `CLAUDE.md` "Domain constants" are inconsistent in the source documents — **`[gap]`** pick one in the first PR that creates `src/config/constants.py`. Recommendation: drop the `_SWITCH` for brevity, matching `CLAUDE.md`.

---

## Anti-Patterns to Avoid

These are observed in `reference/` and explicitly called out in `CLAUDE.md` / PRD §12.2 as bugs to NOT carry over:

1. **Multiple pricing entry points with inconsistent math.** `reference/theo_engine.py:281, 330, 390` — `series_theo`, `series_theo_from_map_probs`, `series_theo_no_sides` apply `_signal_strength` inconsistently. New code: one `live_theo`, period.
2. **Arithmetic-mean round blend.** `reference/theo_engine.py:161` — `(a_rate + (1.0 - b_rate)) / 2.0`. Use Bradley-Terry instead.
3. **Hardcoded `[0.05, 0.95]` and `[0.03, 0.97]` clips.** `reference/theo_engine.py:162, 325, 375, 382, 424`; `reference/fair_value.py:139-144`. Use `[0.01, 0.99]`, sourced from `src/config/constants.py`.
4. **OT-as-coinflip running silently.** `reference/theo_engine.py:179, 194` — DP loop runs `range(WIN_THRESHOLD * 2) = range(26)` and silently uses `p = 0.5` past round 24. New code: explicit hard-stop at total = 24 with a documented OT-coinflip leaf.
5. **Constant `p1`/`p2` per half.** `reference/theo_engine.py:189-194` — same probability for rounds 1-12 and same for 13-24. Ignores pistol and anti-eco (`CLAUDE.md` rule 4).
6. **Class-attribute thresholds.** `reference/market_maker.py:67-75` defines `_QUOTE_TTL`, `_THEO_MOVE_CANCEL`, `_CLOSE_BUFFER_MINUTES`, `_MAX_ERRORS_BEFORE_PAUSE`, `_ERROR_PAUSE_SECONDS` on the class. Move to `src/config/constants.py` per `CLAUDE.md` rule 12.
7. **`dry_run` as a constructor argument.** `reference/market_maker.py:84` — `dry_run: bool = True` on the class. New code: CLI flag at the entry point only (`CLAUDE.md` rule 13 and "Differences from `thunderedge/CLAUDE.md`").
8. **Mutating `self.quote_width` then restoring.** `reference/market_maker.py:417-425` — saves, mutates, restores `self.quote_width` and `self.max_position` mid-call. Not thread-safe and surprising. New code: pass overrides as parameters.
9. **`_parse_teams_from_title` regex.** `reference/market_maker.py:442-456` — fragile screen-scrape of the Kalshi market title. New code: pass team names through explicitly from the match-state engine; never parse them out of the ticker title.

---

*Convention analysis: 2026-04-27*
