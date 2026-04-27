"""Smoke test — exists so `pytest --collect-only` exits 0 on the empty skeleton.

Replace with real tests as features land in Phases 1+. Safe to delete once
any other test file exists in `tests/`.
"""


def test_smoke() -> None:
    assert True
