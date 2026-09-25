import json
import os
import time
from datetime import datetime
from typing import Any, Dict
import pandas as pd

from src.config import Config
from src.exchange import ExchangeClient
from src.logger import setup_logger
from src.strategy import EMAStrategy


class DayTradingBot:
    """Instancia individual para Day Trading con Gestión Dinámica de Riesgo (1%)."""

    def __init__(
        self,
        symbol: str,
        stop_loss_pct: float = 0.01,
        take_profit_pct: float = 0.02,
        risk_per_trade_pct: float = 0.01,
    ) -> None:
        self.symbol = symbol
        self.logger = setup_logger(name=f"Bot-{self.symbol.replace('/', '')}")
        self.exchange = ExchangeClient()
        self.strategy = EMAStrategy()

        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.risk_per_trade_pct = risk_per_trade_pct

        safe_name = self.symbol.replace("/", "_")
        self.state_file = f"data/state_{safe_name}.json"
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

        self.in_position = False
        self.entry_price = 0.0
        self.amount = 0.0
        self.stop_loss_price = 0.0
        self.take_profit_price = 0.0
        self.last_processed_timestamp = None

        self._load_state()

    def _save_state(self) -> None:
        state_data: Dict[str, Any] = {
            "in_position": self.in_position,
            "entry_price": self.entry_price,
            "amount": self.amount,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
            "symbol": self.symbol,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state_data, f, indent=4)
        except Exception as e:
            self.logger.error(f"Error al guardar estado de {self.symbol}: {e}")

    def _load_state(self) -> None:
        if not os.path.exists(self.state_file):
            self._save_state()
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                state_data = json.load(f)

            self.in_position = state_data.get("in_position", False)
            self.entry_price = float(state_data.get("entry_price", 0.0))
            self.amount = float(state_data.get("amount", 0.0))
            self.stop_loss_price = float(state_data.get("stop_loss_price", 0.0))
            self.take_profit_price = float(state_data.get("take_profit_price", 0.0))
        except Exception as e:
            self.logger.error(f"Error cargando estado {self.symbol}: {e}")
            self._reset_position()

    def _reset_position(self) -> None:
        self.in_position = False
        self.entry_price = 0.0
        self.amount = 0.0
        self.stop_loss_price = 0.0
        self.take_profit_price = 0.0
        self._save_state()

    def _calculate_position_size(
        self, current_price: float, usdt_balance: float
    ) -> float:
        capital_asignado = usdt_balance * 0.33
        riesgo_usd = capital_asignado * self.risk_per_trade_pct
        distancia_sl_usd = current_price * self.stop_loss_pct

        cantidad = riesgo_usd / distancia_sl_usd
        costo_total = cantidad * current_price

        if costo_total > capital_asignado:
            cantidad = (capital_asignado * 0.98) / current_price

        return cantidad

    def run_iteration(self) -> None:
        try:
            df_raw = self.exchange.client.fetch_ohlcv(
                self.symbol, timeframe=Config.TIMEFRAME, limit=250
            )
            df = pd.DataFrame(
                df_raw,
                columns=["timestamp", "open", "high", "low", "close", "volume"],
            )

            df_closed = df.iloc[:-1].copy()
            current_price = float(df["close"].iloc[-1])
            last_closed_timestamp = df_closed["timestamp"].iloc[-1]
        except Exception as e:
            self.logger.error(f"Error descargando datos en {self.symbol}: {e}")
            return

        # 1. Monitoreo de Salidas (SL / TP)
        if self.in_position:
            pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            self.logger.info(
                f"[{self.symbol}] Activa | PnL: {pnl_pct:+.2f}% | Precio: ${current_price:,.2f}"
            )

            if current_price <= self.stop_loss_price:
                self.logger.warning(
                    f"🛑 STOP LOSS ALCANZADO en {self.symbol} a ${current_price:,.2f}"
                )
                self._execute_sell()
                self.last_processed_timestamp = last_closed_timestamp
                return

            elif current_price >= self.take_profit_price:
                self.logger.info(
                    f"🎯 TAKE PROFIT ALCANZADO en {self.symbol} a ${current_price:,.2f}"
                )
                self._execute_sell()
                self.last_processed_timestamp = last_closed_timestamp
                return

        # 2. Análisis de Entradas (Bloqueo de Vela - 1 vez por vela de 15m)
        if not self.in_position:
            if self.last_processed_timestamp == last_closed_timestamp:
                return

            signal = self.strategy.generate_signal(df_closed)
            self.logger.info(
                f"--- VELA CERRADA [{self.symbol}] ({last_closed_timestamp}) | Señal: >>> {signal} <<< ---"
            )

            if signal == "BUY":
                try:
                    balances = self.exchange.fetch_balance()
                    usdt_balance = balances.get("USDT", 0.0)

                    trade_amount = self._calculate_position_size(
                        current_price, usdt_balance
                    )
                    self.logger.info(
                        f"🚨 SEÑAL CONFIRMADA en {self.symbol}. Comprando {trade_amount:.6f}..."
                    )

                    order = self.exchange.client.create_market_buy_order(
                        self.symbol, trade_amount
                    )

                    self.entry_price = current_price
                    self.amount = trade_amount
                    self.stop_loss_price = current_price * (1.0 - self.stop_loss_pct)
                    self.take_profit_price = current_price * (1.0 + self.take_profit_pct)
                    self.in_position = True
                    self.last_processed_timestamp = last_closed_timestamp
                    self._save_state()

                    self.logger.info(
                        f"✅ Compra Exitosa en {self.symbol}. ID: {order.get('id')}"
                    )
                except Exception as e:
                    self.logger.error(f"Fallo en compra {self.symbol}: {e}")
            else:
                self.last_processed_timestamp = last_closed_timestamp

    def _execute_sell(self) -> None:
        try:
            order = self.exchange.client.create_market_sell_order(
                self.symbol, self.amount
            )
            self.logger.info(f"✅ Venta ejecutada {self.symbol}. ID: {order.get('id')}")
            self._reset_position()
        except Exception as e:
            self.logger.error(f"Error al ejecutar venta en {self.symbol}: {e}")
            try:
                base_asset = self.symbol.split("/")[0]
                balances = self.exchange.fetch_balance()
                total_balance = balances.get(base_asset, 0.0)
                if total_balance > 0:
                    self.exchange.client.create_market_sell_order(
                        self.symbol, total_balance
                    )
                self._reset_position()
            except Exception as inner_e:
                self.logger.critical(
                    f"Fallo crítico al liquidar {self.symbol}: {inner_e}"
                )


def main() -> None:
    portfolio = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
    escuadron = [DayTradingBot(symbol=moneda) for moneda in portfolio]

    print("\n🚀 Escuadrón Cuantitativo (Day Trading 15m) Iniciado.")

    while True:
        try:
            for bot in escuadron:
                bot.run_iteration()
                time.sleep(1)

            time.sleep(15)
        except KeyboardInterrupt:
            print("\n🛑 Escuadrón detenido manualmente.")
            break
        except Exception as e:
            print(f"Error crítico en loop principal: {e}")
            time.sleep(15)


if __name__ == "__main__":
    main()