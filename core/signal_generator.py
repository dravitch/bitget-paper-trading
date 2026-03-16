"""
Signal Generator - Moteur de génération de signaux multi-stratégies.
Port nettoyé du code existant avec architecture extensible.
"""
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from loguru import logger


class SignalAction(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE = "CLOSE"


class SignalStrength(Enum):
    WEAK = "WEAK"
    MEDIUM = "MEDIUM"
    STRONG = "STRONG"


@dataclass
class TradingSignal:
    symbol: str
    action: SignalAction
    strength: SignalStrength
    confidence: float        # 0.0 à 1.0
    price: float
    timestamp: datetime
    indicators: Dict[str, float]
    message: str = ""
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class BaseStrategy:
    """Classe de base pour toutes les stratégies."""

    def __init__(self, name: str):
        self.name = name
        self._required = ["open", "high", "low", "close", "volume"]

    def validate(self, df: pd.DataFrame) -> bool:
        if df is None or df.empty:
            return False
        missing = [c for c in self._required if c not in df.columns]
        if missing:
            logger.warning(f"{self.name}: colonnes manquantes {missing}")
            return False
        return True

    def generate_signal(self, df: pd.DataFrame) -> TradingSignal:
        raise NotImplementedError

    def _hold_signal(self, price: float = 0.0, message: str = "Données insuffisantes") -> TradingSignal:
        return TradingSignal(
            symbol="",
            action=SignalAction.HOLD,
            strength=SignalStrength.WEAK,
            confidence=0.0,
            price=price,
            timestamp=datetime.now(),
            indicators={},
            message=message,
        )


class RSIStrategy(BaseStrategy):
    """Stratégie RSI avec seuils configurables."""

    def __init__(
        self,
        rsi_period: int = 14,
        oversold: int = 30,
        overbought: int = 70,
        volume_threshold: float = 0.4,
    ):
        super().__init__("RSIStrategy")
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.volume_threshold = volume_threshold

    def _calc_rsi(self, closes: pd.Series) -> pd.Series:
        delta = closes.diff()
        gain = delta.where(delta > 0, 0).rolling(self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.rsi_period).mean()
        rs = gain / loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))

    def generate_signal(self, df: pd.DataFrame) -> TradingSignal:
        if not self.validate(df) or len(df) < self.rsi_period + 5:
            return self._hold_signal()

        try:
            rsi = self._calc_rsi(df["close"])
            current_rsi = rsi.iloc[-1]
            prev_rsi = rsi.iloc[-2]

            vol_ma = df["volume"].rolling(20).mean()
            vol_ratio = df["volume"].iloc[-1] / vol_ma.iloc[-1] if vol_ma.iloc[-1] > 0 else 0
            price = df["close"].iloc[-1]

            indicators = {
                "rsi": current_rsi,
                "rsi_prev": prev_rsi,
                "volume_ratio": vol_ratio,
            }

            # BUY: RSI survendu
            if current_rsi < self.oversold and vol_ratio > self.volume_threshold:
                strong = current_rsi < 25 and vol_ratio > 1.0
                return TradingSignal(
                    symbol="",
                    action=SignalAction.BUY,
                    strength=SignalStrength.STRONG if strong else SignalStrength.MEDIUM,
                    confidence=0.8 if strong else 0.6,
                    price=price,
                    timestamp=datetime.now(),
                    indicators=indicators,
                    message=f"RSI survendu ({current_rsi:.1f})",
                )

            # SELL: RSI suracheté
            if current_rsi > self.overbought and vol_ratio > self.volume_threshold:
                strong = current_rsi > 75 and vol_ratio > 1.0
                return TradingSignal(
                    symbol="",
                    action=SignalAction.SELL,
                    strength=SignalStrength.STRONG if strong else SignalStrength.MEDIUM,
                    confidence=0.8 if strong else 0.6,
                    price=price,
                    timestamp=datetime.now(),
                    indicators=indicators,
                    message=f"RSI suracheté ({current_rsi:.1f})",
                )

            # CLOSE: RSI traverse niveau 50
            crosses_50 = (current_rsi > 50 and prev_rsi <= 50) or (current_rsi < 50 and prev_rsi >= 50)
            if crosses_50:
                return TradingSignal(
                    symbol="",
                    action=SignalAction.CLOSE,
                    strength=SignalStrength.MEDIUM,
                    confidence=0.7,
                    price=price,
                    timestamp=datetime.now(),
                    indicators=indicators,
                    message=f"RSI traverse 50 ({prev_rsi:.1f} → {current_rsi:.1f})",
                )

            return self._hold_signal(price, f"RSI neutre ({current_rsi:.1f})")

        except Exception as e:
            logger.error(f"RSIStrategy: {e}")
            return self._hold_signal()


