"""Pruebas de la interfaz gráfica Tkinter, incluida la E/S en segundo plano.

Si Tkinter no está instalado o no hay entorno gráfico, las pruebas se omiten
(``skip``) en lugar de romper la recogida de toda la suite.
"""

import gc
import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

tk = pytest.importorskip("tkinter", reason="Tkinter no está instalado en este Python.")

from observatorio import interfaz
from observatorio.config import ConfiguracionObservatorio
from observatorio.persistencia import GestorSQLiteObservatorio


def esperar_tareas(ventana: interfaz.VentanaObservatorio, limite_s: float = 5.0) -> None:
    """Procesa eventos de Tk hasta que termine la operación en segundo plano."""
    fin = time.monotonic() + limite_s
    while ventana.ocupada:
        if time.monotonic() > fin:
            raise TimeoutError("La tarea en segundo plano no ha terminado a tiempo")
        ventana.update()
        time.sleep(0.01)


def rellenar_formulario(
    ventana: interfaz.VentanaObservatorio, ident: str, tipo: str, ar: str, dec: str
) -> None:
    """Escribe los cuatro campos del formulario de alta."""
    for campo, valor in (
        (ventana.txt_id, ident),
        (ventana.txt_tipo, tipo),
        (ventana.txt_ar, ar),
        (ventana.txt_dec, dec),
    ):
        campo.delete(0, tk.END)
        campo.insert(0, valor)


