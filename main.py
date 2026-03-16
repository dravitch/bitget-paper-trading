#!/usr/bin/env python3
"""
Bitget Paper Trading System
============================

MODES:
  simulate   Backtest rapide sur données simulées (test de stratégie)
  backtest   Backtest sur données historiques Bitget réelles
  paper      VRAI paper trading temps réel (tourne 24/7 en tmux)

EXEMPLES:
  python main.py --mode simulate --days 30
  python main.py --mode backtest --days 60
  python main.py --mode paper --timeframe 1h          # tourne indéfiniment
  python main.py --mode paper --timeframe 1d --reset  # recommencer à zéro
  python main.py --profile                            # profil exchange live
  python main.py --status                             # état du portfolio actuel
"""
import asyncio
import argparse
import os
import sys
from dotenv import load_dotenv
from loguru import logger

load_dotenv()
logger.remove()
logger.add(sys.stderr, level="WARNING")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Bitget Paper Trading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["simulate", "backtest", "paper"],
        default="simulate",
        help="simulate=mock rapide | backtest=historique Bitget | paper=temps réel 24/7",
    )
    parser.add_argument(
        "--timeframe",
        default="1d",
        choices=["1m", "5m", "15m", "30m", "1h", "4h", "1d"],
        help="Timeframe des bougies (paper mode: détermine la fréquence des cycles)",
    )
    parser.add_argument("--capital", type=float, default=10_000.0, help="Capital initial ($)")
    parser.add_argument("--days", type=int, default=30, help="Jours à simuler (simulate/backtest)")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTC/USDT:USDT", "ETH/USDT:USDT"],
        help="Paires de trading",
    )
    parser.add_argument(
        "--strategy",
        choices=["rsi", "moving_average"],
        default="rsi",
        help="Stratégie de génération de signaux",
    )
    parser.add_argument(
        "--state-file",
        default="portfolio_state.json",
        help="Fichier de sauvegarde de l'état (paper mode)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Ignorer l'état sauvegardé et repartir à zéro (paper mode)",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Affiche le profil exchange live (spreads, frais, liquidité) puis quitte",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Affiche l'état du portfolio sauvegardé puis quitte",
    )
    parser.add_argument("--verbose", action="store_true", help="Logs détaillés")
    return parser.parse_args()


def build_adapter(mode: str, symbols: list):
    """Crée l'adapter approprié selon le mode."""
    if mode in ("backtest", "paper", "live"):
        api_key = os.getenv("BITGET_API_KEY")
        secret = os.getenv("BITGET_SECRET")
        password = os.getenv("BITGET_PASSWORD")

        if not all([api_key, secret, password]):
            print("❌ Clés API manquantes dans .env")
            print("   Copiez .env.example en .env et renseignez vos clés Bitget.")
            print("   Ou utilisez --mode simulate pour tester sans clés.")
            sys.exit(1)

        from adapters.bitget import BitgetAdapter
        return BitgetAdapter(api_key=api_key, secret=secret, password=password)
    else:
        from adapters.mock import MockAdapter
        return MockAdapter(symbols=symbols)


async def show_exchange_profile(symbols: list):
    """Affiche le profil exchange réel (toujours Bitget)."""
    adapter = build_adapter("backtest", symbols)

    print(f"\n{'='*60}")
    print(f"📡 PROFIL EXCHANGE: BITGET (live)")
    print(f"{'='*60}")

    for sym in symbols:
        try:
            profile = adapter.get_exchange_profile(sym)
            print(f"\n  {sym}")
            print(f"    Prix actuel:   ${profile['last_price']:>12,.4f}")
            print(f"    Bid:           ${profile['bid']:>12,.4f}")
            print(f"    Ask:           ${profile['ask']:>12,.4f}")
            print(f"    Spread:        {profile['spread_pct']:>11.4f}%")
            print(f"    Maker fee:     {profile['maker_fee']*100:>11.3f}%")
            print(f"    Taker fee:     {profile['taker_fee']*100:>11.3f}%")
            print(f"    Volume 24h:    ${profile['volume_24h']:>12,.0f}")
            print(f"    Liquidité bid: {profile['bid_liquidity_5lvl']:>12.4f}")
            print(f"    Liquidité ask: {profile['ask_liquidity_5lvl']:>12.4f}")
        except Exception as e:
            print(f"  ❌ {sym}: {e}")


def show_status(state_file: str):
    """Affiche l'état du portfolio sauvegardé."""
    import paper_trading.state as state_store

    info = state_store.status(state_file)
    if not info.get("exists"):
        print(f"ℹ️  Aucun état sauvegardé ({state_file})")
        print("   Lancez --mode paper pour démarrer le paper trading.")
        return

    print(f"\n{'='*50}")
    print(f"📂 ÉTAT PORTFOLIO — {state_file}")
    print(f"{'='*50}")
    print(f"  Sauvegardé:     {info.get('saved_at', 'inconnu')}")
    print(f"  Capital initial: ${info.get('initial_capital', 0):,.2f}")
    print(f"  Cash actuel:     ${info.get('cash', 0):,.2f}")
    print(f"  Trades:          {info.get('total_trades', 0)}")
    positions = info.get("positions", [])
    if positions:
        print(f"  Positions:       {', '.join(positions)}")
    else:
        print("  Positions:       aucune")

    # Charger pour avoir les métriques complètes
    portfolio = state_store.load(state_file)
    if portfolio:
        m = portfolio.metrics()
        print(f"\n  Return:          {m['total_return_pct']:+.2f}%")
        print(f"  Win Rate:        {m['win_rate_pct']:.1f}%")
        print(f"  Max Drawdown:    {m['max_drawdown_pct']:.2f}%")


async def run(args):
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    # Commandes d'information (pas de trading)
    if args.profile:
        await show_exchange_profile(args.symbols)
        return

    if args.status:
        show_status(args.state_file)
        return

    # Construire l'adapter
    adapter = build_adapter(args.mode, args.symbols)

    from paper_trading.engine import PaperTradingEngine

    engine = PaperTradingEngine(
        adapter=adapter,
        initial_capital=args.capital,
        symbols=args.symbols,
        strategy=args.strategy,
        state_file=args.state_file,
    )

    if args.mode == "simulate":
        print(f"\n{'='*60}")
        print("📊 MODE BACKTEST (données simulées)")
        print(f"{'='*60}")
        await engine.run_backtest(days=args.days, timeframe=args.timeframe)

    elif args.mode == "backtest":
        await engine.run_backtest(days=args.days, timeframe=args.timeframe)

    elif args.mode == "paper":
        resume = not args.reset
        if args.reset:
            import os
            if os.path.exists(args.state_file):
                os.remove(args.state_file)
                print(f"🗑️  État précédent supprimé ({args.state_file})")
        await engine.run_paper(timeframe=args.timeframe, resume=resume)


if __name__ == "__main__":
    args = parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interruption — état sauvegardé.")
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        if args.verbose:
            raise
        sys.exit(1)
