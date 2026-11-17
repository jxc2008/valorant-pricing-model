"""Tabulated production map DP: P(A wins map) as a function of A's round-win logits.

The production DP (src.pricing.live_theo._within_map_p_a_wins) only consumes per-round
probabilities from the log5 blend (pistols use the same blend; anti-eco rounds use the fixed
GUN_WIN_RATE). Feeding it a neutral opponent (B rates = 0.5) and a 0.5 league baseline makes
the blend return A's rate unchanged, so the DP output is a function F(eta_atk, eta_def) of A's
attack/defence round logits. We tabulate F (averaged over A starting atk/def) on a grid once
and interpolate bilinearly; ``verify`` checks the interpolation against direct DP calls.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.pricing.data import HalfRates
from src.pricing.live_theo import _within_map_p_a_wins
from src.state.match_state import MatchState

GRID = np.round(np.arange(-3.0, 3.0001, 0.1), 6)
TABLE_PATH = Path(__file__).resolve().parents[2] / "models" / "dp_map_table.npz"
_MAP = "M"


def _sig(x: float) -> float:
    return 1.0 / (1.0 + float(np.exp(-x)))


def dp_map_p(eta_atk: float, eta_def: float) -> float:
    """Direct production-DP call: P(A wins) averaged over A's starting side."""
    hr = HalfRates(
        team_rates={f"A|{_MAP}|atk": {"rate": _sig(eta_atk)}, f"A|{_MAP}|def": {"rate": _sig(eta_def)},
                    f"B|{_MAP}|atk": {"rate": 0.5}, f"B|{_MAP}|def": {"rate": 0.5}},
        league_rates={f"{_MAP}|atk": {"rate": 0.5}}, overall_avg=0.5, pre_shrunk=True)
    ps = []
    for side in ("a_atk", "a_def"):
        ms = MatchState("t", "A", "B", (_MAP,), (side,), (None,), {}, 0, 0, 0, 0, 0, side, False,
                        None, None, None, 0, 0.0)
        ps.append(_within_map_p_a_wins((_MAP,), 0, side, (None,), ms, hr))
    return 0.5 * (ps[0] + ps[1])


def build(path: Path = TABLE_PATH) -> np.ndarray:
    tab = np.array([[dp_map_p(a, d) for d in GRID] for a in GRID])
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, grid=GRID, table=tab)
    return tab


class MapTable:
    def __init__(self, path: Path = TABLE_PATH) -> None:
        if not path.exists():
            build(path)
        z = np.load(path)
        self.grid, self.tab = z["grid"], z["table"]
        self.lo, self.step, self.n = float(self.grid[0]), float(self.grid[1] - self.grid[0]), len(self.grid)

    def __call__(self, eta_atk: np.ndarray | float, eta_def: np.ndarray | float) -> np.ndarray:
        x = np.clip((np.asarray(eta_atk, float) - self.lo) / self.step, 0, self.n - 1.000001)
        y = np.clip((np.asarray(eta_def, float) - self.lo) / self.step, 0, self.n - 1.000001)
        i, j = np.floor(x).astype(int), np.floor(y).astype(int)
        fx, fy = x - i, y - j
        t = self.tab
        return ((1 - fx) * (1 - fy) * t[i, j] + fx * (1 - fy) * t[i + 1, j]
                + (1 - fx) * fy * t[i, j + 1] + fx * fy * t[i + 1, j + 1])

    def map_p(self, d_mean: float, d_var: float, delta: float, n_gh: int = 5) -> float:
        """P(A wins map), integrating the strength difference d ~ N(d_mean, d_var) by
        Gauss-Hermite; A's round logits are d + delta (attacking) and d - delta (defending)."""
        z, w = np.polynomial.hermite_e.hermegauss(n_gh)
        d = d_mean + np.sqrt(max(d_var, 0.0)) * z
        return float((w / w.sum()) @ self(d + delta, d - delta))


def verify(n: int = 40, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    t = MapTable()
    pts = rng.uniform(-2.5, 2.5, size=(n, 2))
    return float(max(abs(t(a, d) - dp_map_p(a, d)) for a, d in pts))
