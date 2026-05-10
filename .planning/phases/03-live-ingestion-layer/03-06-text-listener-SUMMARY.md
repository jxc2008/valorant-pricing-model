---
phase: 03-live-ingestion-layer
plan: "06"
subsystem: ingestion
tags: [twitter, tweepy, async-streaming, soft-confirm, degrade-to-no-op, dec-006-v2, req-text-listener, env-gate]

requires:
  - phase: 03-live-ingestion-layer
    provides: 03-00 RED xfail stubs in tests/ingestion/test_text_listener.py + arbiter_with_stub_sources fixture; 03-01 src/state v2 MatchState with bomb_planted / attackers_alive / defenders_alive / time_left_s / seq_id; 03-03 src/ingestion Arbiter with score_changes deque + >=2-source rule + _DEQUE_MAX_AGE_S=3s quarantine path + tick() + JSONL bridge
provides:
  - "src/ingestion/text_listener.py — tweepy.asynchronous.AsyncStreamingClient-based listener (~150 LOC) with TWITTER_BEARER_TOKEN env-gate degrading to no-op + score-signal regex (\\d{1,2}\\s*[-:]\\s*\\d{1,2}) parsing tweet text into PendingEvent(source=twitter, event_type=score_change) records pushed to arbiter.score_changes."
  - "run_text_listener(arbiter) async coroutine — env-gated entry point. Empty / whitespace-only TWITTER_BEARER_TOKEN -> logger.warning + immediate return (RESEARCH Pitfall 1). Token present -> _MatchSignalListener constructed, static rules synced from TWITTER_RULE_SET (try/except for transient API failures), listener.filter() blocks until TaskGroup cancellation."
  - "_MatchSignalListener subclass — overrides on_tweet(tweet: dict) to extract score signals via _parse_score (rejects scores > 13), pushes PendingEvent into arbiter.score_changes with t_observed=wall_time(), t_ingested=mono_ns()."
  - "TWITTER_API_BASE_URL='https://api.twitter.com/2' + TWITTER_RULE_SET (9 entries: 5 hashtags + 4 league/caster accounts) appended to src/config/constants.py."
  - "3 GREEN tests in tests/ingestion/test_text_listener.py replacing the Wave-0 xfail stubs: test_emits_typed_soft_events / test_twitter_only_update_quarantined / test_no_token_noop."
affects: [03-08-e2e-gate]

tech-stack:
  added: []  # tweepy>=4.14,<5 already in pyproject.toml from Wave 1
  patterns:
    - "Env-gated async coroutine pattern: degrade-to-no-op on missing env var via early return + logger.warning. Mirrors how Phase 3 systems are designed to run unaffected when optional sources are unavailable (RESEARCH Pitfall 1: Twitter Basic tier deprecation)."
    - "Soft-confirm-only ingestion source: pushes PendingEvent into arbiter.score_changes; the arbiter's >=2-source rule (DEC-006 v2 / ARBITER_SCORE_WINDOW_S=2.0) guarantees Twitter alone NEVER mutates state. Twitter-only events age past _DEQUE_MAX_AGE_S=3s and quarantine to JSONL with seq_id=null."
    - "Whitespace-only token gate (.strip() before truthiness check) — accidental blank-string secrets in CI configs degrade to no-op rather than booting a listener that immediately 401s."
    - "tweepy.asynchronous.AsyncStreamingClient import path (NOT tweepy.AsyncStreamingClient — the symbol is NOT re-exported at the tweepy top level in 4.16.x). tweepy.StreamRule IS at top level."

key-files:
  created:
    - "src/ingestion/text_listener.py — Twitter v2 streaming listener (~155 LOC). _SCORE_PATTERN regex + _MatchSignalListener subclass + run_text_listener async entry point."
  modified:
    - "src/config/constants.py — appended Phase 3 text-listener section: TWITTER_API_BASE_URL (str), TWITTER_RULE_SET (tuple of 9 entries — 5 hashtags + 4 operator-pinned 2026-season league accounts)."
    - "src/ingestion/__init__.py — re-export run_text_listener; added to __all__."
    - "tests/ingestion/test_text_listener.py — replaced 3 xfail stubs with GREEN tests per SPEC §4."
    - "tests/config/test_constants.py — added TWITTER_API_BASE_URL + TWITTER_RULE_SET to EXPECTED_NAMES + EXPECTED_TYPES (Rule-3 prophylactic same-commit pattern from Wave 3A)."

