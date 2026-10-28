"""Módulo de persistencia (JSON y SQLite) y validación con expresiones regulares."""

import json
import logging
import re
import sqlite3
from pathlib import Path

import regex

from observatorio.modelo import (
    ObjetoCeleste,
    PersistenciaError,
    RegistroInvalidoError,
    Repositorio,
)

PATRON_FECHA_RAW = r"^\d{4}-\d{2}-\d{2}$"
COMPILADO_RE = re.compile(PATRON_FECHA_RAW)
COMPILADO_REGEX = regex.compile(PATRON_FECHA_RAW)


def guardar_repositorio_json(
    repositorio: Repositorio[ObjetoCeleste],
    ruta_archivo: str | Path,
    logger: logging.Logger | None = None,
) -> None:
    """Serializa y guarda un Repositorio de ObjetoCeleste en un fichero JSON.

    Args:
        repositorio: Repositorio cuyos objetos se van a exportar.
        ruta_archivo: Ruta de destino del fichero JSON.
        logger: Logger opcional para registrar la operación.

    Raises:
        PersistenciaError: Si ocurre un error de escritura en disco.
    """
    datos_serializados = [obj.a_diccionario() for obj in repositorio]
    try:
        with open(ruta_archivo, "w", encoding="utf-8") as archivo:
            json.dump(datos_serializados, archivo, indent=4, ensure_ascii=False)
        if logger:
            logger.info(
                "Persistencia JSON exitosa: %d objetos guardados en '%s'.",
                len(datos_serializados),
                ruta_archivo,
            )
    except OSError as error:
        if logger:
            logger.error("Error al escribir archivo JSON '%s': %s", ruta_archivo, error)
        raise PersistenciaError(f"No se pudo guardar en '{ruta_archivo}': {error}") from error


def cargar_repositorio_json(
    ruta_archivo: str | Path,
    logger: logging.Logger | None = None,
) -> Repositorio[ObjetoCeleste]:
    """Carga y reconstruye un Repositorio de ObjetoCeleste desde un fichero JSON.

    Args:
        ruta_archivo: Ruta de origen del fichero JSON.
        logger: Logger opcional para registrar el evento.

    Returns:
        Nuevo Repositorio con las instancias reconstruidas en memoria.

    Raises:
        PersistenciaError: Si el archivo no existe o el JSON está corrupto.
    """
    repo_reconstruido: Repositorio[ObjetoCeleste] = Repositorio()
    try:
        with open(ruta_archivo, "r", encoding="utf-8") as archivo:
            datos_recuperados = json.load(archivo)
        for item in datos_recuperados:
            obj_nuevo = ObjetoCeleste.desde_diccionario(item)
            repo_reconstruido.agregar(obj_nuevo)
        if logger:
            logger.info(
                "Carga JSON exitosa: %d objetos reconstruidos desde '%s'.",
                len(repo_reconstruido),
                ruta_archivo,
            )
        return repo_reconstruido
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as error:
        if logger:
            logger.error("Fallo al cargar JSON '%s': %s", ruta_archivo, error)
        raise PersistenciaError(f"Error cargando '{ruta_archivo}': {error}") from error


def validar_registro_diccionario(registro: dict[str, object], indice: int = 0) -> ObjetoCeleste:
    """Valida un diccionario crudo verificando su fecha mediante expresiones regulares.

    Args:
        registro: Diccionario con identificador, tipo, coordenadas y fecha_descubrimiento.
        indice: Posición del registro para trazabilidad de errores.

    Returns:
        Instancia válida de ObjetoCeleste.

    Raises:
        RegistroInvalidoError: Si falta algún campo obligatorio o el formato de fecha falla.
    """
    nombre = str(registro.get("identificador", f"Desconocido-{indice}"))
    if "fecha_descubrimiento" not in registro:
        raise RegistroInvalidoError(
            f"[{nombre}] Falla: Falta el campo obligatorio 'fecha_descubrimiento'."
        )

    fecha = str(registro["fecha_descubrimiento"])
    if not COMPILADO_RE.match(fecha) or not COMPILADO_REGEX.match(fecha):
        raise RegistroInvalidoError(
            f"[{nombre}] Falla: Formato de fecha '{fecha}' no es válido (Debe ser YYYY-MM-DD)."
        )

    try:
        return ObjetoCeleste.desde_diccionario(registro)
    except (KeyError, ValueError, TypeError) as error:
        raise RegistroInvalidoError(f"[{nombre}] Falla en datos del objeto: {error}") from error


