"""
State persistence - Sauvegarde/restauration du portfolio entre sessions.
Le paper trading dure des jours/semaines, l'état doit survivre aux redémarrages.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from loguru import logger

from paper_trading.portfolio import PortfolioManager, Position, Trade, TradeSide

STATE_FILE = "portfolio_state.json"


def save(portfolio: PortfolioManager, filepath: str = STATE_FILE):
    """Sauvegarde l'état complet du portfolio sur disque."""
    state = {
        "saved_at": datetime.now().isoformat(),
        "initial_capital": portfolio.initial_capital,
        "cash": portfolio.cash,
        "commission_rate": portfolio.commission_rate,
        "total_trades": portfolio.total_trades,
        "winning_trades": portfolio.winning_trades,
        "losing_trades": portfolio.losing_trades,
        "peak_equity": portfolio.peak_equity,
        "max_drawdown": portfolio.max_drawdown,
        "positions": {
            sym: {
                "quantity": pos.quantity,
                "entry_price": pos.entry_price,
                "entry_time": pos.entry_time.isoformat(),
                "current_price": pos.current_price,
            }
            for sym, pos in portfolio.positions.items()
        },
        "trade_history": [
            {
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side.value,
                "quantity": t.quantity,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                "commission": t.commission,
                "pnl": t.pnl,
                "pnl_percent": t.pnl_percent,
            }
            for t in portfolio.trade_history
        ],
    }
    Path(filepath).write_text(json.dumps(state, indent=2))
    logger.debug(f"État sauvegardé → {filepath}")


def load(filepath: str = STATE_FILE) -> Optional[PortfolioManager]:
    """
    Restaure un portfolio depuis un fichier d'état.
    Retourne None si le fichier n'existe pas.
    """
    path = Path(filepath)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text())

        portfolio = PortfolioManager(
            initial_capital=data["initial_capital"],
            commission_rate=data.get("commission_rate", 0.001),
        )

        # Restaurer le cash et métriques
        portfolio.cash = data["cash"]
        portfolio.total_trades = data["total_trades"]
        portfolio.winning_trades = data["winning_trades"]
        portfolio.losing_trades = data["losing_trades"]
        portfolio.peak_equity = data["peak_equity"]
        portfolio.max_drawdown = data["max_drawdown"]

        # Restaurer les positions
        for sym, pos_data in data.get("positions", {}).items():
            portfolio.positions[sym] = Position(
                symbol=sym,
                quantity=pos_data["quantity"],
                entry_price=pos_data["entry_price"],
                entry_time=datetime.fromisoformat(pos_data["entry_time"]),
                current_price=pos_data["current_price"],
            )

        # Restaurer l'historique des trades
        for t_data in data.get("trade_history", []):
            trade = Trade(
                id=t_data["id"],
                symbol=t_data["symbol"],
                side=TradeSide(t_data["side"]),
                quantity=t_data["quantity"],
                entry_price=t_data["entry_price"],
                exit_price=t_data.get("exit_price"),
                entry_time=datetime.fromisoformat(t_data["entry_time"]) if t_data.get("entry_time") else None,
                exit_time=datetime.fromisoformat(t_data["exit_time"]) if t_data.get("exit_time") else None,
                commission=t_data.get("commission", 0),
                pnl=t_data.get("pnl", 0),
                pnl_percent=t_data.get("pnl_percent", 0),
            )
            portfolio.trade_history.append(trade)

        saved_at = data.get("saved_at", "inconnu")
        logger.info(f"État restauré depuis {filepath} (sauvegardé: {saved_at})")
        return portfolio

    except Exception as e:
        logger.error(f"Échec restauration état: {e}")
        return None


def status(filepath: str = STATE_FILE) -> dict:
    """Retourne un résumé de l'état sauvegardé sans charger le portfolio."""
    path = Path(filepath)
    if not path.exists():
        return {"exists": False}

    try:
        data = json.loads(path.read_text())
        return {
            "exists": True,
            "saved_at": data.get("saved_at"),
            "cash": data.get("cash"),
            "initial_capital": data.get("initial_capital"),
            "total_trades": data.get("total_trades"),
            "positions": list(data.get("positions", {}).keys()),
        }
    except Exception:
        return {"exists": True, "readable": False}
