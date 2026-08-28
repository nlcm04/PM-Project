from scripts.build_static_snapshot import compute_foreign_flow_factor, update_foreign_flow_history


def test_update_foreign_flow_history_appends_new_ticker():
    history = {}
    updated = update_foreign_flow_history(history, {"VNM": 1_000_000.0}, today="2026-08-28")
    assert updated["VNM"] == [{"date": "2026-08-28", "net_value": 1_000_000.0}]


def test_update_foreign_flow_history_upserts_same_day_instead_of_duplicating():
    # Simulates two hourly runs on the same calendar day.
    history = {"VNM": [{"date": "2026-08-28", "net_value": 1_000_000.0}]}
    updated = update_foreign_flow_history(history, {"VNM": 2_000_000.0}, today="2026-08-28")
    assert updated["VNM"] == [{"date": "2026-08-28", "net_value": 2_000_000.0}]


def test_update_foreign_flow_history_appends_new_day():
    history = {"VNM": [{"date": "2026-08-27", "net_value": 1_000_000.0}]}
    updated = update_foreign_flow_history(history, {"VNM": 2_000_000.0}, today="2026-08-28")
    assert updated["VNM"] == [
        {"date": "2026-08-27", "net_value": 1_000_000.0},
        {"date": "2026-08-28", "net_value": 2_000_000.0},
    ]


def test_update_foreign_flow_history_trims_to_window():
    history = {"VNM": [{"date": f"2026-08-{d:02d}", "net_value": float(d)} for d in range(1, 6)]}
    updated = update_foreign_flow_history(history, {"VNM": 6.0}, today="2026-08-06", trim_days=3)
    assert [p["date"] for p in updated["VNM"]] == ["2026-08-04", "2026-08-05", "2026-08-06"]


def test_update_foreign_flow_history_skips_none_snapshots():
    history = {}
    updated = update_foreign_flow_history(history, {"VNM": None}, today="2026-08-28")
    assert "VNM" not in updated


def test_compute_foreign_flow_factor_sums_available_window():
    history = {
        "VNM": [{"date": "2026-08-2%d" % d, "net_value": 1_000_000.0} for d in range(1, 8)],  # 7 days
    }
    factor = compute_foreign_flow_factor(history, window=5)
    assert factor["VNM"] == 5_000_000.0  # only the most recent 5 of the 7 available days


def test_compute_foreign_flow_factor_handles_thin_history():
    # Only 1 day recorded so far -- shouldn't crash or wait for a full window.
    history = {"VNM": [{"date": "2026-08-28", "net_value": 500_000.0}]}
    factor = compute_foreign_flow_factor(history, window=5)
    assert factor["VNM"] == 500_000.0