@pytest.fixture
def dialogos(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Sustituye los cuadros de diálogo y registra (tipo, título) de cada uno."""
    llamados: list[tuple[str, str]] = []

    def registrar(tipo: str, respuesta: object = None):
        def falso(titulo: str, *args: object, **kwargs: object) -> object:
            llamados.append((tipo, titulo))
            return respuesta

        return falso

    monkeypatch.setattr(interfaz.messagebox, "showinfo", registrar("info"))
    monkeypatch.setattr(interfaz.messagebox, "showwarning", registrar("warning"))
    monkeypatch.setattr(interfaz.messagebox, "showerror", registrar("error"))
    monkeypatch.setattr(interfaz.messagebox, "askyesno", registrar("askyesno", True))
    monkeypatch.setattr(interfaz.messagebox, "askquestion", registrar("askquestion", "yes"))
    return llamados


@pytest.fixture
def ventana(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, dialogos: list[tuple[str, str]]
) -> Iterator[interfaz.VentanaObservatorio]:
    """Crea una ventana oculta que trabaja en un directorio temporal."""
    monkeypatch.chdir(tmp_path)
    config = ConfiguracionObservatorio(ruta_sqlite=str(tmp_path / "gui.db"))
    # En Windows, crear muchas ventanas Tk() seguidas en un mismo proceso falla a veces
    # con un TclError intermitente: se reintenta antes de omitir la prueba.
    app = None
    ultimo_error: tk.TclError | None = None
    for _ in range(3):
        try:
            app = interfaz.VentanaObservatorio(
                ruta_json=tmp_path / "catalogo_gui.json", config=config
            )
            break
        except tk.TclError as error:
            ultimo_error = error
            gc.collect()
            time.sleep(0.1)
    if app is None:
        pytest.skip(f"No se pudo crear la ventana Tkinter: {ultimo_error}")
    app.withdraw()
    yield app
    app.destroy()
    # Tcl solo admite llamadas desde el hilo que creó el intérprete. Se libera aquí la
    # ventana (que tiene ciclos de referencias) para que el recolector de basura no lo
    # haga más tarde dentro del hilo de trabajo de otra prueba, lo que abortaría Tcl.
    del app
    gc.collect()


def test_interfaz_carga_catalogo_inicial(ventana) -> None:
    """La interfaz muestra inicialmente los objetos del catálogo."""
    assert len(ventana.catalogo.objetos) == 8
    assert len(ventana.tabla.get_children()) == 8
    assert "8 / 24" in ventana.lbl_estado.cget("text")


def test_interfaz_anadir_objeto(ventana) -> None:
    """Comprueba la creación de un objeto desde el formulario (admite coma decimal)."""
    rellenar_formulario(ventana, "M31-GUI", "Galaxia", "10,68", "41.26")
    ventana._on_anadir_objeto()

    objeto = ventana.catalogo.buscar_por_id("M31-GUI")
    assert objeto is not None
    assert objeto.coordenadas == (10.68, 41.26)
    assert ventana.txt_id.get() == ""


@pytest.mark.parametrize(
    "ident,tipo,ar,dec",
    [
        ("", "Galaxia", "10", "10"),  # campo vacío
        ("X", "Galaxia", "abc", "10"),  # no numérico
        ("X", "Galaxia", "400", "10"),  # fuera de rango
        ("Sol", "Estrella", "10", "10"),  # duplicado
    ],
)
def test_interfaz_anadir_objeto_invalido(ventana, dialogos, ident, tipo, ar, dec) -> None:
    """Las entradas erróneas muestran un error y no modifican el catálogo."""
    rellenar_formulario(ventana, ident, tipo, ar, dec)
    ventana._on_anadir_objeto()
    assert len(ventana.catalogo.objetos) == 8
    assert dialogos[-1][0] == "error"


def test_interfaz_anadir_con_catalogo_lleno(ventana, dialogos) -> None:
    """Superar la capacidad muestra un aviso en lugar de romper la aplicación."""
    while len(ventana.catalogo.objetos) < ventana.catalogo.capacidad_maxima:
        rellenar_formulario(ventana, f"E-{len(ventana.catalogo.objetos)}", "Estrella", "1", "1")
        ventana._on_anadir_objeto()
    rellenar_formulario(ventana, "Exceso", "Nebulosa", "1", "1")
    ventana._on_anadir_objeto()
    assert dialogos[-1] == ("warning", "Capacidad Máxima")


def test_interfaz_guardar_y_cargar_json(ventana) -> None:
    """Guardar y cargar se hacen en segundo plano y la carga pasa por el dominio."""
    rellenar_formulario(ventana, "OBJ-GUI", "Estrella", "20", "30")
    ventana._on_anadir_objeto()

    ventana._on_guardar_json()
    assert ventana.ocupada  # la escritura se ha lanzado en el hilo de trabajo
    esperar_tareas(ventana)
    assert ventana.ruta_json.exists()

    ventana.catalogo.eliminar("OBJ-GUI")
    eventos_antes = len(ventana.observador.eventos_registrados)

    ventana._on_cargar_json()
    esperar_tareas(ventana)

    assert ventana.catalogo.buscar_por_id("OBJ-GUI") is not None
    assert len(ventana.tabla.get_children()) == 9
    # reemplazar_objetos() usa anadir(): el Observer recibe una notificación por objeto
    assert len(ventana.observador.eventos_registrados) - eventos_antes == 9


def test_interfaz_cargar_json_que_no_cabe(ventana, dialogos) -> None:
    """Un JSON con más objetos que la capacidad se rechaza y el catálogo queda intacto."""
    datos = [
        {"identificador": f"O-{i}", "tipo": "Estrella", "coordenadas": [1.0, 1.0]}
        for i in range(ventana.catalogo.capacidad_maxima + 1)
    ]
    ventana.ruta_json.write_text(json.dumps(datos), encoding="utf-8")

    ventana._on_cargar_json()
    esperar_tareas(ventana)

    assert dialogos[-1] == ("warning", "Capacidad Máxima")
    assert len(ventana.catalogo.objetos) == 8


def test_interfaz_cargar_json_corrupto_y_ausente(ventana, dialogos) -> None:
    """Un JSON inexistente avisa y uno corrupto muestra un error de persistencia."""
    ventana._on_cargar_json()
    assert dialogos[-1] == ("warning", "Aviso")

    ventana.ruta_json.write_text("{esto no es json", encoding="utf-8")
    ventana._on_cargar_json()
    esperar_tareas(ventana)
    assert dialogos[-1] == ("error", "Error de Persistencia")
    assert len(ventana.catalogo.objetos) == 8


def test_interfaz_exportar_sqlite(ventana) -> None:
    """La exportación a SQLite en segundo plano guarda todo el catálogo."""
    ventana._on_exportar_sqlite()
    esperar_tareas(ventana)
    recuperados = GestorSQLiteObservatorio(ventana.ruta_sqlite).obtener_todos()
    assert len(recuperados) == 8


def test_interfaz_es_no_bloquea_y_no_admite_dos_a_la_vez(
    ventana, dialogos, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La E/S corre en otro hilo: la ventana sigue respondiendo y bloquea un 2º guardado."""
    liberar = threading.Event()
    hilos: list[str] = []
    original = interfaz.guardar_repositorio_json

    def guardado_lento(*args: object, **kwargs: object) -> None:
        hilos.append(threading.current_thread().name)
        liberar.wait(timeout=5)
        original(*args, **kwargs)

    monkeypatch.setattr(interfaz, "guardar_repositorio_json", guardado_lento)

    ventana._on_guardar_json()
    ventana.update()  # el hilo principal sigue procesando eventos mientras tanto
    assert ventana.ocupada
    assert "⏳" in ventana.lbl_estado.cget("text")

    ventana._on_guardar_json()  # segundo intento mientras el primero sigue en curso
    assert dialogos[-1] == ("warning", "Operación en curso")

    liberar.set()
    esperar_tareas(ventana)
    assert not ventana.ocupada
    assert hilos and hilos[0].startswith("observatorio-io")
    assert hilos[0] != threading.main_thread().name


def test_interfaz_eliminar_objeto(ventana) -> None:
    """Comprueba la eliminación de un objeto personalizado desde la GUI."""
    rellenar_formulario(ventana, "OBJ-ELIMINAR", "Cometa", "30", "20")
    ventana._on_anadir_objeto()

    ventana.tabla.selection_set("OBJ-ELIMINAR")
    ventana._on_eliminar_objeto()

    assert ventana.catalogo.buscar_por_id("OBJ-ELIMINAR") is None


def test_interfaz_eliminar_identificador_numerico(ventana) -> None:
    """Un identificador con aspecto numérico ('123') se elimina sin errores."""
    rellenar_formulario(ventana, "123", "Asteroide", "30", "20")
    ventana._on_anadir_objeto()

    ventana.tabla.selection_set("123")
    ventana._on_eliminar_objeto()

    assert ventana.catalogo.buscar_por_id("123") is None


def test_interfaz_eliminar_protegido_y_sin_seleccion(ventana, dialogos) -> None:
    """No se puede borrar un objeto protegido ni pulsar Eliminar sin selección."""
    ventana._on_eliminar_objeto()
    assert dialogos[-1] == ("warning", "Aviso")

    ventana.tabla.selection_set("Sol")
    ventana._on_eliminar_objeto()
    assert dialogos[-1] == ("error", "Acción no permitida")
    assert ventana.catalogo.buscar_por_id("Sol") is not None


def test_interfaz_crear_telescopio_factory(ventana, dialogos) -> None:
    """El botón de Factory crea un telescopio y lo muestra en un diálogo."""
    ventana._on_crear_telescopio()
    assert dialogos[-1] == ("info", "Telescopio Creado")


def test_cli_gui_lanza_la_interfaz_con_la_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--gui --config X` abre la interfaz con la configuración cargada de X."""
    from observatorio.cli import main

    recibida: list[ConfiguracionObservatorio | None] = []
    monkeypatch.setattr(interfaz, "iniciar_interfaz", recibida.append)
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"factor_capacidad": 4}), encoding="utf-8")

    assert main(["--gui", "--config", str(cfg)]) == 0
    assert recibida[0] is not None and recibida[0].factor_capacidad == 4
