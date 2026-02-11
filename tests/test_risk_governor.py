from titan.risk.governor import RiskGovernor, RiskState


def test_zones():
    gov = RiskGovernor(max_drawdown_pct=0.60, green_dd=0.15, yellow_dd=0.40)

    assert gov.zone(RiskState(equity=1000, high_water_mark=1000)) == "green"
    assert gov.zone(RiskState(equity=850, high_water_mark=1000)) == "yellow"  # 15%
    assert gov.zone(RiskState(equity=600, high_water_mark=1000)) == "red"     # 40%
    assert gov.zone(RiskState(equity=400, high_water_mark=1000)) == "dead"    # 60%


def test_leverage_caps():
    gov = RiskGovernor(max_drawdown_pct=0.60, green_dd=0.15, yellow_dd=0.40)
    base = 5.0

    assert gov.leverage_cap(base, RiskState(1000, 1000)) == 5.0
    assert gov.leverage_cap(base, RiskState(850, 1000)) == 2.0
    assert gov.leverage_cap(base, RiskState(600, 1000)) == 1.0
    assert gov.leverage_cap(base, RiskState(400, 1000)) == 0.0
