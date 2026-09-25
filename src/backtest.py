from typing import List, Dict, Any
import numpy as np
import pandas as pd
from src.exchange import ExchangeClient
from src.strategy import EMAStrategy


class Backtester:
    """Motor de simulación histórica con gestión híbrida (Hard SL / TP + Salidas Técnicas por EMA/RSI)."""

    def __init__(
        self,
        strategy: EMAStrategy,
        initial_capital: float = 1000.0,
        fee_pct: float = 0.001,  # 0.1% comisión de Binance por operación
        stop_loss_pct: float = 0.015,  # 1.5% Stop Loss
        take_profit_pct: float = 0.03,  # 3.0% Take Profit
    ) -> None:
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.fee_pct = fee_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    def run(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Ejecuta la simulación evaluando SL/TP y señales técnicas de salida."""
        df_calc = self.strategy.calculate_indicators(df)

        capital = self.initial_capital
        position = 0.0
        entry_price = 0.0
        stop_loss_price = 0.0
        take_profit_price = 0.0
        trades: List[Dict[str, Any]] = []
        equity_curve: List[float] = [capital]

        fast_col = f"ema_{self.strategy.fast_period}"
        slow_col = f"ema_{self.strategy.slow_period}"
        trend_col = f"ema_{self.strategy.trend_filter_period}"

        start_idx = self.strategy.trend_filter_period + 2

        for i in range(start_idx, len(df_calc)):
            prev_row = df_calc.iloc[i - 1]
            curr_row = df_calc.iloc[i]

            prev_fast = prev_row[fast_col]
            prev_slow = prev_row[slow_col]
            curr_fast = curr_row[fast_col]
            curr_slow = curr_row[slow_col]
            current_close = float(curr_row["close"])
            current_high = float(curr_row["high"])
            current_low = float(curr_row["low"])
            curr_trend = curr_row[trend_col]
            curr_rsi = curr_row["rsi"]
            timestamp = curr_row["timestamp"]

            # -------------------------------------------------------------
            # LÓGICA DE SALIDA (SL / TP / SEÑAL TÉCNICA SELL)
            # -------------------------------------------------------------
            if position > 0.0:
                exit_price = 0.0
                exit_reason = ""

                # 1. Chequeo de Stop Loss (Si la mecha baja tocó el piso)
                if current_low <= stop_loss_price:
                    exit_price = stop_loss_price
                    exit_reason = "STOP_LOSS"

                # 2. Chequeo de Take Profit (Si la mecha alta tocó el techo)
                elif current_high >= take_profit_price:
                    exit_price = take_profit_price
                    exit_reason = "TAKE_PROFIT"

                # 3. Chequeo de Salida Técnica (Cruce bajista o Sobrecompra RSI >= 75)
                else:
                    is_bearish_cross = prev_fast >= prev_slow and curr_fast < curr_slow
                    is_overbought_exit = curr_rsi >= 75.0
                    if is_bearish_cross or is_overbought_exit:
                        exit_price = current_close
                        exit_reason = "SIGNAL_SELL"

                # Si se ejecutó alguna salida, se liquida el trade
                if exit_price > 0.0:
                    gross_revenue = position * exit_price
                    capital = gross_revenue * (1.0 - self.fee_pct)
                    pnl = capital - (position * entry_price)
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100

                    trades.append(
                        {
                            "timestamp": timestamp,
                            "entry_price": entry_price,
                            "exit_price": exit_price,
                            "reason": exit_reason,
                            "pnl": pnl,
                            "pnl_pct": pnl_pct,
                            "won": pnl > 0,
                        }
                    )
                    # Resetear posición
                    position = 0.0
                    entry_price = 0.0
                    stop_loss_price = 0.0
                    take_profit_price = 0.0

            # -------------------------------------------------------------
            # LÓGICA DE ENTRADA (Solo si estamos 100% líquidos)
            # -------------------------------------------------------------
            if position == 0.0:
                is_bullish_cross = prev_fast <= prev_slow and curr_fast > curr_slow
                is_above_trend = current_close > curr_trend
                is_momentum_valid = (
                    self.strategy.rsi_lower_bound
                    <= curr_rsi
                    <= self.strategy.rsi_upper_bound
                )

                if is_bullish_cross and is_above_trend and is_momentum_valid:
                    cost = capital * (1.0 - self.fee_pct)
                    position = cost / current_close
                    entry_price = current_close
                    capital = 0.0

                    # Establecer barreras matemáticas
                    stop_loss_price = entry_price * (1.0 - self.stop_loss_pct)
                    take_profit_price = entry_price * (1.0 + self.take_profit_pct)

            current_equity = (
                capital if position == 0.0 else position * current_close
            )
            equity_curve.append(current_equity)

        # Si al final de la historia hay posición abierta, se valora a precio final
        if position > 0.0:
            last_price = float(df_calc.iloc[-1]["close"])
            capital = (position * last_price) * (1.0 - self.fee_pct)

        return self._calculate_metrics(trades, equity_curve, capital)

    def _calculate_metrics(
        self,
        trades: List[Dict[str, Any]],
        equity_curve: List[float],
        final_capital: float,
    ) -> Dict[str, Any]:
        total_trades = len(trades)
        if total_trades == 0:
            return {
                "error": "No se completaron operaciones en el periodo con estos parámetros."
            }

        winning_trades = [t for t in trades if t["won"]]
        losing_trades = [t for t in trades if not t["won"]]

        win_rate = (len(winning_trades) / total_trades) * 100
        gross_profit = sum(t["pnl"] for t in winning_trades)
        gross_loss = abs(sum(t["pnl"] for t in losing_trades))

        profit_factor = (
            (gross_profit / gross_loss) if gross_loss > 0 else float("inf")
        )
        total_return_pct = (
            (final_capital - self.initial_capital) / self.initial_capital
        ) * 100

        equity_array = np.array(equity_curve)
        peak = np.maximum.accumulate(equity_array)
        drawdowns = (equity_array - peak) / peak
        max_drawdown_pct = abs(float(np.min(drawdowns))) * 100

        tp_hits = sum(1 for t in trades if t["reason"] == "TAKE_PROFIT")
        sl_hits = sum(1 for t in trades if t["reason"] == "STOP_LOSS")
        signal_hits = sum(1 for t in trades if t["reason"] == "SIGNAL_SELL")

        return {
            "initial_capital": self.initial_capital,
            "final_capital": round(final_capital, 2),
            "total_return_pct": round(total_return_pct, 2),
            "total_trades": total_trades,
            "win_rate_pct": round(win_rate, 2),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "tp_hits": tp_hits,
            "sl_hits": sl_hits,
            "signal_hits": signal_hits,
        }


if __name__ == "__main__":
    print("\n--- EJECUTANDO BACKTEST: MODO HÍBRIDO (SL / TP / SEÑAL TÉCNICA) ---")
    exchange = ExchangeClient()
    historical_df = exchange.fetch_ohlcv(limit=1000)

    strategy = EMAStrategy()
    backtester = Backtester(
        strategy=strategy,
        initial_capital=1000.0,
        stop_loss_pct=0.015,
        take_profit_pct=0.03,
    )

    results = backtester.run(historical_df)

    print("\n" + "=" * 50)
    print("RESULTADOS DE BACKTEST (CON SALIDAS TECNICAS)")
    print("=" * 50)
    if "error" in results:
        print(f"Aviso: {results['error']}")
    else:
        print(f"Capital Inicial:     ${results['initial_capital']:,.2f}")
        print(f"Capital Final:       ${results['final_capital']:,.2f}")
        print(f"Retorno Neto:        {results['total_return_pct']}%")
        print(f"Total de Trades:     {results['total_trades']}")
        print(f"Win Rate:            {results['win_rate_pct']}%")
        print(f"Profit Factor:       {results['profit_factor']}")
        print(f"Máximo Drawdown:     {results['max_drawdown_pct']}%")
        print("-" * 50)
        print("ESTADÍSTICAS DE SALIDAS:")
        print(f"  * Salidas por Take Profit (+{backtester.take_profit_pct*100:.1f}%): {results['tp_hits']}")
        print(f"  * Salidas por Stop Loss   (-{backtester.stop_loss_pct*100:.1f}%): {results['sl_hits']}")
        print(f"  * Salidas por Señal Técnica (EMA/RSI):     {results['signal_hits']}")
    print("=" * 50)