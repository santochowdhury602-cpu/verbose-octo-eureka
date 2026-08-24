from market.orderflow import OrderFlowEngine


def make_trade(trade_id, timestamp, side, quantity):
    return {
        "id": trade_id,
        "timestamp": timestamp,
        "side": side,
        "quantity": quantity,
    }


def test_duplicate_trade_is_counted_once():
    engine = OrderFlowEngine()
    item = make_trade("1", 1, "BUY", 2)

    result = engine.analyze([item, item])

    assert result.buy_volume == 2
    assert result.delta == 2
    assert result.cumulative_delta == 2


def test_replay_is_deterministic():
    sequence = [
        make_trade("1", 1, "BUY", 2),
        make_trade("2", 2, "SELL", 1),
    ]

    first = OrderFlowEngine().analyze(sequence)
    replayed = OrderFlowEngine().analyze(sequence + sequence)

    assert replayed == first


def test_out_of_order_trades_have_deterministic_cvd():
    ordered = [
        make_trade("1", 1, "BUY", 2),
        make_trade("2", 2, "SELL", 1),
    ]

    first = OrderFlowEngine().analyze(ordered)
    second = OrderFlowEngine().analyze(list(reversed(ordered)))

    assert second.cumulative_delta == first.cumulative_delta
    assert second.buy_volume == 2
    assert second.sell_volume == 1