"""Interfaz de línea de comandos (CLI) y modo demostración (--demo) del proyecto."""

import argparse
from pathlib import Path

from observatorio import __version__
from observatorio.config import cargar_configuracion
from observatorio.logger import configurar_logger
from observatorio.modelo import (
    CapacidadMaximaError,
    ObjetoCeleste,
    Repositorio,
    SesionObservacion,
    crear_catalogo_ejemplo,
    mostrar_resumen,
)
from observatorio.patrones import (
    AuditoriaLoggerObservador,
    CatalogoObservable,
    FabricaTelescopios,
)
from observatorio.persistencia import (
    GestorSQLiteObservatorio,
    cargar_repositorio_json,
    cargar_y_validar_registros_json,
    guardar_repositorio_json,
)

INTEGRANTES: tuple[str, ...] = ("Carlos Balbas", "Lucas Parreño", "Victor Llorente")


def ejecutar_demo(ruta_config: str = "config.example.json") -> None:
    """Ejecuta la demostración integral de la aplicación en menos de 5 minutos."""
    config = cargar_configuracion(ruta_config)
    logger = configurar_logger("observatorio", config.archivo_log, config.nivel_log)

    logger.info("=" * 65)
    logger.info("INICIANDO DEMO: %s (v%s)", config.nombre_observatorio, __version__)
    logger.info("Integrantes: %s", ", ".join(INTEGRANTES))
    logger.info("=" * 65)

    # 1. Patrón Factory y Polimorfismo de Telescopios (ABC)
    logger.info("--- 1. Creación de Telescopios mediante Patrón Factory ---")
    refractor = FabricaTelescopios.crear_telescopio("refractor", "Refractor Norte", 5, 120)
    reflector = FabricaTelescopios.crear_telescopio("reflector", "Reflector Sur", 12, 250)
    for tel in (refractor, reflector):
        logger.info("Equipo activo -> %s", tel.descripcion_tecnica().strip())

    # 2. Catálogo Observable (Patrón Observer) y manejo de CapacidadMaximaError
    logger.info("--- 2. Catálogo Observable (Patrón Observer) y Sesiones ---")
    catalogo_base = crear_catalogo_ejemplo(config.factor_capacidad)
    catalogo = CatalogoObservable(
        catalogo_base.nombre, catalogo_base.objetos, config.factor_capacidad
    )
    observador = AuditoriaLoggerObservador(logger)
    catalogo.suscribir(observador)

    andromeda = ObjetoCeleste("M31-Andromeda", "Galaxia", (10.68, 41.26))
    catalogo.anadir(andromeda)

    sesion = SesionObservacion("2026-10-27", refractor, andromeda)
    sesion.registrar_horas(3)
    mostrar_resumen(sesion)
    mostrar_resumen(catalogo)

    # Demostración de excepción controlada CapacidadMaximaError
    while len(catalogo.objetos) < catalogo.capacidad_maxima:
        catalogo.anadir(ObjetoCeleste(f"Estrella-{len(catalogo.objetos)}", "Estrella", (1.0, 1.0)))

    try:
        catalogo.anadir(ObjetoCeleste("Objeto-Exceso", "Nebulosa", (15.0, 20.0)))
    except CapacidadMaximaError as error:
        logger.error("Excepción controlada capturada con éxito: %s", error)

    # 3. Persistencia JSON e Identidad vs Igualdad
    logger.info("--- 3. Persistencia en JSON y comprobación == vs is ---")
    repo_original: Repositorio[ObjetoCeleste] = Repositorio()
    for idx, integrante in enumerate(INTEGRANTES, start=1):
        obj = ObjetoCeleste(f"OBJ-{integrante}", "Cuerpo-Integrantes", (10.0 * idx, 15.0 * idx))
        repo_original.agregar(obj)

    guardar_repositorio_json(repo_original, config.ruta_json, logger)
    repo_reconstruido = cargar_repositorio_json(config.ruta_json, logger)

    for orig, rec in zip(repo_original, repo_reconstruido):
        assert orig == rec and orig is not rec
        logger.info(
            "Verificado '%s': orig == rec (%s) | orig is rec (%s)",
            orig.identificador,
            orig == rec,
            orig is rec,
        )

    # 4. Validación de fichero de entrada con Expresiones Regulares
    if Path(config.ruta_validacion).exists():
        logger.info("--- 4. Validación de Registros con Regex (re y regex) ---")
        validados, errores = cargar_y_validar_registros_json(config.ruta_validacion, logger)
        logger.info(
            "Resumen validación: %d aceptados, %d rechazados.",
            len(validados),
            len(errores),
        )

    # 5. Persistencia en Base de Datos SQLite
    logger.info("--- 5. Persistencia Relacional en SQLite ---")
    gestor_sql = GestorSQLiteObservatorio(config.ruta_sqlite)
    total_sql = gestor_sql.guardar_repositorio(repo_original)
    recuperados_sql = gestor_sql.obtener_todos()
    logger.info(
        "SQLite '%s': %d objetos insertados y %d recuperados correctamente.",
        config.ruta_sqlite,
        total_sql,
        len(recuperados_sql),
    )

    logger.info("=" * 65)
    logger.info("DEMO FINALIZADA CON ÉXITO. Revisa el archivo '%s'.", config.archivo_log)
    logger.info("=" * 65)


def construir_parser() -> argparse.ArgumentParser:
    """Construye el analizador de argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        prog="observatorio",
        description="Gestor de Observatorio Astronómico - TPA Universidad Nebrija",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Ejecuta la demostración completa reproducible en menos de 5 minutos.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.example.json",
        help="Ruta al archivo de configuración JSON.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s v{__version__}",
    )
    # interfaz
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Abre la interfaz gráfica de usuario (GUI) del observatorio.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada principal de la aplicación."""
    parser = construir_parser()
    args = parser.parse_args(argv)

    # interfaz
    if args.gui:
        from observatorio.interfaz import iniciar_interfaz

        iniciar_interfaz(cargar_configuracion(args.config))
        return 0

    if args.demo:
        ejecutar_demo(args.config)
        return 0

    # Si se invoca sin argumentos, ejecutamos también el flujo de demostración interactivo
    ejecutar_demo(args.config)
    return 0
