import logging
import os
from typing import Optional


def setup_logger(
    name: str = "TradingBot", log_file: str = "logs/trading_bot.log"
) -> logging.Logger:
    """Configura un registrador profesional con salida simultánea a consola y archivo."""
    # 1. Crear carpeta 'logs' si no existe
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # 2. Instanciar logger base
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Evitar duplicación de manejadores si ya está configurado
    if logger.hasHandlers():
        return logger

    # 3. Formato estándar para auditoría institucional
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 4. Manejador de Archivo (guarda todo desde nivel DEBUG)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # 5. Manejador de Consola (muestra desde nivel INFO para no saturar)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 6. Adjuntar manejadores
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


if __name__ == "__main__":
    # Prueba del sistema de logs
    test_log = setup_logger()
    test_log.info("Sistema de Logging inicializado correctamente.")
    test_log.warning("Prueba de advertencia: Nivel medio.")
    test_log.error("Prueba de error: Nivel alto.")