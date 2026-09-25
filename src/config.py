import os
from typing import List
from dotenv import load_dotenv

# Cargar variables desde el archivo .env a la memoria del sistema
load_dotenv()


class Config:
    """Centraliza y valida todos los parámetros de configuración del bot."""

    EXCHANGE_ID: str = os.getenv("EXCHANGE_ID", "binance_testnet")
    
    # 1. Obtenemos el texto desde .env y lo convertimos en una lista de símbolos
    _raw_symbols: str = os.getenv("SYMBOLS", os.getenv("SYMBOL", "BTC/USDT,ETH/USDT,SOL/USDT"))
    SYMBOLS: List[str] = [s.strip() for s in _raw_symbols.split(",") if s.strip()]

    TIMEFRAME: str = os.getenv("TIMEFRAME", "1h")
    TESTNET: bool = os.getenv("TESTNET", "true").lower() == "true"

    API_KEY: str = os.getenv("API_KEY", "")
    API_SECRET: str = os.getenv("API_SECRET", "")

    @classmethod
    def validate(cls) -> None:
        """Verifica que los parámetros mínimos obligatorios existan."""
        if not cls.SYMBOLS:
            raise ValueError("El parámetro SYMBOLS no puede estar vacío.")
        print(
            f"[CONFIG] Modo: {'TESTNET (Simulación)' if cls.TESTNET else 'PRODUCCIÓN'}"
        )
        print(f"[CONFIG] Pares a monitorear ({len(cls.SYMBOLS)}): {cls.SYMBOLS} | Temporalidad: {cls.TIMEFRAME}")


# Ejecutar validación al importar el módulo
Config.validate()