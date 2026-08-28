from app.quant.sell_rules import evaluate_sell_signal


def test_no_signal_when_all_criteria_pass():
    result = evaluate_sell_signal(
        percentile_rank_last_2_quarters=[60, 55],
        governance_disqualified=False,
        governance_reasons=[],
        current_price=100_000,
        peak_price_since_open=105_000,
        atr=2_000,
    )
    assert result.triggered is False


def test_signal_on_two_quarter_percentile_degradation():
    result = evaluate_sell_signal(
        percentile_rank_last_2_quarters=[25, 20],
        governance_disqualified=False,
        governance_reasons=[],
        current_price=100_000,
        peak_price_since_open=105_000,
        atr=2_000,
    )
    assert result.triggered is True
    assert any("percentile" in r for r in result.reasons)


def test_no_signal_on_single_bad_quarter():
    result = evaluate_sell_signal(
        percentile_rank_last_2_quarters=[60, 20],
        governance_disqualified=False,
        governance_reasons=[],
        current_price=100_000,
        peak_price_since_open=105_000,
        atr=2_000,
    )
    assert result.triggered is False


def test_signal_on_atr_trailing_stop_breach():
    result = evaluate_sell_signal(
        percentile_rank_last_2_quarters=[60, 55],
        governance_disqualified=False,
        governance_reasons=[],
        current_price=90_000,
        peak_price_since_open=100_000,
        atr=3_000,  # stop = 100,000 - 2.5*3,000 = 92,500 > current price
    )
    assert result.triggered is True
    assert any("trailing stop" in r for r in result.reasons)


def test_signal_on_governance_violation_overrides_everything():
    result = evaluate_sell_signal(
        percentile_rank_last_2_quarters=[80, 80],
        governance_disqualified=True,
        governance_reasons=["adverse audit opinion"],
        current_price=100_000,
        peak_price_since_open=100_000,
        atr=0,
    )
    assert result.triggered is True
