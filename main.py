#!/usr/bin/env python3
"""
Bitget Paper Trading System
============================
Simulation de trading avec données réelles ou simulées.

Usage:
  python main.py                                    # simulation par défaut
  python main.py --mode simulate --days 30          # données simulées, 30 jours
  python main.py --mode live-data --days 60         # données live Bitget
  python main.py --symbols BTC/USDT:USDT ETH/USDT:USDT --strategy rsi
  python main.py --profile                          # affiche le profil de l'exchange
"""
import asyncio
import argparse
import os
import sys
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# Configuration du logger
logger.remove()
logger.add(sys.stderr, level="WARNING")  # Silencieux par défaut (INFO en --verbose)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Bitget Paper Trading - Simulation avec données réelles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["simulate", "live-data"],
        default="simulate",
        help="simulate = données mock | live-data = données Bitget réelles",
    )
    parser.add_argument("--capital", type=float, default=10_000.0, help="Capital initial en USDT")
    parser.add_argument("--days", type=int, default=30, help="Nombre de jours à simuler")
    parser.add_argument(
        "--symbols",
        nargs="+",
        default=["BTC/USDT:USDT", "ETH/USDT:USDT"],
        help="Paires de trading",
    )
    parser.add_argument(
        "--strategy",
        choices=["rsi", "moving_average", "combined"],
        default="rsi",
        help="Stratégie de trading",
    )
    parser.add_argument(
        "--profile",
        action="store_true",
        help="Affiche le profil de l'exchange (spreads, frais, liquidité) puis quitte",
    )
    parser.add_argument("--verbose", action="store_true", help="Logs détaillés")
    return parser.parse_args()


def build_adapter(mode: str, symbols: list):
    """Crée l'adapter d'exchange approprié."""
    if mode == "live-data":
        api_key = os.getenv("BITGET_API_KEY")
        secret = os.getenv("BITGET_SECRET")
        password = os.getenv("BITGET_PASSWORD")

        if not all([api_key, secret, password]):
            print("❌ Clés API manquantes. Copiez .env.example en .env et remplissez vos clés.")
            print("   Ou lancez en mode simulate: python main.py --mode simulate")
            sys.exit(1)

        from adapters.bitget import BitgetAdapter
        return BitgetAdapter(api_key=api_key, secret=secret, password=password)
    else:
        from adapters.mock import MockAdapter
        return MockAdapter(symbols=symbols)


async def show_exchange_profile(adapter, symbols: list):
    """Affiche le profil complet de l'exchange pour chaque symbole."""
    print(f"\n{'='*60}")
    print(f"📡 PROFIL EXCHANGE: {adapter.name.upper()}")
    print(f"{'='*60}")

    for sym in symbols:
        try:
            profile = adapter.get_exchange_profile(sym)
            print(f"\n{sym}")
            print(f"  Prix:          ${profile['last_price']:,.4f}")
            print(f"  Bid/Ask:       ${profile['bid']:,.4f} / ${profile['ask']:,.4f}")
            print(f"  Spread:        {profile['spread_pct']:.4f}%")
            print(f"  Maker fee:     {profile['maker_fee']*100:.3f}%")
            print(f"  Taker fee:     {profile['taker_fee']*100:.3f}%")
            print(f"  Volume 24h:    ${profile['volume_24h']:,.0f}")
            print(f"  Liquidité bid: {profile['bid_liquidity_5lvl']:.4f}")
            print(f"  Liquidité ask: {profile['ask_liquidity_5lvl']:.4f}")
        except Exception as e:
            print(f"  ❌ {sym}: {e}")


async def run(args):
    """Point d'entrée principal."""
    if args.verbose:
        logger.remove()
        logger.add(sys.stderr, level="INFO")

    adapter = build_adapter(args.mode, args.symbols)

    if args.profile:
        await show_exchange_profile(adapter, args.symbols)
        return

    # Stratégie combinée = consensus RSI + MA
    strategy = args.strategy
    if strategy == "combined":
        print("ℹ️  Mode combiné: consensus RSI + Moving Average")
        strategy = "rsi"  # TODO: implémenter consensus multi-stratégie

    from paper_trading.engine import PaperTradingEngine

    engine = PaperTradingEngine(
        adapter=adapter,
        initial_capital=args.capital,
        symbols=args.symbols,
        strategy=strategy,
    )

    await engine.run(days=args.days)


if __name__ == "__main__":
    args = parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\n\n⚠️  Interruption utilisateur.")
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        if args.verbose:
            raise
        sys.exit(1)
