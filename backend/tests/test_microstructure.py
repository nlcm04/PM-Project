from datetime import date

from app.quant.microstructure import (
    is_within_price_band,
    price_band,
    round_to_lot,
    settlement_date,
    shares_affordable,
)


def test_round_to_lot_floors_to_100():
    assert round_to_lot(349) == 300
    assert round_to_lot(400) == 400
    assert round_to_lot(99) == 0


def test_shares_affordable_never_overspends():
    qty = shares_affordable(cash=10_050_000, price=50_000)
    assert qty % 100 == 0
    assert qty * 50_000 <= 10_050_000


def test_price_band_is_plus_minus_7_percent():
    floor, ceiling = price_band(100_000)
    assert floor == 93_000
    assert ceiling == 107_000


def test_is_within_price_band():
    assert is_within_price_band(105_000, ref_price=100_000)
    assert not is_within_price_band(108_000, ref_price=100_000)


def test_settlement_date_skips_weekends():
    # Friday trade -> T+2 business days lands on Tuesday
    friday = date(2026, 8, 28)
    assert friday.weekday() == 4
    settled = settlement_date(friday, t_plus=2)
    assert settled.weekday() not in (5, 6)
    assert settled == date(2026, 9, 1)
