"""
Performance Tracker - Analyse et rapport de performance.
"""
import os
from datetime import datetime
from typing import Dict, List
from loguru import logger


class PerformanceTracker:
    """
    Calcule et affiche les métriques de performance d'une session de paper trading.
    """

    def __init__(self, portfolio, snapshots: List[Dict]):
        self.portfolio = portfolio
        self.snapshots = snapshots

    def print_report(self):
        """Affiche un rapport de performance textuel."""
        m = self.portfolio.metrics()

        if not self.snapshots:
            return

        equities = [s["equity"] for s in self.snapshots]
        initial = equities[0]
        final = equities[-1]
        peak = max(equities)
        trough = min(equities)

        print("\n📊 ANALYSE DE PERFORMANCE")
        print("-" * 40)
        print(f"  Équité initiale:  ${initial:>12,.2f}")
        print(f"  Équité finale:    ${final:>12,.2f}")
        print(f"  Peak:             ${peak:>12,.2f}")
        print(f"  Trough:           ${trough:>12,.2f}")
        print(f"  Return:           {m['total_return_pct']:>+11.2f}%")
        print(f"  Max Drawdown:     {m['max_drawdown_pct']:>+11.2f}%")
        print(f"  Win Rate:         {m['win_rate_pct']:>11.1f}%")
        print(f"  Trades:           {m['total_trades']:>12}")
        print("-" * 40)

    def save_report(self, output_dir: str = "performance_reports"):
        """Sauvegarde un rapport texte."""
        os.makedirs(output_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(output_dir, f"report_{ts}.txt")

        m = self.portfolio.metrics()
        lines = [
            f"PAPER TRADING REPORT - {datetime.now().isoformat()}",
            "=" * 50,
            f"Capital initial:  ${m['initial_capital']:,.2f}",
            f"Équité finale:    ${m['current_equity']:,.2f}",
            f"Return:           {m['total_return_pct']:+.2f}%",
            f"Max Drawdown:     {m['max_drawdown_pct']:+.2f}%",
            f"Win Rate:         {m['win_rate_pct']:.1f}%",
            f"Total Trades:     {m['total_trades']}",
            f"Gagnants:         {m['winning_trades']}",
            f"Perdants:         {m['losing_trades']}",
            "",
            "TRADES:",
        ]
        for t in self.portfolio.trade_history:
            if t.pnl != 0:
                lines.append(
                    f"  {t.side.value.upper():4s} {t.symbol} @ {t.exit_price:.2f}"
                    f" | PnL: ${t.pnl:+,.2f} ({t.pnl_percent:+.2f}%)"
                )

        with open(path, "w") as f:
            f.write("\n".join(lines))

        logger.info(f"Rapport sauvegardé: {path}")
        return path

    def plot_equity_curve(self, output_dir: str = "performance_reports"):
        """Génère et sauvegarde la courbe d'équité."""
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates

            if not self.snapshots:
                return

            os.makedirs(output_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(output_dir, f"equity_{ts}.png")

            equities = [s["equity"] for s in self.snapshots]
            days = list(range(len(equities)))

            fig, ax = plt.subplots(figsize=(12, 5))
            ax.plot(days, equities, linewidth=2, color="#2196F3")
            ax.axhline(y=equities[0], color="gray", linestyle="--", alpha=0.5, label="Capital initial")
            ax.fill_between(days, equities, equities[0], alpha=0.1, color="#2196F3")

            ax.set_title("Courbe d'Équité - Paper Trading", fontsize=14)
            ax.set_xlabel("Jours")
            ax.set_ylabel("Équité ($)")
            ax.legend()
            ax.grid(True, alpha=0.3)

            plt.tight_layout()
            plt.savefig(path, dpi=150)
            plt.close()

            logger.info(f"Graphique sauvegardé: {path}")
            return path

        except ImportError:
            logger.warning("matplotlib non disponible - graphique non généré")
