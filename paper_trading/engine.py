"""
Paper Trading Engine - 3 modes distincts :

  simulate  → backtest sur données mock (test rapide de stratégie)
  backtest  → backtest sur données historiques Bitget réelles
  paper     → VRAI paper trading temps réel (tourne 24/7 en tmux)
"""
import asyncio
from datetime import datetime, timezone
from typing import Dict, List
from colorama import Fore, init
from loguru import logger

from adapters.base import ExchangeAdapter
from core.signal_generator import SignalGenerator, SignalAction
from paper_trading.portfolio import PortfolioManager
from paper_trading.performance import PerformanceTracker
import paper_trading.state as state_store

init(autoreset=True)

# Durée en secondes de chaque timeframe
TIMEFRAME_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


def seconds_until_next_candle(timeframe: str, safety_margin: int = 30) -> int:
    """
    Calcule le nombre de secondes jusqu'à la fermeture de la prochaine bougie.
    safety_margin : délai supplémentaire pour que la bougie soit bien enregistrée.
    """
    period = TIMEFRAME_SECONDS.get(timeframe, 3600)
    now = datetime.now(timezone.utc).timestamp()
    next_close = (int(now) // period + 1) * period + safety_margin
    return max(1, int(next_close - now))


class PaperTradingEngine:
    """
    Moteur de trading exchange-agnostique.
    """

    def __init__(
        self,
        adapter: ExchangeAdapter,
        initial_capital: float = 10_000.0,
        symbols: List[str] = None,
        strategy: str = "rsi",
        position_size_pct: float = 0.30,
        slippage: float = 0.0005,
        state_file: str = "portfolio_state.json",
    ):
        self.adapter = adapter
        self.symbols = symbols or ["BTC/USDT:USDT", "ETH/USDT:USDT"]
        self.strategy = strategy
        self.position_size_pct = position_size_pct
        self.slippage = slippage
        self.state_file = state_file

        self.signal_gen = SignalGenerator()
        self.portfolio = PortfolioManager(initial_capital=initial_capital)
        self.daily_snapshots: List[Dict] = []

        logger.info(
            f"Engine prêt | {adapter.name} | capital={initial_capital:.0f} | "
            f"symbols={self.symbols} | strategy={strategy}"
        )

    # ------------------------------------------------------------------
    # MODE 1: BACKTEST (simulate ou données historiques réelles)
    # ------------------------------------------------------------------

    async def run_backtest(self, days: int = 30, timeframe: str = "1d"):
        """
        Backtest : rejoue des données historiques aussi vite que possible.
        Utile pour valider une stratégie rapidement.
        NE PAS confondre avec du paper trading réel.
        """
        print(f"\n{Fore.YELLOW}{'='*70}")
        print(f"{Fore.YELLOW}📊 MODE BACKTEST | {self.adapter.name.upper()} | {days} jours | TF: {timeframe}")
        print(f"{Fore.YELLOW}   ⚠️  Simulation historique - pas du temps réel")
        print(f"{Fore.YELLOW}{'='*70}")

        historical_data = self._load_historical(timeframe, limit=days + 55 + 10)
        if not historical_data:
            return

        warmup = 55
        available = min(len(df) for df in historical_data.values())
        actual_days = min(days, available - warmup)

        if actual_days <= 0:
            print(f"{Fore.RED}❌ Données insuffisantes pour {days} jours (disponible: {available})")
            return

        print(f"{Fore.WHITE}   Capital: ${self.portfolio.initial_capital:,.0f} | Stratégie: {self.strategy}")

        for day in range(actual_days):
            idx = warmup + day
            await self._process_candle(idx, historical_data, day_label=f"{day+1}/{actual_days}")
            if (day + 1) % 7 == 0:
                self._print_weekly(day + 1)

        self._print_final_report()

    # ------------------------------------------------------------------
    # MODE 2: PAPER TRADING TEMPS RÉEL (le vrai)
    # ------------------------------------------------------------------

    async def run_paper(self, timeframe: str = "1d", resume: bool = True):
        """
        Vrai paper trading : tourne indéfiniment, attend la fermeture
        de chaque bougie, persiste l'état entre les sessions.

        Conçu pour fonctionner en session tmux longue durée.
        Ctrl+C pour arrêter proprement (l'état est sauvegardé).
        """
        print(f"\n{Fore.GREEN}{'='*70}")
        print(f"{Fore.GREEN}🔴 PAPER TRADING TEMPS RÉEL | {self.adapter.name.upper()} | TF: {timeframe}")
        print(f"{Fore.GREEN}   Ctrl+C pour arrêter (état sauvegardé automatiquement)")
        print(f"{Fore.GREEN}{'='*70}")

        # Restaurer l'état précédent si disponible
        if resume:
            saved = state_store.load(self.state_file)
            if saved:
                self.portfolio = saved
                m = self.portfolio.metrics()
                print(f"\n{Fore.CYAN}📂 État restauré:")
                print(f"   Cash: ${m['cash']:,.2f} | Equity: ${m['current_equity']:,.2f}")
                print(f"   Positions: {list(self.portfolio.get_positions().keys()) or 'aucune'}")
                print(f"   Trades effectués: {m['total_trades']}")
            else:
                print(f"\n{Fore.WHITE}🆕 Nouvelle session (capital: ${self.portfolio.initial_capital:,.0f})")

        cycle = 0
        try:
            while True:
                cycle += 1
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"\n{Fore.BLUE}{'='*50}")
                print(f"{Fore.BLUE}🕐 CYCLE #{cycle} | {now}")
                print(f"{Fore.BLUE}{'='*50}")

                await self._run_live_cycle(timeframe)

                # Sauvegarder après chaque cycle
                state_store.save(self.portfolio, self.state_file)
                print(f"{Fore.WHITE}💾 État sauvegardé → {self.state_file}")

                # Calculer et afficher le délai jusqu'au prochain cycle
                wait_sec = seconds_until_next_candle(timeframe)
                next_time = datetime.fromtimestamp(
                    datetime.now().timestamp() + wait_sec
                ).strftime("%H:%M:%S")
                print(f"{Fore.CYAN}⏰ Prochain cycle à {next_time} "
                      f"(dans {wait_sec//3600}h {(wait_sec%3600)//60}min {wait_sec%60}s)")

                # Rapport d'équité courant
                m = self.portfolio.metrics()
                print(f"{Fore.WHITE}📊 Équité: ${m['current_equity']:,.2f} "
                      f"({m['total_return_pct']:+.2f}%) | "
                      f"Trades: {m['total_trades']} | "
                      f"Positions: {m['open_positions']}")

                await asyncio.sleep(wait_sec)

        except asyncio.CancelledError:
            pass
        except KeyboardInterrupt:
            pass
        finally:
            # Sauvegarde finale propre
            state_store.save(self.portfolio, self.state_file)
            print(f"\n{Fore.GREEN}✅ Arrêt propre - état sauvegardé dans {self.state_file}")
            self._print_final_report()

    async def _run_live_cycle(self, timeframe: str):
        """Un cycle de trading : fetch → signal → execute pour chaque symbole."""
        current_prices = {}

        for sym in self.symbols:
            try:
                df = self.adapter.get_ohlcv(sym, timeframe, limit=200)
                if df.empty:
                    logger.warning(f"Données vides pour {sym}")
                    continue

                price = df["close"].iloc[-1]
                current_prices[sym] = price

                signal = self.signal_gen.generate_signal(sym, df, self.strategy)
                self._print_signal(sym, signal.action, price, signal.message)
                await self._execute(sym, signal.action, price)

            except Exception as e:
                logger.error(f"Erreur cycle {sym}: {e}")

        if current_prices:
            self.portfolio.update_prices(current_prices)
            self._snapshot(current_prices)

    # ------------------------------------------------------------------
    # Commun aux deux modes
    # ------------------------------------------------------------------

    def _load_historical(self, timeframe: str, limit: int) -> Dict:
        """Charge les données historiques depuis l'adapter."""
        print(f"\n{Fore.CYAN}📡 Chargement données ({self.adapter.name})...")
        data = {}
        for sym in self.symbols:
            try:
                df = self.adapter.get_ohlcv(sym, timeframe, limit)
                if not df.empty:
                    data[sym] = df
                    print(f"{Fore.GREEN}  ✅ {sym}: {len(df)} bougies")
                else:
                    print(f"{Fore.RED}  ❌ {sym}: données vides")
            except Exception as e:
                print(f"{Fore.RED}  ❌ {sym}: {e}")
        return data

    async def _process_candle(self, idx: int, historical_data: Dict, day_label: str):
        """Traite une bougie historique (mode backtest)."""
        print(f"\n{Fore.BLUE}📅 JOUR {day_label}")
        print(f"{Fore.BLUE}{'-'*40}")

        current_prices = {}

        for sym in self.symbols:
            if sym not in historical_data:
                continue
            df = historical_data[sym]
            if idx >= len(df):
                continue

            window = df.iloc[: idx + 1]
            price = window["close"].iloc[-1]
            current_prices[sym] = price

            try:
                signal = self.signal_gen.generate_signal(sym, window, self.strategy)
                self._print_signal(sym, signal.action, price, signal.message)
                await self._execute(sym, signal.action, price)
            except Exception as e:
                logger.error(f"Signal {sym}: {e}")

        self.portfolio.update_prices(current_prices)
        self._snapshot(current_prices)

    async def _execute(self, symbol: str, action: SignalAction, price: float):
        """Exécute l'action si applicable."""
        positions = self.portfolio.get_positions()

        if symbol in positions and action in (SignalAction.SELL, SignalAction.CLOSE):
            sell_price = price * (1 - self.slippage)
            try:
                order = self.portfolio.close_position(symbol, sell_price)
                color = Fore.GREEN if order["pnl"] > 0 else Fore.RED
                print(
                    f"{color}    📤 VENTE {order['quantity']:.6f} {symbol} @ ${sell_price:,.2f}"
                    f" | PnL: ${order['pnl']:+,.2f} ({order['pnl_percent']:+.2f}%)"
                )
            except Exception as e:
                logger.error(f"Vente {symbol}: {e}")

        elif symbol not in positions and action == SignalAction.BUY:
            cash = self.portfolio.get_balance()
            invest = cash * self.position_size_pct
            if invest < 10:
                return
            buy_price = price * (1 + self.slippage)
            try:
                order = self.portfolio.buy(symbol, invest, buy_price)
                print(
                    f"{Fore.GREEN}    📥 ACHAT {order['quantity']:.6f} {symbol} @ ${buy_price:,.2f}"
                    f" (${invest:,.0f})"
                )
            except Exception as e:
                logger.error(f"Achat {symbol}: {e}")

    def _snapshot(self, prices: Dict):
        equity = self.portfolio.get_total_equity(prices)
        self.daily_snapshots.append({
            "date": datetime.now(),
            "equity": equity,
            "cash": self.portfolio.get_balance(),
            "positions": len(self.portfolio.get_positions()),
        })

    def _print_signal(self, symbol: str, action: SignalAction, price: float, message: str = ""):
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
        hint = f" — {message}" if message and action != SignalAction.HOLD else ""
        print(f"  📊 {symbol} | ${price:,.2f} | {c}{labels[action]}{hint}")

    def _print_weekly(self, day: int):
        if not self.daily_snapshots:
            return
        equity = self.daily_snapshots[-1]["equity"]
        ret = (equity / self.portfolio.initial_capital - 1) * 100
        print(f"\n{Fore.CYAN}  📈 Semaine {day//7}: ${equity:,.2f} ({ret:+.2f}%)")

    def _print_final_report(self):
        print(f"\n{Fore.GREEN}{'='*70}")
        print(f"{Fore.GREEN}🏁 RAPPORT FINAL")
        print(f"{Fore.GREEN}{'='*70}")
        self.portfolio.print_summary()

        completed = [t for t in self.portfolio.trade_history if t.pnl != 0]
        if completed:
            print(f"\n{Fore.WHITE}📋 TRADES COMPLÉTÉS:")
            for t in completed:
                color = Fore.GREEN if t.pnl > 0 else Fore.RED
                print(f"  {t.side.value.upper():4s} {t.symbol} | {color}${t.pnl:+,.2f} ({t.pnl_percent:+.2f}%)")

        tracker = PerformanceTracker(self.portfolio, self.daily_snapshots)
        tracker.print_report()
