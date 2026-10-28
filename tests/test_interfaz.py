"""Pruebas básicas de la interfaz gráfica Tkinter."""

import tkinter as tk
from pathlib import Path

import pytest

from observatorio import interfaz


@pytest.fixture
def ventana(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Crea una ventana de prueba sin mostrar cuadros de diálogo reales."""

    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        interfaz.messagebox,
        "showinfo",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        interfaz.messagebox,
        "showwarning",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        interfaz.messagebox,
        "showerror",
        lambda *args, **kwargs: None,
    )

    monkeypatch.setattr(
        interfaz.messagebox,
        "askyesno",
        lambda *args, **kwargs: True,
    )

    try:
        app = interfaz.VentanaObservatorio(ruta_json=tmp_path / "catalogo_gui.json")
    except tk.TclError:
        pytest.skip("Tkinter no está disponible en este entorno gráfico.")

    app.withdraw()

    yield app

    app.destroy()


def test_interfaz_carga_catalogo_inicial(ventana) -> None:
    """La interfaz muestra inicialmente los objetos del catálogo."""

    assert len(ventana.catalogo.objetos) == 8
    assert len(ventana.tabla.get_children()) == 8


def test_interfaz_anadir_objeto(ventana) -> None:
    """Comprueba la creación de un objeto desde el formulario."""

    ventana.txt_id.insert(0, "M31-GUI")
    ventana.txt_tipo.insert(0, "Galaxia")
    ventana.txt_ar.insert(0, "10.68")
    ventana.txt_dec.insert(0, "41.26")

    ventana._on_anadir_objeto()

    objeto = ventana.catalogo.buscar_por_id("M31-GUI")

    assert objeto is not None
    assert objeto.tipo == "Galaxia"


def test_interfaz_guardar_y_cargar_json(ventana) -> None:
    """Comprueba la persistencia JSON desde la interfaz."""

    ventana.txt_id.insert(0, "OBJ-GUI")
    ventana.txt_tipo.insert(0, "Estrella")
    ventana.txt_ar.insert(0, "20")
    ventana.txt_dec.insert(0, "30")

    ventana._on_anadir_objeto()

    ventana._on_guardar_json()

    assert ventana.ruta_json.exists()

    ventana.catalogo.objetos = []

    assert len(ventana.catalogo.objetos) == 0

    ventana._on_cargar_json()

    assert ventana.catalogo.buscar_por_id("OBJ-GUI") is not None


def test_interfaz_eliminar_objeto(ventana) -> None:
    """Comprueba la eliminación de un objeto personalizado desde la GUI."""

    ventana.txt_id.insert(0, "OBJ-ELIMINAR")
    ventana.txt_tipo.insert(0, "Cometa")
    ventana.txt_ar.insert(0, "30")
    ventana.txt_dec.insert(0, "20")

    ventana._on_anadir_objeto()

    for fila in ventana.tabla.get_children():
        valores = ventana.tabla.item(fila, "values")

        if valores[0] == "OBJ-ELIMINAR":
            ventana.tabla.selection_set(fila)
            break

    ventana._on_eliminar_objeto()

    assert ventana.catalogo.buscar_por_id("OBJ-ELIMINAR") is None
