"""Long-only, lot-constrained max-Sharpe optimizer (spec Section 5.1 / 5.2)."""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize

from app.quant.microstructure import round_to_lot


def _negative_sharpe(weights: np.ndarray, mu: np.ndarray, cov: np.ndarray, risk_free: float) -> float:
    port_return = weights @ mu
    port_vol = np.sqrt(weights @ cov @ weights)
    if port_vol == 0:
        return 0.0
    return -(port_return - risk_free) / port_vol


def max_sharpe_weights(mu: np.ndarray, cov: np.ndarray, risk_free: float = 0.0) -> np.ndarray:
    """Solve for the long-only max-Sharpe portfolio: w >= 0, sum(w) == 1."""
    n = len(mu)
    if n == 0:
        return np.array([])
    x0 = np.full(n, 1.0 / n)
    bounds = [(0.0, 1.0)] * n
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    result = minimize(
        _negative_sharpe,
        x0,
        args=(mu, cov, risk_free),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-9},
    )
    weights = result.x if result.success else x0
    weights = np.clip(weights, 0, None)
    total = weights.sum()
    return weights / total if total > 0 else weights


def apply_lot_constraint(weights: np.ndarray, prices: np.ndarray, capital: float, lot_size: int = 100) -> np.ndarray:
    """Convert target weights into whole-lot share quantities that fit within `capital`.

    Greedy correction: round every position down to the nearest lot, then use any
    leftover cash to bump up the most underweight position by one more lot at a time.
    """
    target_value = weights * capital
    quantities = np.array([round_to_lot(v / p, lot_size) if p > 0 else 0 for v, p in zip(target_value, prices)])

    spent = quantities @ prices
    leftover = capital - spent
    # Greedily deploy leftover cash into whichever holding is furthest below its target weight.
    while True:
        current_value = quantities * prices
        current_weights = current_value / capital if capital > 0 else current_value
        shortfall = weights - current_weights
        candidates = np.where((prices * lot_size <= leftover) & (prices > 0))[0]
        if len(candidates) == 0:
            break
        best = candidates[np.argmax(shortfall[candidates])]
        if shortfall[best] <= 0:
            break
        quantities[best] += lot_size
        leftover -= prices[best] * lot_size
    return quantities
