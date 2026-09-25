import unittest
from src.risk import RiskManager


class TestRiskManager(unittest.TestCase):
    """Pruebas unitarias para el gestor de riesgo y dimensionamiento de posición."""

    def setUp(self) -> None:
        self.risk = RiskManager(
            risk_per_trade_pct=0.02,  # 2%
            stop_loss_pct=0.015,       # 1.5%
            take_profit_pct=0.03,      # 3.0%
        )

    def test_calculate_position_size_normal(self) -> None:
        """Verifica el cálculo de tamaño de posición para valores normales."""
        usdt_balance = 10000.0
        current_price = 50000.0

        # Capital a arriesgar: 10000 * 0.02 = 200 USDT
        # Tamaño orden: 200 / 50000 = 0.004 BTC
        expected_size = 0.004
        actual_size = self.risk.calculate_position_size(usdt_balance, current_price)

        self.assertAlmostEqual(actual_size, expected_size, places=6)

    def test_calculate_position_size_zero_or_negative(self) -> None:
        """Verifica que saldos o precios cero/negativos devuelvan 0.0 de forma segura."""
        self.assertEqual(self.risk.calculate_position_size(0.0, 50000.0), 0.0)
        self.assertEqual(self.risk.calculate_position_size(-500.0, 50000.0), 0.0)
        self.assertEqual(self.risk.calculate_position_size(10000.0, 0.0), 0.0)
        self.assertEqual(self.risk.calculate_position_size(10000.0, -100.0), 0.0)

    def test_calculate_exit_levels(self) -> None:
        """Verifica el cálculo de niveles exactos de SL y TP."""
        entry_price = 100000.0
        levels = self.risk.calculate_exit_levels(entry_price)

        # SL: 100000 * (1 - 0.015) = 98500.0
        # TP: 100000 * (1 + 0.03)  = 103000.0
        self.assertEqual(levels["entry_price"], 100000.0)
        self.assertEqual(levels["stop_loss"], 98500.0)
        self.assertEqual(levels["take_profit"], 103000.0)


if __name__ == "__main__":
    unittest.main()
