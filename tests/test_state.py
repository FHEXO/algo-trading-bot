import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from src.main import TradingBot
from src.risk import RiskManager


class TestStatePersistence(unittest.TestCase):
    """Pruebas unitarias para el guardado y recuperación de estado JSON."""

    def setUp(self) -> None:
        # Crear archivo temporal para pruebas de estado
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        self.temp_file.close()

    def tearDown(self) -> None:
        if os.path.exists(self.temp_file.name):
            os.remove(self.temp_file.name)

    @patch("src.main.ExchangeClient")
    @patch("src.main.setup_logger")
    def test_save_and_load_state(self, mock_logger: MagicMock, mock_exchange: MagicMock) -> None:
        """Prueba que el estado de posición se guarde y recupere fielmente en JSON."""
        bot = TradingBot(state_file=self.temp_file.name)

        # Modificar atributos simulando una compra activa
        bot.in_position = True
        bot.entry_price = 68500.50
        bot.amount = 0.002
        bot.stop_loss_price = 67472.99
        bot.take_profit_price = 70555.51
        bot.protection_mode = "NATIVE_OCO"
        bot.native_order_ids = ["1001", "1002"]

        # Guardar en disco
        bot._save_state()

        # Instanciar un segundo bot apuntando al mismo archivo para verificar restauración
        restored_bot = TradingBot(state_file=self.temp_file.name)

        self.assertTrue(restored_bot.in_position)
        self.assertEqual(restored_bot.entry_price, 68500.50)
        self.assertEqual(restored_bot.amount, 0.002)
        self.assertEqual(restored_bot.stop_loss_price, 67472.99)
        self.assertEqual(restored_bot.take_profit_price, 70555.51)
        self.assertEqual(restored_bot.protection_mode, "NATIVE_OCO")
        self.assertEqual(restored_bot.native_order_ids, ["1001", "1002"])

    @patch("src.main.ExchangeClient")
    @patch("src.main.setup_logger")
    def test_reset_position(self, mock_logger: MagicMock, mock_exchange: MagicMock) -> None:
        """Prueba que el reseteo limpie variables en RAM y disco."""
        bot = TradingBot(state_file=self.temp_file.name)
        bot.in_position = True
        bot.entry_price = 50000.0
        bot.amount = 0.001
        bot._save_state()

        # Resetear
        bot._reset_position()

        self.assertFalse(bot.in_position)
        self.assertEqual(bot.entry_price, 0.0)
        self.assertEqual(bot.amount, 0.0)
        self.assertEqual(bot.protection_mode, "NONE")
        self.assertEqual(bot.native_order_ids, [])

        with open(self.temp_file.name, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertFalse(data["in_position"])


if __name__ == "__main__":
    unittest.main()
