"""
Portfolio Manager - Gestion du portefeuille virtuel.
Port nettoyé de portfolio_manager.py avec corrections appliquées.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from loguru import logger


class TradeSide(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class Trade:
    id: str
    symbol: str
    side: TradeSide
    quantity: float
    entry_price: float
    exit_price: Optional[float] = None
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    commission: float = 0.0
    pnl: float = 0.0
    pnl_percent: float = 0.0

    def __post_init__(self):
        if self.entry_time is None:
            self.entry_time = datetime.now()


@dataclass
class Position:
    symbol: str
    quantity: float
    entry_price: float
    entry_time: datetime
    current_price: float = 0.0

    @property
    def unrealized_pnl(self) -> float:
        return (self.current_price - self.entry_price) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return (self.current_price / self.entry_price - 1) * 100

    def update_price(self, price: float):
        self.current_price = price


class PortfolioManager:
    """
    Gestionnaire de portefeuille virtuel.
    Simule l'exécution d'ordres sans passer d'ordres réels.
    """

    def __init__(self, initial_capital: float = 10_000.0, commission_rate: float = 0.001):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.commission_rate = commission_rate

        self.positions: Dict[str, Position] = {}
        self.trade_history: List[Trade] = []

        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.peak_equity = initial_capital
        self.max_drawdown = 0.0

        self.created_at = datetime.now()

    # ------------------------------------------------------------------
    # Ordre d'achat
    # ------------------------------------------------------------------

    def buy(self, symbol: str, amount_usdt: float, price: float) -> Dict:
        """
        Achète 'amount_usdt' worth de 'symbol' au prix 'price'.
        Returns: dict avec détails de l'ordre.
        """
        commission = amount_usdt * self.commission_rate
        total_cost = amount_usdt + commission

        if total_cost > self.cash:
            raise ValueError(f"Fonds insuffisants: besoin {total_cost:.2f}, disponible {self.cash:.2f}")

        quantity = amount_usdt / price
        trade_id = f"T{len(self.trade_history)+1:04d}"

        trade = Trade(
            id=trade_id,
            symbol=symbol,
            side=TradeSide.BUY,
            quantity=quantity,
            entry_price=price,
            commission=commission,
        )

        # Mise à jour position (moyenne si déjà ouverte)
        if symbol in self.positions:
            pos = self.positions[symbol]
            total_qty = pos.quantity + quantity
            avg_price = (pos.quantity * pos.entry_price + quantity * price) / total_qty
            self.positions[symbol] = Position(
                symbol=symbol, quantity=total_qty, entry_price=avg_price,
                entry_time=pos.entry_time, current_price=price
            )
        else:
            self.positions[symbol] = Position(
                symbol=symbol, quantity=quantity, entry_price=price,
                entry_time=datetime.now(), current_price=price
            )

        self.cash -= total_cost
        self.trade_history.append(trade)
        self.total_trades += 1
        self._update_metrics()

        logger.debug(f"BUY {symbol}: {quantity:.6f} @ {price:.2f} (comm: {commission:.4f})")
        return {
            "id": trade_id, "symbol": symbol, "side": "buy",
            "quantity": quantity, "price": price,
            "amount_usdt": amount_usdt, "commission": commission,
        }

    # ------------------------------------------------------------------
    # Ordre de vente
    # ------------------------------------------------------------------

    def sell(self, symbol: str, quantity: float, price: float) -> Dict:
        """
        Vend 'quantity' de 'symbol' au prix 'price'.
        Returns: dict avec détails + PnL réalisé.
        """
        if symbol not in self.positions:
            raise ValueError(f"Aucune position ouverte pour {symbol}")

        pos = self.positions[symbol]
        if quantity > pos.quantity:
            quantity = pos.quantity  # vente partielle max

        amount_usdt = quantity * price
        commission = amount_usdt * self.commission_rate
        net = amount_usdt - commission
        pnl = (price - pos.entry_price) * quantity - commission
        pnl_pct = (price / pos.entry_price - 1) * 100

        trade_id = f"T{len(self.trade_history)+1:04d}"
        trade = Trade(
            id=trade_id, symbol=symbol, side=TradeSide.SELL,
            quantity=quantity, entry_price=pos.entry_price,
            exit_price=price, commission=commission,
            pnl=pnl, pnl_percent=pnl_pct, exit_time=datetime.now()
        )

        if quantity >= pos.quantity:
            del self.positions[symbol]
        else:
            pos.quantity -= quantity
            pos.update_price(price)

        self.cash += net
        self.winning_trades += (1 if pnl > 0 else 0)
        self.losing_trades += (1 if pnl <= 0 else 0)
        self.trade_history.append(trade)
        self.total_trades += 1
        self._update_metrics()

        logger.debug(f"SELL {symbol}: {quantity:.6f} @ {price:.2f} | PnL: {pnl:+.2f}")
        return {
            "id": trade_id, "symbol": symbol, "side": "sell",
            "quantity": quantity, "price": price,
            "amount_usdt": amount_usdt, "commission": commission,
            "pnl": pnl, "pnl_percent": pnl_pct,
        }

    def close_position(self, symbol: str, price: float) -> Dict:
        """Ferme complètement une position."""
        if symbol not in self.positions:
            raise ValueError(f"Position non trouvée: {symbol}")
        return self.sell(symbol, self.positions[symbol].quantity, price)

    # Alias pour compatibilité avec l'ancien code
    def place_market_order(self, symbol: str, side: str, amount: float, price: float) -> Dict:
        if side.lower() == "buy":
            return self.buy(symbol, amount, price)
        return self.sell(symbol, amount, price)

    # ------------------------------------------------------------------
    # Métriques
    # ------------------------------------------------------------------

    def get_total_equity(self, current_prices: Dict[str, float] = None) -> float:
        equity = self.cash
        prices = current_prices or {}
        for sym, pos in self.positions.items():
            price = prices.get(sym, pos.current_price)
            equity += pos.quantity * price
        return equity

    def _update_metrics(self):
        equity = self.get_total_equity()
        if equity > self.peak_equity:
            self.peak_equity = equity
        dd = (self.peak_equity - equity) / self.peak_equity * 100
        self.max_drawdown = max(self.max_drawdown, dd)

    def get_balance(self) -> float:
        return self.cash

    def get_positions(self) -> Dict:
        return {
            sym: {
                "quantity": pos.quantity,
                "avg_price": pos.entry_price,
                "current_price": pos.current_price,
                "unrealized_pnl": pos.unrealized_pnl,
                "unrealized_pnl_pct": pos.unrealized_pnl_pct,
            }
            for sym, pos in self.positions.items()
        }

    def update_prices(self, prices: Dict[str, float]):
        for sym, price in prices.items():
            if sym in self.positions:
                self.positions[sym].update_price(price)
        self._update_metrics()

    def metrics(self, current_prices: Dict[str, float] = None) -> Dict:
        equity = self.get_total_equity(current_prices)
        total_return = (equity / self.initial_capital - 1) * 100
        completed = self.winning_trades + self.losing_trades
        win_rate = (self.winning_trades / completed * 100) if completed > 0 else 0

        return {
            "initial_capital": self.initial_capital,
            "current_equity": equity,
            "cash": self.cash,
            "total_return_pct": total_return,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate_pct": win_rate,
            "max_drawdown_pct": self.max_drawdown,
            "open_positions": len(self.positions),
        }

    # Alias pour compatibilité
    def get_performance_metrics(self) -> Dict:
        m = self.metrics()
        m["total_return_percent"] = m.pop("total_return_pct")
        m["win_rate_percent"] = m.pop("win_rate_pct")
        m["max_drawdown_percent"] = m.pop("max_drawdown_pct")
        m["current_cash"] = m.pop("cash")
        return m

    def print_summary(self):
        m = self.metrics()
        print(f"\n{'='*60}")
        print("📊 RÉSUMÉ DU PORTFOLIO")
        print(f"{'='*60}")
        print(f"💰 Capital initial:  ${m['initial_capital']:>12,.2f}")
        print(f"💵 Équité actuelle:  ${m['current_equity']:>12,.2f}")
        print(f"🎯 Return total:      {m['total_return_pct']:>+11.2f}%")
        print(f"📈 Trades total:      {m['total_trades']:>12}")
        print(f"✅ Gagnants:          {m['winning_trades']:>12}")
        print(f"❌ Perdants:          {m['losing_trades']:>12}")
        print(f"🏆 Win Rate:          {m['win_rate_pct']:>11.1f}%")
        print(f"📉 Max Drawdown:      {m['max_drawdown_pct']:>+11.2f}%")
        print(f"💸 Cash:             ${m['cash']:>12,.2f}")
        print(f"📊 Positions:         {m['open_positions']:>12}")
        print(f"{'='*60}")
