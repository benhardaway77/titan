from titan.risk.governor import RiskGovernor, RiskState


def make_state(dd_pct: float) -> RiskState:
    """Helper: build a RiskState with the given drawdown percentage."""
    hwm = 1000.0
    return RiskState(equity=hwm * (1 - dd_pct), high_water_mark=hwm)


def test_zones():
    gov = RiskGovernor(max_drawdown_pct=0.60, green_dd=0.15, yellow_dd=0.40, red_dd=0.59)

    assert gov.zone(make_state(0.00)) == "green"     # no drawdown
    assert gov.zone(make_state(0.14)) == "green"     # just under green threshold
    assert gov.zone(make_state(0.15)) == "yellow"    # at green_dd
    assert gov.zone(make_state(0.39)) == "yellow"    # just under yellow threshold
    assert gov.zone(make_state(0.40)) == "red"       # at yellow_dd
    assert gov.zone(make_state(0.58)) == "red"       # just under red_dd
    assert gov.zone(make_state(0.59)) == "critical"  # at red_dd — pre-kill-switch
    assert gov.zone(make_state(0.60)) == "dead"      # at max_drawdown_pct
    assert gov.zone(make_state(0.80)) == "dead"      # beyond kill-switch


def test_leverage_caps():
    gov = RiskGovernor(max_drawdown_pct=0.60, green_dd=0.15, yellow_dd=0.40, red_dd=0.59)
    base = 5.0

    assert gov.leverage_cap(base, make_state(0.00)) == 5.0   # green: full cap
    assert gov.leverage_cap(base, make_state(0.15)) == 2.0   # yellow: capped at 2x
    assert gov.leverage_cap(base, make_state(0.40)) == 1.0   # red: capped at 1x
    assert gov.leverage_cap(base, make_state(0.59)) == 0.0   # critical: no new leverage
    assert gov.leverage_cap(base, make_state(0.60)) == 0.0   # dead: no new leverage


def test_allow_new_risk():
    gov = RiskGovernor(max_drawdown_pct=0.60, green_dd=0.15, yellow_dd=0.40, red_dd=0.59)

    assert gov.allow_new_risk(make_state(0.00)) is True    # green
    assert gov.allow_new_risk(make_state(0.15)) is True    # yellow
    assert gov.allow_new_risk(make_state(0.40)) is True    # red — reduced, but allowed
    assert gov.allow_new_risk(make_state(0.59)) is False   # critical — halt new risk
    assert gov.allow_new_risk(make_state(0.60)) is False   # dead


def test_drawdown_pct_zero_hwm():
    """RiskState with zero high_water_mark should not crash."""
    s = RiskState(equity=1000, high_water_mark=0)
    assert s.drawdown_pct == 0.0
