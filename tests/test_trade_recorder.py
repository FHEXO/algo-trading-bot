import os
import tempfile
import unittest
import pandas as pd
from src.trade_recorder import TradeRecorder


class TestTradeRecorder(unittest.TestCase):
    """Pruebas unitarias para el registro de operaciones en CSV y Excel."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.csv_path = os.path.join(self.temp_dir.name, "test_trades.csv")
        self.xlsx_path = os.path.join(self.temp_dir.name, "test_trades.xlsx")
        self.recorder = TradeRecorder(csv_file=self.csv_path, excel_file=self.xlsx_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_init_files_created(self) -> None:
        """Verifica que los archivos CSV y XLSX se creen con sus encabezados."""
        self.assertTrue(os.path.exists(self.csv_path))
        self.assertTrue(os.path.exists(self.xlsx_path))

        df_csv = pd.read_csv(self.csv_path, encoding="utf-8-sig")
        self.assertEqual(list(df_csv.columns), TradeRecorder.COLUMNS)

    def test_record_winning_trade(self) -> None:
        """Verifica el cálculo de PnL positivo y registro en el archivo."""
        trade = self.recorder.record_trade(
            entry_time="2026-09-03 12:00:00",
            exit_time="2026-09-03 12:30:00",
            symbol="BTC/USDT",
            amount=0.002,
            entry_price=80000.0,
            exit_price=82400.0,  # +3%
            stop_loss_price=78800.0,
            take_profit_price=82400.0,
            exit_reason="TAKE_PROFIT",
            balance_total=5004.80,
            protection_mode="NATIVE_OCO",
        )

        self.assertEqual(trade["ID"], 1)
        self.assertEqual(trade["PnL_Porcentaje"], "+3.00%")
        self.assertEqual(trade["PnL_USD"], "+4.80")

        # Verificar que se escribió en disco
        df_disk = pd.read_csv(self.csv_path, encoding="utf-8-sig")
        self.assertEqual(len(df_disk), 1)
        self.assertEqual(df_disk.iloc[0]["Motivo_Salida"], "TAKE_PROFIT")

    def test_record_losing_trade(self) -> None:
        """Verifica el cálculo de PnL negativo."""
        trade = self.recorder.record_trade(
            entry_time="2026-09-03 14:00:00",
            exit_time="2026-09-03 14:15:00",
            symbol="BTC/USDT",
            amount=0.002,
            entry_price=80000.0,
            exit_price=78800.0,  # -1.5%
            stop_loss_price=78800.0,
            take_profit_price=82400.0,
            exit_reason="STOP_LOSS",
            balance_total=4997.60,
            protection_mode="SOFTWARE_POLLING",
        )

        self.assertEqual(trade["ID"], 1)
        self.assertEqual(trade["PnL_Porcentaje"], "-1.50%")
        self.assertEqual(trade["PnL_USD"], "-2.40")


if __name__ == "__main__":
    unittest.main()
