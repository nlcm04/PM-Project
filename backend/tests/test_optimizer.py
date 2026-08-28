import numpy as np

from app.quant.optimizer import apply_lot_constraint, max_sharpe_weights


def test_max_sharpe_weights_are_long_only_and_sum_to_one():
    mu = np.array([0.08, 0.05, 0.03])
    cov = np.diag([0.04, 0.02, 0.01])
    weights = max_sharpe_weights(mu, cov)
    assert np.all(weights >= -1e-9)
    assert np.isclose(weights.sum(), 1.0, atol=1e-6)


def test_apply_lot_constraint_respects_capital_and_lot_size():
    weights = np.array([0.5, 0.5])
    prices = np.array([37_000, 61_500])
    capital = 100_000_000
    quantities = apply_lot_constraint(weights, prices, capital)
    assert np.all(quantities % 100 == 0)
    assert quantities @ prices <= capital
