"""Bradley-Terry round-win-probability blend.

Replaces the audit-engine arithmetic-mean blend ``(a + (1-b)) / 2`` with the
log-odds form ``a*(1-b) / (a*(1-b) + (1-a)*b)``.

Sources
-------
- DEC-003 / CLAUDE.md rule 3 / CON-bradley-terry-formula
- prd.md §12.2 #4 (audit-engine bug being fixed)
- roadmap.md §1.2 (acceptance criteria — see test_blend.py)
- 01-RESEARCH.md §3 (algebraic symmetry proof; clip-on-input rationale)

Why Bradley-Terry, not arithmetic mean
--------------------------------------
For ``(0.7, 0.3)`` (team A is 70% on its side, team B is 30% on its side, i.e.
team A's opponent gives up rounds at a 70% rate too), arithmetic mean returns
``(0.7 + 0.7) / 2 = 0.70``. Bradley-Terry returns ``0.49 / 0.58 ≈ 0.845``,
correctly capturing that compounding edges multiply rather than average.

Why clip inputs only, never outputs
-----------------------------------
``round_p(a, b) + round_p(b, a) == 1`` is required for downstream symmetry
(the DP relies on this in `series_value` recurrences). Clipping the OUTPUT
breaks this identity (``0.999... → 0.99`` does not pair with
``0.001... → 0.01`` for ``1 - x``). Clipping inputs symmetrically preserves
the algebra. See 01-RESEARCH.md §3 Pitfall 4.

The output clip ``[CONVICTION_CLIP_LOW, CONVICTION_CLIP_HIGH] = [0.01, 0.99]``
is applied in ``live_theo.py`` on the FINAL ``theo_series`` and per-map
probabilities, never on intermediate round probabilities.
"""

from __future__ import annotations

from src.config.constants import BT_BLEND_EPSILON


def round_p(a_rate: float, b_rate_opposite_side: float) -> float:
    """P(team A wins one round) given A's rate on its side and B's rate on opposite side.

    Args:
        a_rate: Team A's empirical win-rate on the side it plays this round.
            Must be in ``[0.0, 1.0]`` (will be clipped to
            ``[BT_BLEND_EPSILON, 1 - BT_BLEND_EPSILON]`` internally).
        b_rate_opposite_side: Team B's empirical win-rate on the OPPOSITE side
            (i.e., the side B plays while A is on `side`). Same bounds.

    Returns:
        ``(a*(1-b)) / (a*(1-b) + (1-a)*b)`` after BT_BLEND_EPSILON input clip.
        Always finite, in ``(0.0, 1.0)``. NEVER clipped on output (CON-bradley-
        terry-formula / 01-RESEARCH.md §3 Pitfall 4 — preserves BT symmetry
        ``round_p(a, b) + round_p(b, a) == 1``).

    Notes:
        DO NOT call this with the arithmetic-mean form. See module docstring.
    """
    a = max(BT_BLEND_EPSILON, min(1.0 - BT_BLEND_EPSILON, a_rate))
    b = max(BT_BLEND_EPSILON, min(1.0 - BT_BLEND_EPSILON, b_rate_opposite_side))
    return (a * (1.0 - b)) / (a * (1.0 - b) + (1.0 - a) * b)