key-decisions:
  - "tweepy 4.16.x ships AsyncStreamingClient under tweepy.asynchronous (NOT at the tweepy top level the planner's <interfaces> block referenced). Researcher's import tweepy + tweepy.AsyncStreamingClient would AttributeError at module load. The fix imports AsyncStreamingClient from tweepy.asynchronous explicitly while still using tweepy.StreamRule (which IS at top level) for rule construction."
  - "Whitespace-only TWITTER_BEARER_TOKEN counts as empty (.strip() gate). The plan's body explicitly tests this case (test_no_token_noop second pass with monkeypatch.setenv('   ')) — accidental blank-string secrets in CI deployments degrade to no-op rather than 401-looping a real client against a bad credential."
  - "Tests exercise the listener via direct method calls (await listener.on_tweet({...})) rather than booting the network stream. The mocked Twitter API path is exercised through synthetic dict payloads; the rule-sync / listener.filter() code path is only entered when the token gate is satisfied, which test_no_token_noop inverts intentionally. No aioresponses needed — environment_notes 'tests should mock the Twitter API (no real network)' is satisfied by avoiding the network code path entirely."
  - "Twitter-only quarantine test exercises the staleness path (t_observed = wall_time() - 10s, older than _DEQUE_MAX_AGE_S=3s) — the alternative would have been to call tick() once with a fresh single-source event and check it stays in the deque, but that asserts hold-not-quarantine semantics; the SPEC acceptance is the stronger 'quarantined to JSONL with source=twitter' assertion which the staleness path produces directly."
  - "type: ignore[misc] localized on the AsyncStreamingClient subclass declaration. tweepy ships no type stubs, so AsyncStreamingClient resolves to Any under mypy and 'Class cannot subclass Any' fires. The ignore is the canonical fix and is scoped to the one declaration line — the rest of the file's typing remains strict."
  - "Source provenance pinned to source='twitter' (a SourceName Literal) rather than a free-form string — the arbiter's group-by-fields_proposed-signature already trips the 2-source rule on (twitter, ribgg) or (twitter, ocr_score) pairs because SourceName Literal values are distinct."

patterns-established:
  - "Optional ingestion sources degrade to no-op via env gate: Phase 3 ingestion is designed so the system runs without TWITTER_BEARER_TOKEN; the arbiter still satisfies its >=2-source rule via rib.gg + OCR. Future optional sources (e.g., bo3.gg / vlr.gg / Twitch IRC chat in Phase 5 robustness work) follow this pattern: check env -> if absent, log warning + return; if present, construct + run."
  - "Soft-confirm-only source contract: a source that pushes ONLY PendingEvent records into arbiter deques and NEVER calls src.state.commit / src.state.quarantine. The arbiter is the sole writer; sources are pure producers. text_listener follows the same shape as scoreboard.py (Wave 4A) and ocr.py (Wave 4C)."

requirements-completed: [REQ-text-listener]

# Metrics
duration: 8 min
completed: 2026-05-10
---

# Phase 3 Plan 06: Text Listener Summary

**Twitter v2 streaming text listener (REQ-text-listener) via tweepy.asynchronous.AsyncStreamingClient with TWITTER_BEARER_TOKEN env-gate degrading to no-op (RESEARCH Pitfall 1: Basic tier deprecated 2026-02-06 for new accounts), score-signal regex parsing tweet text into PendingEvent(source=twitter) soft-confirm pushes against arbiter.score_changes, and the arbiter's >=2-source rule guaranteeing Twitter alone never commits state — 3 GREEN tests replace the Wave-0 xfail stubs.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-05-10T01:47:02Z
- **Completed:** 2026-05-10T01:55:42Z
- **Tasks:** 2
- **Files modified:** 5 (1 created — src/ingestion/text_listener.py; 4 modified — src/config/constants.py, src/ingestion/__init__.py, tests/config/test_constants.py, tests/ingestion/test_text_listener.py)

## Accomplishments

