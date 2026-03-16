"""
Tests du PortfolioManager.
Lance avec: pytest tests/test_portfolio.py -v
"""
import pytest
from paper_trading.portfolio import PortfolioManager


@pytest.fixture
def portfolio():
    return PortfolioManager(initial_capital=10_000.0)


def test_initial_state(portfolio):
    assert portfolio.cash == 10_000.0
    assert portfolio.get_total_equity() == 10_000.0
    assert portfolio.total_trades == 0
    assert len(portfolio.get_positions()) == 0


def test_buy_order(portfolio):
    order = portfolio.buy("BTC/USDT:USDT", 1000.0, 50_000.0)
    assert order["quantity"] == pytest.approx(1000.0 / 50_000.0, rel=1e-6)
    assert portfolio.cash < 10_000.0
    assert "BTC/USDT:USDT" in portfolio.get_positions()


def test_sell_order(portfolio):
    portfolio.buy("BTC/USDT:USDT", 1000.0, 50_000.0)
    order = portfolio.sell("BTC/USDT:USDT", 0.01, 55_000.0)
    assert "pnl" in order
    assert order["pnl"] > 0  # prix monté de 50k à 55k


def test_close_position(portfolio):
    portfolio.buy("BTC/USDT:USDT", 1000.0, 50_000.0)
    assert "BTC/USDT:USDT" in portfolio.get_positions()
    portfolio.close_position("BTC/USDT:USDT", 52_000.0)
    assert "BTC/USDT:USDT" not in portfolio.get_positions()


def test_insufficient_funds(portfolio):
    with pytest.raises(ValueError, match="Fonds insuffisants"):
        portfolio.buy("BTC/USDT:USDT", 15_000.0, 50_000.0)


def test_sell_no_position(portfolio):
    with pytest.raises(ValueError):
        portfolio.sell("BTC/USDT:USDT", 0.1, 50_000.0)


def test_metrics(portfolio):
    portfolio.buy("BTC/USDT:USDT", 2000.0, 50_000.0)
    portfolio.close_position("BTC/USDT:USDT", 55_000.0)
    m = portfolio.metrics()
    assert m["total_trades"] == 2
    assert m["winning_trades"] == 1
    assert m["total_return_pct"] > 0


def test_update_prices(portfolio):
    portfolio.buy("BTC/USDT:USDT", 1000.0, 50_000.0)
    portfolio.update_prices({"BTC/USDT:USDT": 55_000.0})
    positions = portfolio.get_positions()
    assert positions["BTC/USDT:USDT"]["current_price"] == 55_000.0
    assert positions["BTC/USDT:USDT"]["unrealized_pnl"] > 0


def test_win_rate(portfolio):
    # 2 gains
    portfolio.buy("BTC/USDT:USDT", 1000.0, 50_000.0)
    portfolio.close_position("BTC/USDT:USDT", 55_000.0)
    portfolio.buy("ETH/USDT:USDT", 1000.0, 3_000.0)
    portfolio.close_position("ETH/USDT:USDT", 3_300.0)
    m = portfolio.metrics()
    assert m["win_rate_pct"] == 100.0
