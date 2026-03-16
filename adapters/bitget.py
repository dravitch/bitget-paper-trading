"""
Bitget exchange adapter using ccxt.
Utilise les données live du mainnet pour alimenter le paper trading.
"""
import ccxt
import pandas as pd
from typing import Dict
from loguru import logger
from .base import ExchangeAdapter


class BitgetAdapter(ExchangeAdapter):
    """
    Adapter Bitget via ccxt.
    Aucun ordre réel n'est passé - uniquement lecture des données de marché.
    """

    def __init__(self, api_key: str = None, secret: str = None, password: str = None):
        self.exchange = ccxt.bitget(
            {
                "apiKey": api_key,
                "secret": secret,
                "password": password,
                "enableRateLimit": True,
            }
        )
        self._markets_loaded = False
        logger.info("BitgetAdapter initialisé (lecture seule - paper trading)")

    def _ensure_markets(self):
        if not self._markets_loaded:
            self.exchange.load_markets()
            self._markets_loaded = True

    @property
    def name(self) -> str:
        return "bitget"

    def get_ohlcv(self, symbol: str, timeframe: str = "1d", limit: int = 200) -> pd.DataFrame:
        """Données OHLCV historiques depuis Bitget."""
        self._ensure_markets()
        try:
            raw = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)
            return df
        except Exception as e:
            logger.error(f"get_ohlcv {symbol}: {e}")
            raise

    def get_orderbook(self, symbol: str, depth: int = 10) -> Dict:
        """Order book live Bitget."""
        self._ensure_markets()
        try:
            return self.exchange.fetch_order_book(symbol, depth)
        except Exception as e:
            logger.error(f"get_orderbook {symbol}: {e}")
            return {"bids": [], "asks": []}

    def get_ticker(self, symbol: str) -> Dict:
        """Ticker 24h Bitget."""
        self._ensure_markets()
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            logger.error(f"get_ticker {symbol}: {e}")
            return {}

    def get_trading_fees(self, symbol: str) -> Dict:
        """Frais réels Bitget pour ce symbole."""
        self._ensure_markets()
        try:
            market = self.exchange.market(symbol)
            return {
                "maker": market.get("maker", 0.001),
                "taker": market.get("taker", 0.001),
            }
        except Exception as e:
            logger.warning(f"get_trading_fees {symbol}: {e} - utilisation des frais par défaut")
            return {"maker": 0.001, "taker": 0.001}
