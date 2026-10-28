"""Pruebas unitarias del modelo de dominio, patrones de diseño y validaciones."""

from pathlib import Path

import pytest

from observatorio.cli import construir_parser
from observatorio.config import ConfiguracionObservatorio, cargar_configuracion
from observatorio.logger import configurar_logger
from observatorio.modelo import (
    CapacidadMaximaError,
    ObjetoCeleste,
    RegistroInvalidoError,
    Repositorio,
    SesionObservacion,
    Telescopio,
    TelescopioReflector,
    TelescopioRefractor,
    mostrar_resumen,
)
from observatorio.patrones import (
    AuditoriaLoggerObservador,
    CatalogoObservable,
    FabricaTelescopios,
)
from observatorio.persistencia import validar_registro_diccionario


def test_creacion_objeto_celeste_identidad_e_igualdad() -> None:
    """Verifica __eq__, __repr__ y diferencia entre identidad (is) e igualdad (==)."""
    obj1 = ObjetoCeleste("OBJ-Carlos Balbas", "Estrella", (10.5, 20.5))
    obj2 = ObjetoCeleste("OBJ-Carlos Balbas", "Estrella", (10.5, 20.5))
    obj3 = ObjetoCeleste("OBJ-Lucas Parreño", "Planeta", (50.0, -10.0))

    assert obj1 == obj2
    assert obj1 is not obj2
    assert obj1 != obj3
    assert obj1 != "no_es_un_objeto_celeste"
    assert "ObjetoCeleste(" in repr(obj1)


@pytest.mark.parametrize(
    "identificador,tipo,coordenadas",
    [
        ("", "Estrella", (10.0, 20.0)),
        ("   ", "Estrella", (10.0, 20.0)),
        ("Sirio", "", (10.0, 20.0)),
        ("Sirio", "Estrella", (-1.0, 20.0)),
        ("Sirio", "Estrella", (361.0, 20.0)),
        ("Sirio", "Estrella", (10.0, -95.0)),
        ("Sirio", "Estrella", (10.0, 95.0)),
        ("Sirio", "Estrella", (10.0,)),  # type: ignore[arg-type]
    ],
)
def test_objeto_celeste_validaciones_error(
    identificador: str, tipo: str, coordenadas: tuple[float, float]
) -> None:
    """Comprueba que ObjetoCeleste rechaza datos inválidos lanzando ValueError."""
    with pytest.raises(ValueError):
        ObjetoCeleste(identificador, tipo, coordenadas)


def test_clase_abstracta_telescopio_no_instanciable() -> None:
    """Verifica que Telescopio (ABC) no puede instanciarse directamente."""
    with pytest.raises(TypeError):
        Telescopio("Telescopio Genérico")  # type: ignore[abstract]


def test_subclases_telescopio_y_encapsulamiento() -> None:
    """Comprueba getters, setters, validaciones de tipo y polimorfismo en Telescopio."""
    refractor = TelescopioRefractor("Refractor Principal", 10, 120)
    reflector = TelescopioReflector("Reflector Sur", 20, 250)

    assert "Refractor de lentes" in refractor.descripcion_tecnica()
    assert "Reflector de espejos" in reflector.descripcion_tecnica()

    refractor.nombre = "  Refractor Modificado  "
    refractor.horas_uso = 15
    refractor.diametro_mm = 150
    assert refractor.nombre == "Refractor Modificado"
    assert refractor.horas_uso == 15
    assert refractor.diametro_mm == 150

    with pytest.raises(TypeError):
        refractor.nombre = "   "
    with pytest.raises(TypeError):
        refractor.nombre = 123  # type: ignore[assignment]
    with pytest.raises(TypeError):
        refractor.horas_uso = -5
    with pytest.raises(TypeError):
        refractor.horas_uso = 3.5  # type: ignore[assignment]
    with pytest.raises(TypeError):
        refractor.diametro_mm = 0
    with pytest.raises(TypeError):
        refractor.diametro_mm = "grande"  # type: ignore[assignment]


def test_patron_factory_telescopios() -> None:
    """Verifica la creación mediante FabricaTelescopios y el rechazo de tipos inválidos."""
    t1 = FabricaTelescopios.crear_telescopio("refractor", "T1")
    t2 = FabricaTelescopios.crear_telescopio("REFLECTOR", "T2", 5, 300)

    assert isinstance(t1, TelescopioRefractor)
    assert isinstance(t2, TelescopioReflector)
    assert t2.diametro_mm == 300

    with pytest.raises(ValueError):
        FabricaTelescopios.crear_telescopio("radiotelescopio", "T3")


