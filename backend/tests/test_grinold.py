import numpy as np
import pandas as pd

from app.quant.grinold import expected_active_return, fundamental_law_breadth, information_coefficient


def test_information_coefficient_perfect_rank_correlation():
    scores = pd.Series([1, 2, 3, 4, 5])
    forward_returns = pd.Series([0.01, 0.02, 0.03, 0.04, 0.05])
    assert np.isclose(information_coefficient(scores, forward_returns), 1.0)


def test_expected_active_return_scales_by_ic_sigma_and_score():
    ic = 0.1
    sigma = pd.Series([0.02, 0.03])
    score_z = pd.Series([1.0, -1.0])
    mu = expected_active_return(ic, sigma, score_z)
    assert np.isclose(mu.iloc[0], 0.1 * 0.02 * 1.0)
    assert np.isclose(mu.iloc[1], 0.1 * 0.03 * -1.0)


def test_fundamental_law_breadth_scales_with_sqrt_n():
    ir_10 = fundamental_law_breadth(ic=0.1, n_independent_bets=10)
    ir_40 = fundamental_law_breadth(ic=0.1, n_independent_bets=40)
    assert np.isclose(ir_40, ir_10 * 2)