class MovingAverageStrategy(BaseStrategy):
    """Stratégie croisement de moyennes mobiles."""

    def __init__(self, fast_period: int = 20, slow_period: int = 50):
        super().__init__("MovingAverageStrategy")
        self.fast = fast_period
        self.slow = slow_period

    def generate_signal(self, df: pd.DataFrame) -> TradingSignal:
        if not self.validate(df) or len(df) < self.slow + 5:
            return self._hold_signal()

        try:
            ma_fast = df["close"].rolling(self.fast).mean()
            ma_slow = df["close"].rolling(self.slow).mean()
            ratio = ma_fast.iloc[-1] / ma_slow.iloc[-1] if ma_slow.iloc[-1] > 0 else 1
            price = df["close"].iloc[-1]

            indicators = {
                "ma_fast": ma_fast.iloc[-1],
                "ma_slow": ma_slow.iloc[-1],
                "ratio": ratio,
            }

            if ratio > 1.02:
                return TradingSignal(
                    symbol="",
                    action=SignalAction.BUY,
                    strength=SignalStrength.MEDIUM,
                    confidence=0.7,
                    price=price,
                    timestamp=datetime.now(),
                    indicators=indicators,
                    message=f"MA{self.fast} > MA{self.slow} (+{(ratio-1)*100:.1f}%)",
                )
            if ratio < 0.98:
                return TradingSignal(
                    symbol="",
                    action=SignalAction.SELL,
                    strength=SignalStrength.MEDIUM,
                    confidence=0.7,
                    price=price,
                    timestamp=datetime.now(),
                    indicators=indicators,
                    message=f"MA{self.fast} < MA{self.slow} ({(ratio-1)*100:.1f}%)",
                )

            return self._hold_signal(price, f"MA{self.fast}/MA{self.slow} alignées")

        except Exception as e:
            logger.error(f"MovingAverageStrategy: {e}")
            return self._hold_signal()


class SignalGenerator:
    """
    Orchestrateur de signaux multi-stratégies.
    Enregistre et exécute les stratégies, fusionne les résultats.
    """

    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
        self.history: List[TradingSignal] = []
        self._register_defaults()

    def _register_defaults(self):
        self.register("rsi", RSIStrategy())
        self.register("moving_average", MovingAverageStrategy())

    def register(self, name: str, strategy: BaseStrategy):
        """Enregistre une stratégie (built-in ou custom)."""
        self.strategies[name] = strategy
        logger.info(f"Stratégie enregistrée: {name} - {strategy.name}")

    def generate_signal(self, symbol: str, df: pd.DataFrame, strategy: str = "rsi") -> TradingSignal:
        """Génère un signal pour un symbole avec la stratégie donnée."""
        if strategy not in self.strategies:
            raise ValueError(f"Stratégie inconnue: {strategy}. Disponibles: {list(self.strategies)}")

        signal = self.strategies[strategy].generate_signal(df)
        signal.symbol = symbol
        self.history.append(signal)
        logger.debug(f"Signal [{symbol}] {signal.action.value} ({signal.strength.value}) - {signal.message}")
        return signal

    def analyze_all(self, symbol: str, df: pd.DataFrame) -> Dict[str, TradingSignal]:
        """Analyse avec toutes les stratégies enregistrées."""
        results = {}
        for name in self.strategies:
            try:
                results[name] = self.generate_signal(symbol, df, name)
            except Exception as e:
                logger.error(f"Erreur stratégie {name} sur {symbol}: {e}")
        return results

    def consensus(self, signals: Dict[str, TradingSignal]) -> Dict:
        """
        Calcule le consensus de plusieurs signaux.
        Utile pour combiner RSI + MA ou multi-exchange.
        """
        if not signals:
            return {"action": SignalAction.HOLD, "confidence": 0.0}

        votes: Dict[SignalAction, float] = {}
        for sig in signals.values():
            votes[sig.action] = votes.get(sig.action, 0) + sig.confidence

        best_action = max(votes, key=votes.__getitem__)
        avg_confidence = sum(s.confidence for s in signals.values()) / len(signals)

        return {
            "action": best_action,
            "confidence": avg_confidence,
            "votes": {k.value: v for k, v in votes.items()},
        }