def cargar_y_validar_registros_json(
    ruta_archivo: str | Path,
    logger: logging.Logger | None = None,
) -> tuple[Repositorio[ObjetoCeleste], list[str]]:
    """Lee un archivo JSON de registros astronómicos, validando cada entrada con regex.

    Args:
        ruta_archivo: Ruta al fichero JSON con los registros a validar.
        logger: Logger opcional para registrar aceptaciones y rechazos.

    Returns:
        Tupla con (Repositorio de objetos válidos, lista de mensajes de error rechazados).
    """
    repo_validados: Repositorio[ObjetoCeleste] = Repositorio()
    errores: list[str] = []

    try:
        with open(ruta_archivo, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, json.JSONDecodeError) as error:
        raise PersistenciaError(f"No se pudo leer '{ruta_archivo}': {error}") from error

    for i, registro in enumerate(datos, 1):
        try:
            obj = validar_registro_diccionario(registro, i)
            repo_validados.agregar(obj)
            if logger:
                logger.info("Registro validado con éxito: %s", obj.identificador)
        except RegistroInvalidoError as error:
            mensaje_error = str(error)
            errores.append(mensaje_error)
            if logger:
                logger.warning("Registro rechazado en validación: %s", mensaje_error)

    return repo_validados, errores


class GestorSQLiteObservatorio:
    """Gestiona la persistencia relacional de objetos celestes mediante SQLite3."""

    def __init__(self, ruta_db: str | Path = "observatorio.db") -> None:
        self.ruta_db = Path(ruta_db)
        self._inicializar_tablas()

    def _inicializar_tablas(self) -> None:
        """Crea la tabla de objetos celestes si no existe en la base de datos."""
        try:
            with sqlite3.connect(self.ruta_db) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS objetos_celestes (
                        identificador TEXT PRIMARY KEY,
                        tipo TEXT NOT NULL,
                        ascension_recta REAL NOT NULL,
                        declinacion REAL NOT NULL
                    )
                    """)
                conn.commit()
        except sqlite3.Error as error:
            raise PersistenciaError(f"Error inicializando SQLite: {error}") from error

    def guardar_objeto(self, objeto: ObjetoCeleste) -> None:
        """Inserta o actualiza un ObjetoCeleste en la base de datos SQLite."""
        ar, dec = objeto.coordenadas
        try:
            with sqlite3.connect(self.ruta_db) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO objetos_celestes
                    (identificador, tipo, ascension_recta, declinacion)
                    VALUES (?, ?, ?, ?)
                    """,
                    (objeto.identificador, objeto.tipo, ar, dec),
                )
                conn.commit()
        except sqlite3.Error as error:
            raise PersistenciaError(f"Error guardando objeto en SQLite: {error}") from error

    def guardar_repositorio(self, repositorio: Repositorio[ObjetoCeleste]) -> int:
        """Guarda todos los elementos de un repositorio dentro de una transacción SQLite."""
        contador = 0
        for obj in repositorio:
            self.guardar_objeto(obj)
            contador += 1
        return contador

    def obtener_todos(self) -> Repositorio[ObjetoCeleste]:
        """Recupera todos los objetos celestes almacenados en la base de datos SQLite."""
        repo: Repositorio[ObjetoCeleste] = Repositorio()
        try:
            with sqlite3.connect(self.ruta_db) as conn:
                cursor = conn.execute(
                    "SELECT identificador, tipo, ascension_recta, declinacion "
                    "FROM objetos_celestes ORDER BY rowid ASC"
                )
                for fila in cursor.fetchall():
                    obj = ObjetoCeleste(fila[0], fila[1], (float(fila[2]), float(fila[3])))
                    repo.agregar(obj)
            return repo
        except sqlite3.Error as error:
            raise PersistenciaError(f"Error consultando SQLite: {error}") from error
