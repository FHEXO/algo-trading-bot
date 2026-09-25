from typing import Dict, Any, List, Optional
import ccxt
import pandas as pd
from src.config import Config


class ExchangeClient:
    """Maneja la comunicación, datos de mercado y órdenes nativas con Binance Demo Trading."""

    def __init__(self) -> None:
        exchange_class = getattr(ccxt, Config.EXCHANGE_ID, None)

        if not exchange_class:
            raise ValueError(
                f"Exchange '{Config.EXCHANGE_ID}' no está soportado por CCXT."
            )

        self.client: ccxt.Exchange = exchange_class(
            {
                "apiKey": Config.API_KEY,
                "secret": Config.API_SECRET,
                "enableRateLimit": True,
            }
        )

        # Enlazar con Binance Demo Trading Web
        if Config.TESTNET:
            if hasattr(self.client, "enable_demo_trading"):
                self.client.enable_demo_trading(True)
            elif hasattr(self.client, "set_sandbox_mode"):
                self.client.set_sandbox_mode(True)

    def fetch_ohlcv(self, symbol: Optional[str] = None, limit: int = 100) -> pd.DataFrame:
        """Descarga las últimas velas del mercado para un símbolo determinado."""
        # Si no se pasa símbolo, tomar el primero de la lista de configuración
        target_symbol = symbol or (Config.SYMBOLS[0] if Config.SYMBOLS else "BTC/USDT")
        
        raw_candles = self.client.fetch_ohlcv(
            symbol=target_symbol,
            timeframe=Config.TIMEFRAME,
            limit=limit,
        )
        columns = ["timestamp", "open", "high", "low", "close", "volume"]
        df = pd.DataFrame(raw_candles, columns=columns)
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        return df

    def fetch_balance(self) -> Dict[str, float]:
        """Consulta los fondos disponibles en Binance Demo Trading."""
        try:
            balance = self.client.fetch_balance()
            non_zero_balances = {
                coin: amount
                for coin, amount in balance.get("total", {}).items()
                if amount > 0
            }
            return non_zero_balances
        except ccxt.AuthenticationError as e:
            print(f"[ERROR DE AUTENTICACIÓN] {e}")
            raise
        except Exception as e:
            print(f"[ERROR EXCHANGE] {e}")
            raise

    # -------------------------------------------------------------
    # MÉTODOS DE ÓRDENES (MERCADO, OCO, STOP LOSS Y CANCELACIÓN)
    # -------------------------------------------------------------
    def create_market_buy_order(
        self, symbol: str, amount: float
    ) -> Dict[str, Any]:
        """Envía una orden de compra a mercado."""
        return self.client.create_market_buy_order(symbol, amount)

    def create_market_sell_order(
        self, symbol: str, amount: float
    ) -> Dict[str, Any]:
        """Envía una orden de venta a mercado."""
        return self.client.create_market_sell_order(symbol, amount)

    def create_oco_sell_order(
        self,
        symbol: str,
        amount: float,
        take_profit_price: float,
        stop_loss_price: float,
        stop_limit_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Crea una orden OCO (One-Cancels-the-Other) de venta:
        - Límite de Ganancia: take_profit_price
        - Gatillo de Pérdida (Stop): stop_loss_price
        - Límite de Ejecución de Pérdida: stop_limit_price (por defecto 0.2% por debajo de stop_price)
        """
        if stop_limit_price is None:
            stop_limit_price = round(stop_loss_price * 0.998, 2)

        # Usar endpoint nativo OCO de Binance vía CCXT
        binance_symbol = symbol.replace("/", "")
        params = {
            "symbol": binance_symbol,
            "side": "SELL",
            "quantity": self.client.amount_to_precision(symbol, amount),
            "price": self.client.price_to_precision(symbol, take_profit_price),
            "stopPrice": self.client.price_to_precision(symbol, stop_loss_price),
            "stopLimitPrice": self.client.price_to_precision(
                symbol, stop_limit_price
            ),
            "stopLimitTimeInForce": "GTC",
        }

        if hasattr(self.client, "privatePostOrderOco"):
            return self.client.privatePostOrderOco(params)
        elif hasattr(self.client, "private_post_order_oco"):
            return self.client.private_post_order_oco(params)
        else:
            raise NotImplementedError(
                "El método OCO no está soportado en este cliente CCXT."
            )

    def create_stop_loss_order(
        self,
        symbol: str,
        amount: float,
        stop_loss_price: float,
        stop_limit_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Crea una orden Stop Loss Limit nativa como alternativa a OCO."""
        if stop_limit_price is None:
            stop_limit_price = round(stop_loss_price * 0.998, 2)

        params = {
            "stopPrice": self.client.price_to_precision(symbol, stop_loss_price)
        }
        return self.client.create_order(
            symbol=symbol,
            type="STOP_LOSS_LIMIT",
            side="sell",
            amount=amount,
            price=stop_limit_price,
            params=params,
        )

    def cancel_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Cancela una orden abierta en el exchange."""
        return self.client.cancel_order(order_id, symbol)

    def cancel_all_symbol_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Cancela todas las órdenes abiertas de un símbolo específico."""
        try:
            if hasattr(self.client, "cancel_all_orders"):
                return self.client.cancel_all_orders(symbol)
        except Exception:
            pass

        # Fallback: consultar órdenes abiertas y cancelar una a una
        open_orders = self.fetch_open_orders(symbol)
        cancelled = []
        for order in open_orders:
            try:
                res = self.client.cancel_order(order["id"], symbol)
                cancelled.append(res)
            except Exception as e:
                print(f"[WARN] Error cancelando orden {order.get('id')}: {e}")
        return cancelled

    def fetch_open_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Consulta todas las órdenes activas/pendientes en el exchange."""
        return self.client.fetch_open_orders(symbol)

    def fetch_order(self, order_id: str, symbol: str) -> Dict[str, Any]:
        """Consulta el estado detallado de una orden por su ID."""
        return self.client.fetch_order(order_id, symbol)


if __name__ == "__main__":
    exchange = ExchangeClient()
    print("\n--- CONSULTANDO BALANCE DE BINANCE DEMO TRADING ---")
    saldo = exchange.fetch_balance()
    print("Saldos disponibles:")
    for moneda, cantidad in saldo.items():
        print(f"  * {moneda}: {cantidad}")

    print("\n--- CONSULTANDO ÓRDENES ABIERTAS ---")
    first_symbol = Config.SYMBOLS[0] if Config.SYMBOLS else "BTC/USDT"
    try:
        ordenes = exchange.fetch_open_orders(first_symbol)
        print(f"Órdenes abiertas ({first_symbol}): {len(ordenes)}")
        for o in ordenes:
            print(f"  * ID: {o.get('id')} | Tipo: {o.get('type')} | Lado: {o.get('side')} | Precio: {o.get('price')}")
    except Exception as e:
        print(f"Aviso al consultar órdenes abiertas: {e}")