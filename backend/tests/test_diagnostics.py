import numpy as np
import pandas as pd

from app.quant.diagnostics import prune_by_vif, run_adf


def test_run_adf_on_white_noise_is_stationary():
    rng = np.random.default_rng(0)
    series = pd.Series(rng.normal(size=200))
    result = run_adf(series)
    assert result["is_stationary"] is True


def test_prune_by_vif_drops_collinear_factor():
    rng = np.random.default_rng(0)
    base = rng.normal(size=300)
    df = pd.DataFrame(
        {
            "a": base,
            "b": base * 2 + rng.normal(scale=0.001, size=300),  # near-perfectly collinear with a
            "c": rng.normal(size=300),
        }
    )
    pruned, dropped = prune_by_vif(df, threshold=5.0)
    assert len(dropped) >= 1
    assert "c" in pruned.columns
