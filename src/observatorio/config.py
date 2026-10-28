"""Módulo de carga de configuración del proyecto."""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConfiguracionObservatorio:
    """Almacena los parámetros de configuración de la aplicación."""

    nombre_observatorio: str = "Observatorio Astronómico Nebrija"
    ruta_json: str = "objetos_integrantes.json"
    ruta_validacion: str = "datos_observatorio.json"
    ruta_sqlite: str = "observatorio.db"
    archivo_log: str = "observatorio.log"
    nivel_log: str = "INFO"
    factor_capacidad: int = 3


def cargar_configuracion(ruta: str | Path = "config.example.json") -> ConfiguracionObservatorio:
    """Carga la configuración desde un archivo JSON o devuelve la configuración por defecto.

    Args:
        ruta: Ruta al fichero de configuración JSON.

    Returns:
        Instancia inmutable de ConfiguracionObservatorio.
    """
    ruta_path = Path(ruta)
    if not ruta_path.exists():
        return ConfiguracionObservatorio()

    with open(ruta_path, "r", encoding="utf-8") as archivo:
        datos = json.load(archivo)

    return ConfiguracionObservatorio(
        nombre_observatorio=datos.get("nombre_observatorio", "Observatorio Astronómico Nebrija"),
        ruta_json=datos.get("ruta_json", "objetos_integrantes.json"),
        ruta_validacion=datos.get("ruta_validacion", "datos_observatorio.json"),
        ruta_sqlite=datos.get("ruta_sqlite", "observatorio.db"),
        archivo_log=datos.get("archivo_log", "observatorio.log"),
        nivel_log=datos.get("nivel_log", "INFO"),
        factor_capacidad=int(datos.get("factor_capacidad", 3)),
    )
