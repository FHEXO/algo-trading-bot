from typing import Literal
import pandas as pd
from src.exchange import ExchangeClient

SignalType = Literal["BUY", "SELL", "HOLD"]


class EMAStrategy:
    """
    Estrategia Cuantitativa Profesional:
    1. Filtro Macro: Precio > EMA 200 (Solo compras en tendencia alcista).
    2. Señal de Entrada: Cruce Alcista EMA 9 > EMA 21.
    3. Filtro de Momentum: 50 <= RSI <= 70 (Fuerza compradora sin sobrecompra).
    4. Señal de Salida: Cruce Bajista EMA 9 < EMA 21 o RSI > 75 (Toma de ganancias por sobreextensión).
    """

    def __init__(
        self,
        fast_period: int = 9,
        slow_period: int = 21,
        trend_filter_period: int = 200,
        rsi_period: int = 14,
        rsi_lower_bound: float = 50.0,
        rsi_upper_bound: float = 70.0,
    ) -> None:
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.trend_filter_period = trend_filter_period
        self.rsi_period = rsi_period
        self.rsi_lower_bound = rsi_lower_bound
        self.rsi_upper_bound = rsi_upper_bound

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula EMAs y RSI de forma vectorizada."""
        df = df.copy()

        # 1. Medias Móviles Exponenciales
        df[f"ema_{self.fast_period}"] = (
            df["close"].ewm(span=self.fast_period, adjust=False).mean()
        )
        df[f"ema_{self.slow_period}"] = (
            df["close"].ewm(span=self.slow_period, adjust=False).mean()
        )
        df[f"ema_{self.trend_filter_period}"] = (
            df["close"].ewm(span=self.trend_filter_period, adjust=False).mean()
        )

        # 2. Relative Strength Index (RSI - Wilder's Smoothing)
        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        # Media móvil exponencial con alpha = 1 / periodo
        avg_gain = gain.ewm(alpha=1 / self.rsi_period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / self.rsi_period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, 1e-9)
        df["rsi"] = 100 - (100 / (1 + rs))

        return df

    def generate_signal(self, df: pd.DataFrame) -> SignalType:
        """Evalúa las condiciones con el triple filtro."""
        min_required_bars = self.trend_filter_period + 2
        if len(df) < min_required_bars:
            return "HOLD"

        df_calc = self.calculate_indicators(df)

        prev_row = df_calc.iloc[-2]
        curr_row = df_calc.iloc[-1]

        fast_col = f"ema_{self.fast_period}"
        slow_col = f"ema_{self.slow_period}"
        trend_col = f"ema_{self.trend_filter_period}"

        prev_fast = prev_row[fast_col]
        prev_slow = prev_row[slow_col]
        curr_fast = curr_row[fast_col]
        curr_slow = curr_row[slow_col]
        curr_close = curr_row["close"]
        curr_trend = curr_row[trend_col]
        curr_rsi = curr_row["rsi"]

        # Condición BUY (Triple Confluencia):
        # Cruce alcista + Precio sobre EMA 200 + RSI en zona de impulso (50 - 70)
        is_bullish_cross = prev_fast <= prev_slow and curr_fast > curr_slow
        is_above_trend = curr_close > curr_trend
        is_momentum_valid = self.rsi_lower_bound <= curr_rsi <= self.rsi_upper_bound

        if is_bullish_cross and is_above_trend and is_momentum_valid:
            return "BUY"

        # Condición SELL:
        # Cruce bajista o Sobrecompra extrema (RSI > 75)
        is_bearish_cross = prev_fast >= prev_slow and curr_fast < curr_slow
        is_overbought_exit = curr_rsi >= 75.0

        if is_bearish_cross or is_overbought_exit:
            return "SELL"

        return "HOLD"


if __name__ == "__main__":
    client = ExchangeClient()
    candles_df = client.fetch_ohlcv(limit=250)

    strategy = EMAStrategy()
    df_calc = strategy.calculate_indicators(candles_df)
    current_signal = strategy.generate_signal(candles_df)

    print("\n--- ÚLTIMAS 5 FILAS CON TRIPLE FILTRO (EMA 9, 21, 200 + RSI) ---")
    print(df_calc[["timestamp", "close", "ema_9", "ema_21", "ema_200", "rsi"]].tail(5))
    print(f"\n[SEÑAL ACTUAL DEL MERCADO]: >>> {current_signal} <<<")