"""
Paper Trading Engine - Moteur principal de simulation.
Utilise un adapter d'exchange pour les données (mock ou live).
"""
import asyncio
from datetime import datetime
from typing import Dict, List
from colorama import Fore, init
from loguru import logger

from adapters.base import ExchangeAdapter
from core.signal_generator import SignalGenerator, SignalAction
from paper_trading.portfolio import PortfolioManager
from paper_trading.performance import PerformanceTracker

init(autoreset=True)


class PaperTradingEngine:
    """
    Moteur de paper trading exchange-agnostique.

    Paramètres:
        adapter:          Adapter d'exchange (MockAdapter ou BitgetAdapter)
        initial_capital:  Capital virtuel de départ
        symbols:          Liste des paires à trader
        strategy:         Nom de la stratégie ('rsi', 'moving_average', 'combined')
        position_size_pct: Fraction du cash allouée par trade (0.0 à 1.0)
        slippage:         Slippage simulé (fraction du prix)
    """

    def __init__(
        self,
        adapter: ExchangeAdapter,
        initial_capital: float = 10_000.0,
        symbols: List[str] = None,
        strategy: str = "rsi",
        position_size_pct: float = 0.30,
        slippage: float = 0.0005,
    ):
        self.adapter = adapter
        self.portfolio = PortfolioManager(initial_capital=initial_capital)
        self.signal_gen = SignalGenerator()
        self.symbols = symbols or ["BTC/USDT:USDT", "ETH/USDT:USDT"]
        self.strategy = strategy
        self.position_size_pct = position_size_pct
        self.slippage = slippage

        self.historical_data: Dict = {}
        self.daily_snapshots: List[Dict] = []

        logger.info(
            f"PaperTradingEngine prêt | exchange={adapter.name} | "
            f"capital={initial_capital:.0f} | symbols={self.symbols}"
        )

    # ------------------------------------------------------------------
    # Chargement des données
    # ------------------------------------------------------------------

    def load_data(self, timeframe: str = "1d", limit: int = 200):
        """Charge les données historiques depuis l'adapter."""
        print(f"\n{Fore.CYAN}📡 Chargement des données ({self.adapter.name})...")
        for sym in self.symbols:
            try:
                df = self.adapter.get_ohlcv(sym, timeframe, limit)
                if not df.empty:
                    self.historical_data[sym] = df
                    print(f"{Fore.GREEN}  ✅ {sym}: {len(df)} bougies")
                else:
                    print(f"{Fore.RED}  ❌ {sym}: données vides")
            except Exception as e:
                print(f"{Fore.RED}  ❌ {sym}: {e}")

    # ------------------------------------------------------------------
    # Boucle principale
    # ------------------------------------------------------------------

    async def run(self, days: int = 30):
        """Lance la simulation sur 'days' jours."""
        if not self.historical_data:
            self.load_data()

        if not self.historical_data:
            print(f"{Fore.RED}❌ Aucune donnée disponible. Arrêt.")
            return

        available = min(len(df) for df in self.historical_data.values())
        warmup = 55  # bougies nécessaires aux indicateurs
        actual_days = min(days, available - warmup)

        if actual_days <= 0:
            print(f"{Fore.RED}❌ Pas assez de données (besoin: {warmup + days}, disponible: {available})")
            return

        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"{Fore.CYAN}🚀 PAPER TRADING | {self.adapter.name.upper()} | {actual_days} jours")
        print(f"{Fore.CYAN}{'='*70}")
        print(f"{Fore.WHITE}   Stratégie: {self.strategy} | Capital: ${self.portfolio.initial_capital:,.0f}")

        for day in range(actual_days):
            idx = warmup + day
            await self._process_day(idx, day + 1, actual_days)

            if (day + 1) % 7 == 0:
                self._print_weekly(day + 1)

        self._print_final()

    async def _process_day(self, data_idx: int, day_num: int, total: int):
        """Traite une journée de trading."""
        print(f"\n{Fore.BLUE}📅 JOUR {day_num}/{total}")
        print(f"{Fore.BLUE}{'-'*50}")

        current_prices = {}

        for sym in self.symbols:
            if sym not in self.historical_data:
                continue

            df = self.historical_data[sym]
            if data_idx >= len(df):
                continue

            window = df.iloc[: data_idx + 1]
            price = window["close"].iloc[-1]
            current_prices[sym] = price

            # Générer signal
            try:
                signal = self.signal_gen.generate_signal(sym, window, self.strategy)
                action = signal.action
            except Exception as e:
                logger.error(f"Signal {sym}: {e}")
                action = SignalAction.HOLD

            self._print_signal(sym, action, price)
            await self._execute(sym, action, price, window.index[-1])

        self.portfolio.update_prices(current_prices)
        self._snapshot(current_prices, data_idx)

    async def _execute(self, symbol: str, action: SignalAction, price: float, date):
        """Exécute l'action si applicable."""
        positions = self.portfolio.get_positions()

        if symbol in positions and action in (SignalAction.SELL, SignalAction.CLOSE):
            sell_price = price * (1 - self.slippage)
            try:
                order = self.portfolio.close_position(symbol, sell_price)
                color = Fore.GREEN if order["pnl"] > 0 else Fore.RED
                print(
                    f"{color}  📤 VENTE {order['quantity']:.6f} {symbol} @ ${sell_price:,.2f}"
                    f" | PnL: ${order['pnl']:+,.2f} ({order['pnl_percent']:+.2f}%)"
                )
            except Exception as e:
                print(f"{Fore.RED}  ❌ Vente échouée {symbol}: {e}")

        elif symbol not in positions and action == SignalAction.BUY:
            cash = self.portfolio.get_balance()
            invest = cash * self.position_size_pct
            if invest < 10:
                return
            buy_price = price * (1 + self.slippage)
            try:
                order = self.portfolio.buy(symbol, invest, buy_price)
                print(
                    f"{Fore.GREEN}  📥 ACHAT  {order['quantity']:.6f} {symbol} @ ${buy_price:,.2f}"
                    f" (investissement: ${invest:,.0f})"
                )
            except Exception as e:
                print(f"{Fore.RED}  ❌ Achat échoué {symbol}: {e}")

    def _snapshot(self, prices: Dict, idx: int):
        equity = self.portfolio.get_total_equity(prices)
        self.daily_snapshots.append(
            {
                "day": idx,
                "date": datetime.now(),
                "equity": equity,
                "cash": self.portfolio.get_balance(),
                "positions": len(self.portfolio.get_positions()),
            }
        )

    def _print_signal(self, symbol: str, action: SignalAction, price: float):
        colors = {
            SignalAction.BUY: Fore.GREEN,
            SignalAction.SELL: Fore.RED,
            SignalAction.CLOSE: Fore.YELLOW,
            SignalAction.HOLD: Fore.WHITE,
        }
        labels = {
            SignalAction.BUY: "ACHAT",
            SignalAction.SELL: "VENTE",
            SignalAction.CLOSE: "FERMETURE",
            SignalAction.HOLD: "MAINTIEN",
        }
        c = colors[action]
        print(f"{Fore.WHITE}  📊 {symbol} | ${price:,.2f} | {c}{labels[action]}")

    def _print_weekly(self, week: int):
        if not self.daily_snapshots:
            return
        equity = self.daily_snapshots[-1]["equity"]
        ret = (equity / self.portfolio.initial_capital - 1) * 100
        print(f"\n{Fore.CYAN}  📈 Semaine {week//7}: Équité ${equity:,.2f} ({ret:+.2f}%)")

    def _print_final(self):
        print(f"\n{Fore.GREEN}{'='*70}")
        print(f"{Fore.GREEN}🏁 RAPPORT FINAL")
        print(f"{Fore.GREEN}{'='*70}")
        self.portfolio.print_summary()

        if self.portfolio.trade_history:
            print(f"\n{Fore.WHITE}📋 TRADES RÉALISÉS:")
            for t in self.portfolio.trade_history:
                if t.pnl != 0:
                    color = Fore.GREEN if t.pnl > 0 else Fore.RED
                    print(f"  {t.side.value.upper():4s} {t.symbol} | {color}PnL: ${t.pnl:+,.2f}")

        # Générer rapport de performance
        tracker = PerformanceTracker(self.portfolio, self.daily_snapshots)
        tracker.print_report()