def test_sesion_observacion_y_protocolo_resumible() -> None:
    """Comprueba SesionObservacion, el registro de horas y mostrar_resumen."""
    tel = TelescopioRefractor("Galileo", 2, 100)
    obj = ObjetoCeleste("Júpiter", "Planeta", (12.0, 4.0))
    sesion = SesionObservacion("2026-10-27", tel, obj)

    sesion.registrar_horas(3)
    assert tel.horas_uso == 5
    texto = mostrar_resumen(sesion)
    assert "Sesión 2026-10-27: Júpiter con Galileo" == texto

    with pytest.raises(ValueError):
        sesion.registrar_horas(0)
    with pytest.raises(ValueError):
        SesionObservacion("   ", tel, obj)


def test_catalogo_y_patron_observer(tmp_path: Path) -> None:
    """Verifica la búsqueda, el límite de capacidad y las notificaciones del Observer."""
    log_file = tmp_path / "test.log"
    logger = configurar_logger("test_obs", log_file)
    observador = AuditoriaLoggerObservador(logger)

    iniciales = [ObjetoCeleste("Sol", "Estrella", (10.0, 20.0))]
    # Con 1 objeto inicial, capacidad_maxima es 1 * 3 = 3
    catalogo = CatalogoObservable("Catálogo Pequeño", iniciales)
    catalogo.suscribir(observador)

    assert catalogo.capacidad_maxima == 3
    assert catalogo.buscar_por_id("Sol") is not None
    assert catalogo.buscar_por_id("Inexistente") is None

    catalogo.anadir(ObjetoCeleste("Luna", "Satélite", (15.0, 10.0)))
    catalogo.anadir(ObjetoCeleste("Marte", "Planeta", (25.0, -5.0)))

    with pytest.raises(CapacidadMaximaError) as exc_info:
        catalogo.anadir(ObjetoCeleste("Exceso", "Asteroide", (30.0, 30.0)))

    assert exc_info.value.capacidad_actual == 3
    assert exc_info.value.capacidad_maxima == 3
    assert len(observador.eventos_registrados) == 3  # 2 altas + 1 fallo de capacidad

    catalogo.desuscribir(observador)


def test_repositorio_generico() -> None:
    """Comprueba la clase genérica Repositorio[T]."""
    repo: Repositorio[ObjetoCeleste] = Repositorio()
    obj = ObjetoCeleste("Sirio", "Estrella", (101.2, -16.7))
    repo.agregar(obj)

    assert len(repo) == 1
    assert list(repo) == [obj]
    assert repo.obtener_todos() == [obj]


def test_validacion_regex_registros() -> None:
    """Prueba la validación de diccionarios mediante expresiones regulares."""
    reg_valido = {
        "identificador": "OBJ-Victor Llorente",
        "tipo": "Cometa",
        "coordenadas": [30.0, 45.0],
        "fecha_descubrimiento": "2025-11-03",
    }
    obj = validar_registro_diccionario(reg_valido)
    assert obj.identificador == "OBJ-Victor Llorente"

    reg_sin_fecha = {
        "identificador": "OBJ-SinFecha",
        "tipo": "Planeta",
        "coordenadas": [10.0, 20.0],
    }
    with pytest.raises(RegistroInvalidoError, match="fecha_descubrimiento"):
        validar_registro_diccionario(reg_sin_fecha)

    reg_fecha_mala = {
        "identificador": "OBJ-FechaMala",
        "tipo": "Planeta",
        "coordenadas": [10.0, 20.0],
        "fecha_descubrimiento": "2025/11/03",
    }
    with pytest.raises(RegistroInvalidoError, match="YYYY-MM-DD"):
        validar_registro_diccionario(reg_fecha_mala)


def test_configuracion_por_defecto_y_archivo(tmp_path: Path) -> None:
    """Verifica la carga de configuración desde archivo y por defecto."""
    cfg_defecto = cargar_configuracion(tmp_path / "no_existe.json")
    assert isinstance(cfg_defecto, ConfiguracionObservatorio)

    archivo_cfg = tmp_path / "custom_config.json"
    archivo_cfg.write_text(
        '{"nombre_observatorio": "Obs Test", "factor_capacidad": 4}', encoding="utf-8"
    )
    cfg_cargada = cargar_configuracion(archivo_cfg)
    assert cfg_cargada.nombre_observatorio == "Obs Test"
    assert cfg_cargada.factor_capacidad == 4


def test_parser_reconoce_argumento_gui() -> None:
    """Comprueba que argparse reconoce correctamente el modo --gui."""

    parser = construir_parser()

    args = parser.parse_args(["--gui"])

    assert args.gui is True
    assert args.demo is False
