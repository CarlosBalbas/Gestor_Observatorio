"""Pruebas de las reglas de dominio y de los caminos de error de la persistencia."""

import json
import sqlite3
from pathlib import Path

import pytest

from observatorio.cli import main
from observatorio.logger import configurar_logger
from observatorio.modelo import (
    OBJETOS_PROTEGIDOS,
    CapacidadMaximaError,
    CatalogoObservatorio,
    ObjetoCeleste,
    ObjetoDuplicadoError,
    PersistenciaError,
    Repositorio,
    crear_catalogo_ejemplo,
)
from observatorio.patrones import AuditoriaLoggerObservador, CatalogoObservable
from observatorio.persistencia import (
    GestorSQLiteObservatorio,
    cargar_repositorio_json,
    cargar_y_validar_registros_json,
    guardar_repositorio_json,
)


def _obj(ident: str, ar: float = 1.0) -> ObjetoCeleste:
    return ObjetoCeleste(ident, "Estrella", (ar, 1.0))


# --------------------------------------------------------------------- dominio


def test_objeto_celeste_es_hashable_y_coherente_con_eq() -> None:
    """Dos objetos iguales tienen el mismo hash: se pueden usar en sets y como claves."""
    a = _obj("Vega")
    b = _obj("Vega")
    assert a == b and a is not b
    assert hash(a) == hash(b)
    assert len({a, b}) == 1
    assert {a: "visto"}[b] == "visto"


def test_objeto_celeste_rechaza_tipos_no_texto() -> None:
    """Un identificador que no es str produce TypeError, no AttributeError."""
    with pytest.raises(TypeError):
        ObjetoCeleste(123, "Estrella", (1.0, 1.0))  # type: ignore[arg-type]


@pytest.mark.parametrize("factor,esperada", [(1, 8), (3, 24), (5, 40)])
def test_factor_capacidad_configurable(factor: int, esperada: int) -> None:
    """La capacidad máxima depende del factor (antes estaba fijado a 3)."""
    assert crear_catalogo_ejemplo(factor).capacidad_maxima == esperada
    assert CatalogoObservable("C", [_obj("A"), _obj("B")], factor).capacidad_maxima == 2 * factor


@pytest.mark.parametrize("factor", [0, -1, 2.5])
def test_factor_capacidad_invalido(factor: object) -> None:
    with pytest.raises(ValueError):
        CatalogoObservatorio("C", None, factor)  # type: ignore[arg-type]


def test_catalogo_vacio_usa_base_8() -> None:
    assert CatalogoObservatorio("Vacío").capacidad_maxima == 24
    with pytest.raises(ValueError):
        CatalogoObservatorio("   ")
    with pytest.raises(ObjetoDuplicadoError):
        CatalogoObservatorio("C", [_obj("A"), _obj("A")])


def test_anadir_rechaza_identificador_duplicado() -> None:
    catalogo = crear_catalogo_ejemplo()
    with pytest.raises(ObjetoDuplicadoError):
        catalogo.anadir(_obj("Sol"))
    assert isinstance(ObjetoDuplicadoError("x"), ValueError)
    assert len(catalogo.objetos) == 8


def test_eliminar_objetos() -> None:
    """Protegidos -> ValueError; inexistente -> False; personalizado -> True."""
    catalogo = crear_catalogo_ejemplo()
    for protegido in OBJETOS_PROTEGIDOS:
        with pytest.raises(ValueError, match="protegido"):
            catalogo.eliminar(protegido)
    assert catalogo.eliminar("No-Existe") is False
    catalogo.anadir(_obj("Temporal"))
    assert catalogo.eliminar("  Temporal  ") is True
    assert catalogo.buscar_por_id("Temporal") is None


