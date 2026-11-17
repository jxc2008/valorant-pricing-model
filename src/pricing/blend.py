"""Bradley-Terry round-win-probability blend.

Replaces the audit-engine arithmetic-mean blend ``(a + (1-b)) / 2`` with a
log-odds (log5) form against the league side baseline:
``odds(p) = odds(a) * odds(1-b) / odds(L_side)``. With ``L_side = 0.5`` this is
Bradley-Terry ``a*(1-b) / (a*(1-b) + (1-a)*b)``.

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
``round_p(a, b, L) + round_p(b, a, 1-L) == 1`` is required for downstream symmetry
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


def _odds(x: float) -> float:
    return x / (1.0 - x)


def _clip(x: float) -> float:
    return max(BT_BLEND_EPSILON, min(1.0 - BT_BLEND_EPSILON, x))


def round_p(a_rate: float, b_rate_opposite_side: float, league_side_rate: float) -> float:
    """P(team A wins one round), log5 against the league side baseline.

    ``odds(p) = odds(a) * odds(1 - b) / odds(L_side)``

    Args:
        a_rate: Team A's win-rate on the side it plays this round, on this map.
        b_rate_opposite_side: Team B's win-rate on the opposite side, same map.
        league_side_rate: League win-rate for the side TEAM A plays (L_side),
            on this map. Both team rates already embed this side advantage;
            dividing by ``odds(L_side)`` once removes the double count. The
            previous form ``odds(a)*odds(1-b)`` implicitly assumed L_side=0.5.

    Invariants (tests/pricing/test_blend.py):
        - league-average teams: ``round_p(L, 1-L, L) == L``
        - symmetry: ``round_p(a, b, L) + round_p(b, a, 1-L) == 1``
        - reduces to Bradley-Terry ``a(1-b)/(a(1-b)+(1-a)b)`` when L = 0.5

    All three inputs are clipped to ``[BT_BLEND_EPSILON, 1-BT_BLEND_EPSILON]``;
    the output is never clipped (see module docstring).
    """
    a, b, lg = _clip(a_rate), _clip(b_rate_opposite_side), _clip(league_side_rate)
    o = _odds(a) * _odds(1.0 - b) / _odds(lg)
    return o / (1.0 + o)
