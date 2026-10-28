"""Pruebas de integración de extremo a extremo (E2E) para el Gestor de Observatorio."""

import json
from pathlib import Path

from observatorio.cli import main
from observatorio.persistencia import (
    GestorSQLiteObservatorio,
    cargar_repositorio_json,
    cargar_y_validar_registros_json,
    guardar_repositorio_json,
)


def test_integracion_flujo_completo_json_sqlite_y_validacion(tmp_path: Path) -> None:
    """Prueba de integración: Validación JSON -> Repositorio -> Persistencia JSON -> SQLite."""
    ruta_entrada = tmp_path / "entrada_observatorio.json"
    datos_entrada = [
        {
            "identificador": "OBJ-Carlos Balbas",
            "tipo": "Cuerpo-Integrantes",
            "coordenadas": [10.0, 15.0],
            "fecha_descubrimiento": "2023-05-12",
        },
        {
            "identificador": "OBJ-Lucas Parreño",
            "tipo": "Cuerpo-Integrantes",
            "coordenadas": [20.0, 30.0],
            "fecha_descubrimiento": "2024-08-22",
        },
        {
            "identificador": "OBJ-Invalido",
            "tipo": "Asteroide",
            "coordenadas": [50.0, 75.0],
            "fecha_descubrimiento": "2026/02/20",
        },
    ]
    ruta_entrada.write_text(json.dumps(datos_entrada), encoding="utf-8")

    # Paso 1: Cargar y filtrar registros válidos mediante Regex
    repo_validados, errores = cargar_y_validar_registros_json(ruta_entrada)
    assert len(repo_validados) == 2
    assert len(errores) == 1

    # Paso 2: Exportar los validados a un nuevo archivo JSON y recargarlos
    ruta_export_json = tmp_path / "exportados.json"
    guardar_repositorio_json(repo_validados, ruta_export_json)
    repo_recargado_json = cargar_repositorio_json(ruta_export_json)
    assert len(repo_recargado_json) == 2

    for orig, rec in zip(repo_validados, repo_recargado_json):
        assert orig == rec
        assert orig is not rec

    # Paso 3: Persistir en base de datos SQLite y verificar lectura
    ruta_db = tmp_path / "integracion.db"
    gestor_sql = GestorSQLiteObservatorio(ruta_db)
    insertados = gestor_sql.guardar_repositorio(repo_recargado_json)
    assert insertados == 2

    repo_desde_sql = gestor_sql.obtener_todos()
    assert len(repo_desde_sql) == 2
    assert next(iter(repo_desde_sql)).identificador == "OBJ-Carlos Balbas"


def test_integracion_cli_modo_demo(tmp_path: Path) -> None:
    """Prueba de integración del punto de entrada CLI con el argumento --demo."""
    cfg_path = tmp_path / "config.test.json"
    validacion_path = tmp_path / "datos_obs.json"

    validacion_path.write_text(
        json.dumps(
            [
                {
                    "identificador": "OBJ-Victor Llorente",
                    "tipo": "Planeta",
                    "coordenadas": [30.0, 45.0],
                    "fecha_descubrimiento": "2025-11-03",
                }
            ]
        ),
        encoding="utf-8",
    )

    cfg_data = {
        "nombre_observatorio": "Observatorio Test CLI",
        "ruta_json": str(tmp_path / "salida.json"),
        "ruta_validacion": str(validacion_path),
        "ruta_sqlite": str(tmp_path / "salida.db"),
        "archivo_log": str(tmp_path / "salida.log"),
        "nivel_log": "INFO",
        "factor_capacidad": 3,
    }
    cfg_path.write_text(json.dumps(cfg_data), encoding="utf-8")

    codigo_salida = main(["--demo", "--config", str(cfg_path)])
    assert codigo_salida == 0
    assert (tmp_path / "salida.json").exists()
    assert (tmp_path / "salida.db").exists()
    assert (tmp_path / "salida.log").exists()