def test_reemplazar_objetos_notifica_y_es_atomico() -> None:
    """reemplazar_objetos pasa por anadir (Observer) y no toca nada si no cabe."""
    import logging

    observador = AuditoriaLoggerObservador(logging.getLogger("test_reemplazar"))
    catalogo = CatalogoObservable("C", [_obj("A")], 3)  # capacidad 3
    catalogo.suscribir(observador)

    catalogo.reemplazar_objetos([_obj("X"), _obj("Y")])
    assert [o.identificador for o in catalogo.objetos] == ["X", "Y"]
    assert len(observador.eventos_registrados) == 2

    with pytest.raises(CapacidadMaximaError):
        catalogo.reemplazar_objetos([_obj(str(i)) for i in range(4)])
    with pytest.raises(ObjetoDuplicadoError):
        catalogo.reemplazar_objetos([_obj("Z"), _obj("Z")])
    assert [o.identificador for o in catalogo.objetos] == ["X", "Y"]  # intacto


# ------------------------------------------------------------------ persistencia


def test_cargar_json_inexistente_lanza_persistencia_error(tmp_path: Path) -> None:
    with pytest.raises(PersistenciaError) as info:
        cargar_repositorio_json(tmp_path / "no_existe.json")
    assert isinstance(info.value.__cause__, OSError)  # raise ... from error


@pytest.mark.parametrize(
    "contenido",
    [
        "{no es json",
        '{"identificador": "A"}',
        '["texto suelto"]',
        '[{"identificador": "A", "tipo": "Estrella"}]',
        '[{"identificador": "A", "tipo": "Estrella", "coordenadas": [500, 0]}]',
    ],
)
def test_cargar_json_mal_formado(tmp_path: Path, contenido: str) -> None:
    """Cualquier JSON corrupto o con datos inválidos acaba en PersistenciaError."""
    ruta = tmp_path / "malo.json"
    ruta.write_text(contenido, encoding="utf-8")
    with pytest.raises(PersistenciaError):
        cargar_repositorio_json(ruta)


def test_guardar_json_en_ruta_imposible(tmp_path: Path) -> None:
    repo: Repositorio[ObjetoCeleste] = Repositorio()
    repo.agregar(_obj("A"))
    with pytest.raises(PersistenciaError):
        guardar_repositorio_json(repo, tmp_path / "no" / "existe" / "x.json")


def test_validacion_registros_casos_limite(tmp_path: Path) -> None:
    """Registros que no son objetos o con coordenadas malas se rechazan sin parar la carga."""
    ruta = tmp_path / "registros.json"
    ruta.write_text(
        json.dumps(
            [
                "no soy un diccionario",
                {"identificador": "Mal", "tipo": "X", "fecha_descubrimiento": "2024-01-01"},
                {
                    "identificador": "Bien",
                    "tipo": "Estrella",
                    "coordenadas": [1, 2],
                    "fecha_descubrimiento": "2024-01-01",
                },
            ]
        ),
        encoding="utf-8",
    )
    validos, errores = cargar_y_validar_registros_json(ruta)
    assert [o.identificador for o in validos] == ["Bien"]
    assert len(errores) == 2

    ruta.write_text('{"no": "es una lista"}', encoding="utf-8")
    with pytest.raises(PersistenciaError):
        cargar_y_validar_registros_json(ruta)
    with pytest.raises(PersistenciaError):
        cargar_y_validar_registros_json(tmp_path / "no_existe.json")


def test_sqlite_guardar_objeto_y_reemplazo(tmp_path: Path) -> None:
    """guardar_objeto inserta y, con el mismo identificador, actualiza (INSERT OR REPLACE)."""
    gestor = GestorSQLiteObservatorio(tmp_path / "obs.db")
    gestor.guardar_objeto(_obj("A", 1.0))
    gestor.guardar_objeto(_obj("A", 2.0))
    todos = gestor.obtener_todos().obtener_todos()
    assert todos == [_obj("A", 2.0)]


