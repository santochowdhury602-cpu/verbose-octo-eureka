from brain.risk import (
    RiskConfig,
    RiskGate,
)


def test_risk_approved():

    gate = RiskGate(
        RiskConfig(
            account_size=500,
            risk_per_trade_pct=1,
            max_leverage=5,
            minimum_confidence=75,
        )
    )

    result = gate.evaluate(
        action="LONG",
        confidence=80,
        entry=100000,
        stop_loss=99500,
        leverage=5,
    )

    assert result.approved is True
    assert result.risk_usd == 5
    assert result.position_size > 0


def test_missing_stop_rejected():

    result = RiskGate().evaluate(
        action="LONG",
        confidence=80,
        entry=100000,
        stop_loss=None,
        leverage=5,
    )

    assert result.approved is False
    assert any(
        "stop" in x.lower()
        for x in result.rejection_reasons
    )


def test_excessive_leverage_rejected():

    result = RiskGate().evaluate(
        action="LONG",
        confidence=80,
        entry=100000,
        stop_loss=99500,
        leverage=10,
    )

    assert result.approved is False


def test_drawdown_kill_switch():

    result = RiskGate().evaluate(
        action="LONG",
        confidence=80,
        entry=100000,
        stop_loss=99500,
        leverage=5,
        daily_drawdown_pct=3,
    )

    assert result.approved is False


def test_position_limit():

    result = RiskGate().evaluate(
        action="LONG",
        confidence=80,
        entry=100000,
        stop_loss=99500,
        leverage=5,
        open_positions=2,
    )

    assert result.approved is False


def test_wrong_long_stop():

    result = RiskGate().evaluate(
        action="LONG",
        confidence=80,
        entry=100000,
        stop_loss=101000,
        leverage=5,
    )

    assert result.approved is False


def test_wrong_short_stop():

    result = RiskGate().evaluate(
        action="SHORT",
        confidence=80,
        entry=100000,
        stop_loss=99000,
        leverage=5,
    )

    assert result.approved is False
