"""Configuración centralizada del sistema de logging para el observatorio."""

import logging
import sys
from pathlib import Path


def configurar_logger(
    nombre: str = "observatorio",
    archivo_log: str | Path = "observatorio.log",
    nivel: str = "INFO",
) -> logging.Logger:
    """Configura y devuelve un logger con salida a fichero y consola.

    Args:
        nombre: Nombre identificador del logger.
        archivo_log: Ruta del archivo donde persistir los registros de log.
        nivel: Nivel mínimo de severidad (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns:
        Instancia de logging.Logger configurada.
    """
    logger = logging.getLogger(nombre)
    nivel_num = getattr(logging, nivel.upper(), logging.INFO)
    logger.setLevel(nivel_num)

    if not logger.handlers:
        formato = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        manejador_archivo = logging.FileHandler(archivo_log, encoding="utf-8")
        manejador_archivo.setFormatter(formato)
        logger.addHandler(manejador_archivo)

        manejador_consola = logging.StreamHandler(sys.stdout)
        manejador_consola.setFormatter(formato)
        logger.addHandler(manejador_consola)

    return logger
