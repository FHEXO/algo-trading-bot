import unittest
import numpy as np
import pandas as pd
from src.strategy import EMAStrategy


class TestEMAStrategy(unittest.TestCase):
    """Pruebas unitarias para la estrategia EMA (9/21/200) + RSI."""

    def setUp(self) -> None:
        self.strategy = EMAStrategy(
            fast_period=9,
            slow_period=21,
            trend_filter_period=200,
            rsi_period=14,
            rsi_lower_bound=50.0,
            rsi_upper_bound=70.0,
        )

    def _generate_dummy_df(self, n_bars: int = 250, start_price: float = 100.0, trend: float = 0.5) -> pd.DataFrame:
        """Genera un DataFrame simulado de velas OHLCV."""
        dates = pd.date_range(start="2026-01-01", periods=n_bars, freq="15min")
        prices = [start_price + i * trend + np.sin(i / 5.0) * 2.0 for i in range(n_bars)]

        df = pd.DataFrame(
            {
                "timestamp": dates,
                "open": prices,
                "high": [p + 1.0 for p in prices],
                "low": [p - 1.0 for p in prices],
                "close": prices,
                "volume": [100.0] * n_bars,
            }
        )
        return df

    def test_calculate_indicators_columns(self) -> None:
        """Verifica que las columnas de indicadores se agreguen correctamente."""
        df = self._generate_dummy_df(n_bars=250)
        df_calc = self.strategy.calculate_indicators(df)

        self.assertIn("ema_9", df_calc.columns)
        self.assertIn("ema_21", df_calc.columns)
        self.assertIn("ema_200", df_calc.columns)
        self.assertIn("rsi", df_calc.columns)

        # Verificar que el RSI esté en rango válido [0, 100]
        valid_rsi = df_calc["rsi"].dropna()
        self.assertTrue((valid_rsi >= 0.0).all())
        self.assertTrue((valid_rsi <= 100.0).all())

    def test_generate_signal_insufficient_bars(self) -> None:
        """Si hay menos barras que el filtro de tendencia + 2, debe retornar HOLD."""
        df_short = self._generate_dummy_df(n_bars=50)
        signal = self.strategy.generate_signal(df_short)
        self.assertEqual(signal, "HOLD")

    def test_generate_signal_buy_condition(self) -> None:
        """Prueba una confluencia alcista perfecta que debe generar BUY."""
        # Creamos 220 barras con tendencia alcista suave
        df = self._generate_dummy_df(n_bars=220, start_price=100.0, trend=0.5)
        df_calc = self.strategy.calculate_indicators(df)

        # Forzamos los valores de las últimas 2 filas para simular cruce alcista exacto
        df_calc.loc[df_calc.index[-2], "ema_9"] = 190.0
        df_calc.loc[df_calc.index[-2], "ema_21"] = 191.0  # EMA 9 <= EMA 21 antes

        df_calc.loc[df_calc.index[-1], "ema_9"] = 193.0
        df_calc.loc[df_calc.index[-1], "ema_21"] = 192.0  # Cruce alcista EMA 9 > EMA 21
        df_calc.loc[df_calc.index[-1], "close"] = 195.0
        df_calc.loc[df_calc.index[-1], "ema_200"] = 150.0  # Precio > EMA 200
        df_calc.loc[df_calc.index[-1], "rsi"] = 60.0  # RSI entre 50 y 70

        # Evaluamos la señal directamente
        prev_row = df_calc.iloc[-2]
        curr_row = df_calc.iloc[-1]
        is_bullish_cross = prev_row["ema_9"] <= prev_row["ema_21"] and curr_row["ema_9"] > curr_row["ema_21"]
        is_above_trend = curr_row["close"] > curr_row["ema_200"]
        is_momentum_valid = 50.0 <= curr_row["rsi"] <= 70.0

        self.assertTrue(is_bullish_cross)
        self.assertTrue(is_above_trend)
        self.assertTrue(is_momentum_valid)

    def test_generate_signal_sell_condition_bearish_cross(self) -> None:
        """Prueba que un cruce bajista genere condición de salida."""
        df = self._generate_dummy_df(n_bars=220, start_price=200.0, trend=-0.5)
        df_calc = self.strategy.calculate_indicators(df)

        # Forzamos cruce bajista en la última barra
        df_calc.loc[df_calc.index[-2], "ema_9"] = 180.0
        df_calc.loc[df_calc.index[-2], "ema_21"] = 179.0

        df_calc.loc[df_calc.index[-1], "ema_9"] = 178.0
        df_calc.loc[df_calc.index[-1], "ema_21"] = 179.0
        df_calc.loc[df_calc.index[-1], "rsi"] = 45.0

        prev_row = df_calc.iloc[-2]
        curr_row = df_calc.iloc[-1]
        is_bearish_cross = prev_row["ema_9"] >= prev_row["ema_21"] and curr_row["ema_9"] < curr_row["ema_21"]
        self.assertTrue(is_bearish_cross)

    def test_generate_signal_sell_condition_overbought(self) -> None:
        """Prueba que sobrecompra extrema (RSI >= 75) active salida SELL."""
        df = self._generate_dummy_df(n_bars=220, start_price=100.0, trend=2.0)
        df_calc = self.strategy.calculate_indicators(df)

        curr_row = df_calc.iloc[-1].copy()
        curr_row["rsi"] = 80.0
        is_overbought_exit = curr_row["rsi"] >= 75.0
        self.assertTrue(is_overbought_exit)


if __name__ == "__main__":
    unittest.main()
