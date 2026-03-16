"""
Mock exchange adapter for testing without API keys.
Génère des données OHLCV réalistes basées sur une seed fixe.
"""
import numpy as np
import pandas as pd
from typing import Dict, List
from .base import ExchangeAdapter

# Prix de base par symbole (approximation réaliste)
_BASE_PRICES = {
    "BTC/USDT:USDT": 50000,
    "ETH/USDT:USDT": 3000,
    "SOL/USDT:USDT": 150,
    "BTC/USDT": 50000,
    "ETH/USDT": 3000,
}
_DEFAULT_PRICE = 100
_DEFAULT_VOLATILITY = 0.02


class MockAdapter(ExchangeAdapter):
    """
    Adapter simulé pour tests et développement.
    Données déterministes (seed fixe) pour reproduire les résultats.
    """

    def __init__(self, symbols: List[str] = None, seed: int = 42):
        self.symbols = symbols or ["BTC/USDT:USDT", "ETH/USDT:USDT"]
        self.seed = seed

    @property
    def name(self) -> str:
        return "mock"

    def get_ohlcv(self, symbol: str, timeframe: str = "1d", limit: int = 200) -> pd.DataFrame:
        """Génère des données OHLCV simulées réalistes."""
        base_price = _BASE_PRICES.get(symbol, _DEFAULT_PRICE)
        volatility = 0.015 if "BTC" in symbol else _DEFAULT_VOLATILITY

        rng = np.random.default_rng(self.seed + hash(symbol) % 1000)
        returns = rng.normal(0.0002, volatility, limit)  # légère tendance haussière
        prices = base_price * np.cumprod(1 + returns)

        dates = pd.date_range(end=pd.Timestamp.now(), periods=limit, freq="D")
        spread = volatility * 0.1

        df = pd.DataFrame(
            {
                "open": prices * (1 - spread / 2),
                "high": prices * (1 + spread),
                "low": prices * (1 - spread),
                "close": prices,
                "volume": rng.integers(5000, 50000, limit).astype(float),
            },
            index=dates,
        )
        return df

    def get_orderbook(self, symbol: str, depth: int = 10) -> Dict:
        """Order book simulé."""
        ticker = self.get_ticker(symbol)
        mid = ticker["last"]
        spread = mid * 0.0002

        bids = [[mid - spread * (i + 1), 0.5 + i * 0.1] for i in range(depth)]
        asks = [[mid + spread * (i + 1), 0.5 + i * 0.1] for i in range(depth)]
        return {"bids": bids, "asks": asks}

    def get_ticker(self, symbol: str) -> Dict:
        """Ticker simulé basé sur la dernière donnée OHLCV."""
        df = self.get_ohlcv(symbol, limit=2)
        last = df["close"].iloc[-1]
        spread = last * 0.0002
        return {
            "last": last,
            "bid": last - spread,
            "ask": last + spread,
            "quoteVolume": df["volume"].iloc[-1] * last,
            "change": (df["close"].iloc[-1] / df["close"].iloc[-2] - 1) * 100,
        }

    def get_trading_fees(self, symbol: str) -> Dict:
        """Frais simulés (équivalents Bitget standard)."""
        return {"maker": 0.001, "taker": 0.001}
