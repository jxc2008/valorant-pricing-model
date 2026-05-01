# Deferred Items — Phase 02

Pre-existing issues discovered during execution but out of scope for the
current plan. Each entry tags the discovering plan and the affected file.

## Plan 02-03 — pre-existing ruff errors in Plan 02-02 files

- `tests/calibration/conftest.py:18` — `UP035`: import `Iterator` from
  `collections.abc` (Python 3.9+ pattern). Plan 02-02 ships this file.
- `tests/probe/test_endpoint_shapes.py:13` — `I001`: import block
  un-sorted or un-formatted. Plan 02-02 ships this file.

Both were authored before the plan-phase pass that revised 02-03. They do
not fail Plan 02-03's acceptance criteria (which scope ruff to
`scripts/probe_round_events.py`) but `uv run ruff check .` reports them.

Plan 02-04 author should run `uv run ruff check --fix tests/` as a one-line
maintenance fix at the start of execution.