- **REQ-text-listener GREEN.** SPEC §4 acceptance #6 satisfied: mocked Twitter stream emits typed soft-events; Twitter-only update quarantined to JSONL with seq_id=null + quarantined=true + source="twitter"; test_no_token_noop returns < 1s without raising.
- **RESEARCH Pitfall 1 documented + handled.** Twitter API Basic tier ($200/mo) deprecated 2026-02-06 for new accounts is documented in module docstring + TWITTER_RULE_SET docstring; the listener degrades to no-op via env gate so default CI deployments and post-2026-02-06 accounts are unaffected.
- **TWITTER_RULE_SET pinned with operator-recommended VCT 2026 hashtags + accounts.** 9 entries: 5 hashtags (#VCT, #VALORANTChampions, #VCTAmericas, #VCTEMEA, #VCTPacific) + 4 league/caster accounts (from:ValorantEsports, from:VCT_Americas, from:VCT_EMEA, from:VCT_Pacific).
- **Listener degrades to no-op on missing/whitespace-only token.** Verified by test_no_token_noop with both `monkeypatch.delenv` and `monkeypatch.setenv(name, "   ")` — both paths complete in <1s with no events pushed and no state mutation.
- **Soft-confirm-only contract structurally enforced.** text_listener pushes PendingEvent into arbiter.score_changes ONLY; the arbiter's >=2-source rule (DEC-006 v2 / ARBITER_SCORE_WINDOW_S=2.0) blocks Twitter-alone commits; stale Twitter-only events quarantine to JSONL after _DEQUE_MAX_AGE_S=3s. Twitter NEVER pushes into bomb_events / round_end_events deques (signal-quality too noisy per SPEC §5).
- **mypy src/ingestion/ + ruff src tests scripts clean.** mypy --strict src/pricing src/state still clean (9 source files). One localized `type: ignore[misc]` on the AsyncStreamingClient subclass since tweepy ships no stubs.
- **287 passed / 26 xfailed regression.** Up from 284/29 — the 3 text_listener xfails are now GREEN.

## Task Commits

1. **Task 1: Twitter constants + src/ingestion/text_listener.py with degrade-to-no-op** — `cbf2017` (feat)
2. **Task 2: GREEN test_text_listener — soft events + Twitter-only quarantine + no-token-noop** — `e25b5de` (test)

**Plan metadata commit:** to follow (this SUMMARY.md + STATE.md + ROADMAP.md + REQUIREMENTS.md update).

## Files Created/Modified

### Created
- `src/ingestion/text_listener.py` (~155 LOC) — Twitter v2 streaming listener. Module docstring documents (a) soft-confirm-only contract per SPEC §4, (b) RESEARCH Pitfall 1 permanent degradation semantics, (c) the run_text_listener surface, (d) the NEVER-do list (no bomb_events / round_end_events pushes; no construct-without-env-gate). `_SCORE_PATTERN = re.compile(r"\b(\d{1,2})\s*[-:]\s*(\d{1,2})\b")`. `_MatchSignalListener(AsyncStreamingClient)` overrides `_parse_score` (returns dict | None; rejects > 13) and `async on_tweet` (pushes PendingEvent into arbiter.score_changes). `async run_text_listener(arbiter)` env-gates on TWITTER_BEARER_TOKEN with .strip() check, syncs rules with try/except wrapping for transient API failures, awaits listener.filter().

### Modified
- `src/config/constants.py` — appended "Phase 3 — text listener (REQ-text-listener / 03-06 / 03-CONTEXT D-07)" section: `TWITTER_API_BASE_URL: Final[str] = "https://api.twitter.com/2"` (sanity anchor; not used directly), `TWITTER_RULE_SET: Final[tuple[str, ...]]` of 9 entries. Both Final-typed per CRule 12.
- `src/ingestion/__init__.py` — added `from src.ingestion.text_listener import run_text_listener` + appended "run_text_listener" to __all__ (alphabetical).
- `tests/ingestion/test_text_listener.py` — replaced 3 xfail stubs with GREEN tests. Each test uses `@pytest.mark.asyncio` and the `arbiter_with_stub_sources` conftest fixture. Direct `await listener.on_tweet({...})` invocation drives the soft-event path; `arb.score_changes.append(PendingEvent(...))` + `arb.tick()` drives the quarantine path; `monkeypatch.delenv` / `monkeypatch.setenv("   ")` drives the no-op path.
- `tests/config/test_constants.py` — added TWITTER_API_BASE_URL + TWITTER_RULE_SET to EXPECTED_NAMES (`# Phase 3 — text listener (REQ-text-listener / 03-06 / D-07)` section header) + EXPECTED_TYPES (str + tuple respectively). Rule-3 prophylactic — same-commit pattern as Wave 3A.

## Decisions Made

- **tweepy 4.16.x AsyncStreamingClient lives in tweepy.asynchronous, not at the tweepy top level.** The planner's `<interfaces>` block referenced `tweepy.AsyncStreamingClient` which AttributeErrors at module load. Fix: `from tweepy.asynchronous import AsyncStreamingClient` while still using `tweepy.StreamRule` (top-level). Verified empirically with `python -c "import tweepy.asynchronous; print(dir(tweepy.asynchronous))"`.
- **Whitespace-only TWITTER_BEARER_TOKEN counts as empty.** `.strip()` before truthiness check. The second pass of `test_no_token_noop` (`monkeypatch.setenv("TWITTER_BEARER_TOKEN", "   ")`) verifies this — accidental blank-string secrets in CI configs degrade to no-op rather than 401-looping.
- **Tests exercise listener via direct on_tweet calls, NOT a real network stream.** environment_notes "tests should mock the Twitter API (no real network)" is satisfied by avoiding the network code path entirely (the rule-sync / listener.filter() path is only entered when the token gate passes, which test_no_token_noop inverts). No aioresponses fixture needed.
- **Twitter-only quarantine asserted via the staleness path (t_observed = wall_time() - 10s).** Pushing a fresh single-source event would assert hold-not-quarantine semantics (the arbiter holds for cross-confirm, doesn't quarantine immediately); the SPEC §4 acceptance is the stronger "Twitter-only update quarantined" assertion which the 10s staleness path produces directly.
- **type: ignore[misc] localized on the `class _MatchSignalListener(AsyncStreamingClient)` declaration.** tweepy ships no stubs so AsyncStreamingClient resolves to Any; mypy fires "Class cannot subclass Any [misc]". The ignore is canonical for stubless library inheritance and is scoped to the one declaration line.
- **Source provenance is `source="twitter"` (a SourceName Literal).** The arbiter's group-by-fields_proposed-signature naturally trips the 2-source rule on (twitter, ribgg) or (twitter, ocr_score) pairs because SourceName values are distinct Literal members. No special-casing needed in the arbiter.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] tweepy 4.16.x does not expose AsyncStreamingClient at the top level.**
- **Found during:** Task 1 (text_listener.py implementation, before any test ran).
- **Issue:** The planner's `<interfaces>` block referenced `tweepy.AsyncStreamingClient` and `class _MatchSignalListener(tweepy.AsyncStreamingClient):`. Empirically: `python -c "import tweepy; print(hasattr(tweepy, 'AsyncStreamingClient'))"` -> False in 4.16.0. The symbol lives in `tweepy.asynchronous`. The plan-as-written would raise `AttributeError` at module import time, blocking every downstream consumer of `from src.ingestion import run_text_listener`.
- **Fix:** Imported `AsyncStreamingClient` from `tweepy.asynchronous`; kept `tweepy.StreamRule` at top level (which IS exposed there). Documented in module docstring "Implementation notes" so future maintainers don't re-introduce the broken import.
- **Files modified:** src/ingestion/text_listener.py.
- **Verification:** `python -c "from src.ingestion.text_listener import run_text_listener, _MatchSignalListener; print('ok')"` succeeds.
- **Committed in:** `cbf2017` (Task 1 commit).

**2. [Rule 3 - Blocking] tests/config/test_constants.py allow-list update required for new constants.**
- **Found during:** Task 1 (anticipated proactively per Wave 3A established pattern; verified with `pytest tests/config/test_constants.py` after the fix landed).
- **Issue:** Adding new uppercase constants to src/config/constants.py without updating EXPECTED_NAMES + EXPECTED_TYPES in tests/config/test_constants.py would fail `test_no_unexpected_uppercase_names_leak_in`. Wave 3A's SUMMARY documented this as a recurring same-commit fix when new constants land (CRule 12 / no-magic-numbers compliance).
- **Fix:** Added TWITTER_API_BASE_URL (str) + TWITTER_RULE_SET (tuple) to both EXPECTED_NAMES (with `# Phase 3 — text listener (REQ-text-listener / 03-06 / D-07)` section header) and EXPECTED_TYPES.
- **Files modified:** tests/config/test_constants.py.
- **Verification:** `pytest tests/config/test_constants.py -x` -> 75 passed / 0 failed.
- **Committed in:** `cbf2017` (Task 1 commit; same-commit prophylactic per Wave 3A pattern).

**3. [Rule 3 - Blocking] mypy "Class cannot subclass Any" on the AsyncStreamingClient subclass.**
- **Found during:** Task 1 verify (`mypy src/ingestion/`).
- **Issue:** tweepy ships no type stubs (no py.typed marker, no separate -stubs package). `from tweepy.asynchronous import AsyncStreamingClient` resolves to Any under mypy with `ignore_missing_imports = True` (project default). Subclassing Any fires `error: Class cannot subclass "AsyncStreamingClient" (has type "Any") [misc]`.
- **Fix:** Localized `# type: ignore[misc]` on the `class _MatchSignalListener(AsyncStreamingClient):` declaration line. This is the canonical fix for stubless library inheritance — alternative options (loosening project-wide mypy strictness, adding a custom stub file, switching to a Protocol shim) all add more cost than the one-line ignore.
- **Files modified:** src/ingestion/text_listener.py.
- **Verification:** `mypy src/ingestion/` -> "Success: no issues found in 8 source files".
- **Committed in:** `cbf2017` (Task 1 commit).

---

**Total deviations:** 3 auto-fixed (1 bug, 2 blocking).
**Impact on plan:** All 3 deviations were one-shot blocking issues surfaced during Task 1. Deviation 1 (tweepy import path) was a planner reference error that would have crashed the module at import time — caught at first smoke import. Deviations 2 and 3 followed established Wave 3A patterns (same-commit constants allow-list update; type: ignore for stubless library inheritance). None indicate a design issue; all fixes preserve plan intent.

## Authentication Gates

None. The listener is designed to degrade to no-op on missing TWITTER_BEARER_TOKEN — there is no auth gate to hit at execution time. Operators with a Basic-tier Twitter account opt in by setting the env var.

## Issues Encountered

None blocking. The listener landed straight to GREEN on the first pytest run after deviation fixes; no rule-logic bugs surfaced.

## User Setup Required

None at execution time. Operator action is OPT-IN only:
- If running with a pre-2026-02-06 Twitter API Basic-tier account: set `TWITTER_BEARER_TOKEN` env var; the listener will boot and stream.
- Default deployment: no env var set; listener degrades to no-op + logger.warning; arbiter satisfies its >=2-source rule via rib.gg + OCR cross-confirm.

## Next Phase Readiness

Plan 03-07 (ETL re-run + calibration) is unblocked — independent from text listener; Wave 4A (Plan 03-04 / scoreboard poller) and Plan 03-02 (round-conclusion v2 surface) are the upstream dependencies.

Plan 03-08 (E2E gate) is unblocked:
- `from src.ingestion import run_text_listener` resolves; the synthetic E2E test composes the listener via `asyncio.TaskGroup` alongside `run_scoreboard_poller`, the 4 OCR workers, and the arbiter.tick() driver.
- The E2E test runs without TWITTER_BEARER_TOKEN set (default CI environment); run_text_listener returns immediately and the TaskGroup composes without it. Arbiter's >=2-source rule still trips via rib.gg + OCR.
- Twitter-only quarantine semantics are structurally proven by `test_twitter_only_update_quarantined` in this plan; the E2E test does not need to re-prove them.

## Self-Check: PASSED

- `src/ingestion/text_listener.py` exists on disk (verified via Read tool earlier in execution).
- `src/config/constants.py` declares TWITTER_API_BASE_URL + TWITTER_RULE_SET (verified via successful smoke import: `from src.config.constants import TWITTER_RULE_SET, TWITTER_API_BASE_URL; assert len(TWITTER_RULE_SET) >= 5`).
- `from src.ingestion import run_text_listener` resolves (verified via successful smoke import).
- `from src.ingestion.text_listener import run_text_listener, _MatchSignalListener, _SCORE_PATTERN` resolves.
- 2 task commits reachable on git: `cbf2017` (Task 1), `e25b5de` (Task 2). Auto-pushed to remote main via post-commit hook (`To https://github.com/jxc2008/valorant-pricing-model ... main -> main`).
- `pytest tests/ingestion/test_text_listener.py -v` -> 3 passed / 0 failed.
- `pytest tests/ -x --no-cov -q` -> 287 passed / 26 xfailed (no FAIL; up 3 GREEN from 284/29).
- `mypy --strict src/pricing src/state` -> "Success: no issues found in 9 source files".
- `mypy src/ingestion/` -> "Success: no issues found in 8 source files".
- `ruff check src tests scripts` -> "All checks passed!".
- xfail markers REMOVED from tests/ingestion/test_text_listener.py (verified — file now contains only @pytest.mark.asyncio decorators on the 3 GREEN tests; no `pytest.xfail(...)` runtime calls).
- TWITTER_BEARER_TOKEN no-op verified by `test_no_token_noop` (both delenv path and whitespace-only setenv path complete in <1s without raising).

---
*Phase: 03-live-ingestion-layer*
*Completed: 2026-05-10*
