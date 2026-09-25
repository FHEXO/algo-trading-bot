import unittest
from src.config import Config


class TestConfig(unittest.TestCase):
    """Pruebas unitarias para la configuración central del bot."""

    def test_config_attributes(self) -> None:
        """Verifica que las variables principales de configuración estén definidas."""
        self.assertIsNotNone(Config.EXCHANGE_ID)
        self.assertIsNotNone(Config.SYMBOL)
        self.assertIsNotNone(Config.TIMEFRAME)
        self.assertIsInstance(Config.TESTNET, bool)

    def test_config_validate_success(self) -> None:
        """Config.validate() no debe lanzar error con configuración válida."""
        try:
            Config.validate()
        except Exception as e:
            self.fail(f"Config.validate() falló inesperadamente: {e}")

    def test_config_validate_missing_symbol(self) -> None:
        """Config.validate() debe lanzar ValueError si SYMBOL está vacío."""
        original_symbol = Config.SYMBOL
        try:
            Config.SYMBOL = ""
            with self.assertRaises(ValueError):
                Config.validate()
        finally:
            Config.SYMBOL = original_symbol


if __name__ == "__main__":
    unittest.main()
