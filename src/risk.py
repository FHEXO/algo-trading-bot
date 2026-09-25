from typing import Dict, Any


class RiskManager:
    """Gestiona el tamaño de las posiciones, Stop Loss y Take Profit."""

    def __init__(
        self,
        risk_per_trade_pct: float = 0.02,  # 2% del balance total por trade
        stop_loss_pct: float = 0.015,  # 1.5% de pérdida máxima
        take_profit_pct: float = 0.03,  # 3.0% de ganancia objetivo (Ratio 1:2)
    ) -> None:
        self.risk_per_trade_pct = risk_per_trade_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct

    def calculate_position_size(
        self, usdt_balance: float, current_price: float
    ) -> float:
        """Calcula la cantidad de criptoactivo a comprar según el balance disponible."""
        if usdt_balance <= 0 or current_price <= 0:
            return 0.0

        # Monto en dólares a asignar en esta operación
        capital_to_risk = usdt_balance * self.risk_per_trade_pct

        # Cantidad en unidades de cripto (ej. BTC)
        position_size = capital_to_risk / current_price

        # Redondear a 6 decimales para compatibilidad con el exchange
        return round(position_size, 6)

    def calculate_exit_levels(self, entry_price: float) -> Dict[str, float]:
        """Calcula los niveles exactos de Stop Loss y Take Profit."""
        stop_loss = round(entry_price * (1.0 - self.stop_loss_pct), 2)
        take_profit = round(entry_price * (1.0 + self.take_profit_pct), 2)

        return {
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }


if __name__ == "__main__":
    # Test rápido de dimensionamiento de posición
    risk = RiskManager(
        risk_per_trade_pct=0.02, stop_loss_pct=0.015, take_profit_pct=0.03
    )

    balance_prueba = 10000.0  # 10,000 USDT disponibles en Testnet
    precio_actual_btc = 69355.87

    tamano_orden = risk.calculate_position_size(
        balance_prueba, precio_actual_btc
    )
    niveles = risk.calculate_exit_levels(precio_actual_btc)

    print("\n--- TEST DE GESTIÓN DE RIESGO ---")
    print(f"Balance USDT: ${balance_prueba:,.2f}")
    print(f"Capital asignado por operación (2%): ${balance_prueba * 0.02:.2f}")
    print(f"Tamaño de orden calculado: {tamano_orden} BTC")
    print(f"Precio Entrada: ${niveles['entry_price']:,.2f}")
    print(f"Nivel Stop Loss (-1.5%): ${niveles['stop_loss']:,.2f}")
    print(f"Nivel Take Profit (+3.0%): ${niveles['take_profit']:,.2f}")