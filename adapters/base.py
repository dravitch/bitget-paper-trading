"""
Abstract base class for exchange adapters.
All exchanges must implement this interface.
"""
from abc import ABC, abstractmethod
from typing import Dict, List
import pandas as pd


class ExchangeAdapter(ABC):
    """
    Interface commune pour tous les exchanges.
    Permet de switcher d'exchange sans toucher au moteur de trading.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nom de l'exchange (ex: 'bitget', 'binance')"""

    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: str = "1d", limit: int = 200) -> pd.DataFrame:
        """
        Données OHLCV historiques.
        Returns: DataFrame avec colonnes [open, high, low, close, volume], index datetime
        """

    @abstractmethod
    def get_orderbook(self, symbol: str, depth: int = 10) -> Dict:
        """
        Order book en temps réel.
        Returns: {'bids': [[price, qty]...], 'asks': [[price, qty]...]}
        """

    @abstractmethod
    def get_ticker(self, symbol: str) -> Dict:
        """
        Prix et stats 24h.
        Returns: {'last': float, 'bid': float, 'ask': float, 'volume': float, ...}
        """

    @abstractmethod
    def get_trading_fees(self, symbol: str) -> Dict:
        """
        Structure de frais réelle.
        Returns: {'maker': float, 'taker': float}
        """

    def get_exchange_profile(self, symbol: str) -> Dict:
        """
        Profil complet de l'exchange pour un symbole.
        Combine spread, fees, liquidité - base de la simulation réaliste.
        """
        ticker = self.get_ticker(symbol)
        fees = self.get_trading_fees(symbol)
        orderbook = self.get_orderbook(symbol, depth=5)

        bid = ticker.get("bid", 0)
        ask = ticker.get("ask", 0)
        mid = (bid + ask) / 2 if bid and ask else ticker.get("last", 0)
        spread = (ask - bid) / mid if mid > 0 else 0

        # Liquidité côté bid et ask (5 premiers niveaux)
        bid_liquidity = sum(qty for _, qty in orderbook.get("bids", [])[:5])
        ask_liquidity = sum(qty for _, qty in orderbook.get("asks", [])[:5])

        return {
            "exchange": self.name,
            "symbol": symbol,
            "last_price": ticker.get("last", 0),
            "bid": bid,
            "ask": ask,
            "spread_pct": spread * 100,
            "maker_fee": fees.get("maker", 0.001),
            "taker_fee": fees.get("taker", 0.001),
            "bid_liquidity_5lvl": bid_liquidity,
            "ask_liquidity_5lvl": ask_liquidity,
            "volume_24h": ticker.get("quoteVolume", 0),
        }