def test_sqlite_guardar_repositorio_es_todo_o_nada(tmp_path: Path) -> None:
    """Si una fila falla, la transacción hace ROLLBACK y no queda guardada ninguna."""
    ruta = tmp_path / "obs.db"
    gestor = GestorSQLiteObservatorio(ruta)
    with sqlite3.connect(ruta) as conexion:
        conexion.execute("""
            CREATE TRIGGER rechazar_malo BEFORE INSERT ON objetos_celestes
            WHEN NEW.identificador = 'MALO'
            BEGIN SELECT RAISE(ABORT, 'fila rechazada'); END
            """)
    conexion.close()

    repo: Repositorio[ObjetoCeleste] = Repositorio()
    for ident in ("A", "B", "MALO", "C"):
        repo.agregar(_obj(ident))

    with pytest.raises(PersistenciaError):
        gestor.guardar_repositorio(repo)
    assert len(gestor.obtener_todos()) == 0  # ni A ni B se han quedado guardados


def test_sqlite_errores_se_envuelven(tmp_path: Path) -> None:
    """Los sqlite3.Error se convierten en PersistenciaError en cada operación."""
    with pytest.raises(PersistenciaError):
        GestorSQLiteObservatorio(tmp_path)  # un directorio no es una base de datos

    ruta = tmp_path / "obs.db"
    gestor = GestorSQLiteObservatorio(ruta)
    with sqlite3.connect(ruta) as conexion:
        conexion.execute("DROP TABLE objetos_celestes")
    conexion.close()
    with pytest.raises(PersistenciaError):
        gestor.guardar_objeto(_obj("A"))
    with pytest.raises(PersistenciaError):
        gestor.guardar_repositorio(Repositorio())
    with pytest.raises(PersistenciaError):
        gestor.obtener_todos()


# ------------------------------------------------------------------------- CLI


def test_cli_aplica_factor_capacidad_de_la_config(tmp_path: Path) -> None:
    """El factor_capacidad del JSON de configuración llega al catálogo de la demo."""
    cfg = tmp_path / "cfg.json"
    cfg.write_text(
        json.dumps(
            {
                "ruta_json": str(tmp_path / "s.json"),
                "ruta_validacion": str(tmp_path / "no_hay.json"),
                "ruta_sqlite": str(tmp_path / "s.db"),
                "archivo_log": str(tmp_path / "s.log"),
                "factor_capacidad": 2,
            }
        ),
        encoding="utf-8",
    )
    assert main(["--config", str(cfg)]) == 0  # sin argumentos también ejecuta la demo
    log = (tmp_path / "s.log").read_text(encoding="utf-8")
    assert "(16/16)" in log  # 8 objetos x factor 2
    assert "(24/24)" not in log


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as salida:
        main(["--version"])
    assert salida.value.code == 0
    assert "1.0.0" in capsys.readouterr().out


def test_logger_cambia_de_fichero_sin_duplicar(tmp_path: Path) -> None:
    """Reconfigurar con otro fichero redirige el log; con el mismo, no duplica manejadores."""
    primero, segundo = tmp_path / "uno.log", tmp_path / "dos.log"
    logger = configurar_logger("test_logger_ficheros", primero)
    configurar_logger("test_logger_ficheros", primero)
    assert len(logger.handlers) == 2

    configurar_logger("test_logger_ficheros", segundo)
    logger.info("mensaje de prueba")
    assert len(logger.handlers) == 2
    assert "mensaje de prueba" in segundo.read_text(encoding="utf-8")
    assert "mensaje de prueba" not in primero.read_text(encoding="utf-8")


def test_python_m_observatorio_usa_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """`python -m observatorio --version` pasa por __main__.py y sale con código 0."""
    import runpy

    monkeypatch.setattr("sys.argv", ["observatorio", "--version"])
    with pytest.raises(SystemExit) as salida:
        runpy.run_module("observatorio", run_name="__main__")
    assert salida.value.code == 0
