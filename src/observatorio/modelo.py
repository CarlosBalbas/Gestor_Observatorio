"""Módulo de dominio principal del Gestor de Observatorio Astronómico."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from types import NotImplementedType
from typing import Generic, Protocol, TypeVar


class Resumible(Protocol):
    """Protocolo estructural (Duck Typing) para entidades que generan un resumen textual."""

    def resumen(self) -> str:
        """Devuelve una cadena descriptiva con el resumen del objeto."""
        ...


class CapacidadMaximaError(Exception):
    """Excepción lanzada cuando el catálogo alcanza su límite de capacidad."""

    def __init__(self, mensaje: str, capacidad_actual: int, capacidad_maxima: int) -> None:
        super().__init__(mensaje)
        self.capacidad_actual = capacidad_actual
        self.capacidad_maxima = capacidad_maxima


class RegistroInvalidoError(Exception):
    """Excepción lanzada cuando un registro de entrada no cumple los criterios de validación."""


class ObjetoDuplicadoError(ValueError):
    """Excepción lanzada al registrar un identificador que ya existe en el catálogo.

    Hereda de ValueError porque es un valor de entrada no válido para el catálogo.
    """


class PersistenciaError(Exception):
    """Excepción lanzada cuando ocurre un fallo de lectura o escritura en almacenamiento."""


OBJETOS_PROTEGIDOS: frozenset[str] = frozenset(
    {"Sol", "Luna", "Sirio", "Júpiter", "Saturno", "Neptuno", "M45", "Pluton"}
)
"""Identificadores del catálogo de referencia que no se pueden eliminar."""

FACTOR_CAPACIDAD_POR_DEFECTO = 3
"""Multiplicador aplicado al número de objetos iniciales para fijar la capacidad máxima."""


class ObjetoCeleste:
    """Representa un cuerpo o fenómeno astronómico observado con coordenadas ecuatoriales."""

    def __init__(self, identificador: str, tipo: str, coordenadas: tuple[float, float]) -> None:
        """Inicializa un objeto celeste validando su identificador, tipo y coordenadas.

        Args:
            identificador: Nombre o código único del objeto celeste.
            tipo: Categoría astronómica (Estrella, Planeta, Galaxia, etc.).
            coordenadas: Tupla (ascensión_recta, declinación) en grados.

        Raises:
            TypeError: Si el identificador o el tipo no son cadenas de texto.
            ValueError: Si los textos están vacíos o las coordenadas están fuera de rango.
        """
        if not isinstance(identificador, str) or not isinstance(tipo, str):
            raise TypeError("El identificador y el tipo tienen que ser cadenas de texto")
        if not identificador.strip() or not tipo.strip():
            raise ValueError("El identificador y el tipo NO pueden estar vacíos")
        if len(coordenadas) != 2:
            raise ValueError("Se necesitan exactamente 2 coordenadas, AR y declinación")
        ar, dec = (float(valor) for valor in coordenadas)
        if ar < 0 or ar > 360 or dec < -90 or dec > 90:
            raise ValueError("Coordenadas fuera de rango")

        self._identificador = identificador.strip()
        self._tipo = tipo.strip()
        self.__coordenadas = (ar, dec)

    @property
    def identificador(self) -> str:
        """Devuelve el identificador único del objeto celeste."""
        return self._identificador

    @property
    def tipo(self) -> str:
        """Devuelve el tipo astronómico del objeto celeste."""
        return self._tipo

    @property
    def coordenadas(self) -> tuple[float, float]:
        """Devuelve la tupla (AR, DEC) del objeto celeste."""
        return self.__coordenadas

    def a_diccionario(self) -> dict[str, object]:
        """Serializa la instancia a un diccionario compatible con JSON."""
        return {
            "identificador": self.identificador,
            "tipo": self.tipo,
            "coordenadas": list(self.coordenadas),
        }

    @classmethod
    def desde_diccionario(cls, datos: dict[str, object]) -> "ObjetoCeleste":
        """Reconstruye un ObjetoCeleste a partir de un diccionario."""
        coords_raw = datos.get("coordenadas")
        if not isinstance(coords_raw, (list, tuple)) or len(coords_raw) != 2:
            raise ValueError("Formato de coordenadas inválido en diccionario")
        coord = (float(coords_raw[0]), float(coords_raw[1]))
        return cls(str(datos["identificador"]), str(datos["tipo"]), coord)

    def __repr__(self) -> str:
        return f"ObjetoCeleste({self.identificador!r}, {self.tipo!r}, {self.coordenadas!r})"

    def __eq__(self, otro: object) -> bool | NotImplementedType:
        if not isinstance(otro, ObjetoCeleste):
            return NotImplemented
        return (self.identificador, self.tipo, self.coordenadas) == (
            otro.identificador,
            otro.tipo,
            otro.coordenadas,
        )

    def __hash__(self) -> int:
        """Hash coherente con __eq__: los atributos comparados son de solo lectura."""
        return hash((self.identificador, self.tipo, self.coordenadas))


class Telescopio(ABC):
    """Clase base abstracta que modela un telescopio del observatorio."""

    UNIDAD_HORAS = "h"

    def __init__(self, nombre: str, horas_uso: int = 0, diametro_mm: int = 100) -> None:
        self.nombre = nombre
        self.horas_uso = horas_uso
        self.diametro_mm = diametro_mm

    @abstractmethod
    def descripcion_tecnica(self) -> str:
        """Devuelve los detalles ópticos específicos del telescopio."""

    @property
    def nombre(self) -> str:
        """Nombre identificativo del telescopio."""
        return self.__nombre

    @nombre.setter
    def nombre(self, nuevo_valor: str) -> None:
        if not isinstance(nuevo_valor, str):
            raise TypeError("El nombre tiene que ser un string")
        if not nuevo_valor.strip():
            raise ValueError("El nombre del telescopio no puede estar vacío")
        self.__nombre = nuevo_valor.strip()

    @property
    def horas_uso(self) -> int:
        """Horas acumuladas de uso del telescopio."""
        return self.__horas_uso

    @horas_uso.setter
    def horas_uso(self, nuevo_valor: int) -> None:
        if type(nuevo_valor) is not int:
            raise TypeError("Las horas de uso tienen que ser un int")
        if nuevo_valor < 0:
            raise ValueError("Las horas de uso tienen que ser mayor o igual a 0")
        self.__horas_uso = nuevo_valor

    @property
    def diametro_mm(self) -> int:
        """Diámetro de apertura en milímetros."""
        return self.__diametro_mm

    @diametro_mm.setter
    def diametro_mm(self, nuevo_valor: int) -> None:
        if type(nuevo_valor) is not int:
            raise TypeError("El diámetro tiene que ser un int")
        if nuevo_valor <= 0:
            raise ValueError("El diámetro tiene que ser mayor a 0")
        self.__diametro_mm = nuevo_valor


class TelescopioRefractor(Telescopio):
    """Telescopio dióptrico basado en un sistema de lentes."""

    def __init__(self, nombre: str, horas_uso: int = 0, diametro_mm: int = 100) -> None:
        super().__init__(nombre, horas_uso, diametro_mm)

    def descripcion_tecnica(self) -> str:
        return f" {self.nombre} (Refractor de lentes), diámetro: {self.diametro_mm} mm"


class TelescopioReflector(Telescopio):
    """Telescopio catóptrico basado en un sistema de espejos."""

    def __init__(self, nombre: str, horas_uso: int = 0, diametro_mm: int = 200) -> None:
        super().__init__(nombre, horas_uso, diametro_mm)

    def descripcion_tecnica(self) -> str:
        return f" {self.nombre} (Reflector de espejos), diámetro: {self.diametro_mm} mm"


class SesionObservacion:
    """Vincula un telescopio y un objeto celeste en una fecha de observación determinada."""

    def __init__(self, fecha: str, telescopio: Telescopio, objetivo: ObjetoCeleste) -> None:
        if not fecha.strip():
            raise ValueError("La fecha no puede estar vacía")
        self.fecha = fecha.strip()
        self.telescopio = telescopio
        self.objetivo = objetivo

    def registrar_horas(self, horas: int) -> None:
        """Incrementa las horas de uso del telescopio asociado a la sesión."""
        if horas <= 0:
            raise ValueError("Las horas a registrar deben ser positivas")
        self.telescopio.horas_uso += horas

    def resumen(self) -> str:
        """Genera un resumen textual de la sesión (cumple el protocolo Resumible)."""
        return (
            f"Sesión {self.fecha}: {self.objetivo.identificador} con " f"{self.telescopio.nombre}"
        )


def _comprobar_identificadores_unicos(objetos: list[ObjetoCeleste]) -> None:
    """Lanza ObjetoDuplicadoError si algún identificador aparece más de una vez."""
    vistos: set[str] = set()
    for obj in objetos:
        if obj.identificador in vistos:
            raise ObjetoDuplicadoError(f"Identificador repetido: '{obj.identificador}'.")
        vistos.add(obj.identificador)


class CatalogoObservatorio:
    """Agrupa una colección de objetos celestes bajo una capacidad máxima controlada."""

    def __init__(
        self,
        nombre: str,
        objetos_iniciales: list[ObjetoCeleste] | None = None,
        factor_capacidad: int = FACTOR_CAPACIDAD_POR_DEFECTO,
    ) -> None:
        """Crea el catálogo y fija su capacidad máxima.

        Args:
            nombre: Nombre del catálogo.
            objetos_iniciales: Objetos con los que arranca (se copia la lista).
            factor_capacidad: La capacidad máxima es nº de objetos iniciales x factor
                (con 8 como base si el catálogo empieza vacío).

        Raises:
            ValueError: Si el nombre está vacío o el factor no es un entero positivo.
            ObjetoDuplicadoError: Si los objetos iniciales repiten identificador.
        """
        if not nombre.strip():
            raise ValueError("El nombre del catálogo no puede estar vacío")
        if type(factor_capacidad) is not int or factor_capacidad < 1:
            raise ValueError("El factor de capacidad tiene que ser un entero positivo")
        self.nombre = nombre.strip()
        self.objetos: list[ObjetoCeleste] = (
            [] if objetos_iniciales is None else list(objetos_iniciales)
        )
        _comprobar_identificadores_unicos(self.objetos)
        base = len(self.objetos) if len(self.objetos) > 0 else 8
        self.__capacidad_maxima = base * factor_capacidad

    @property
    def capacidad_maxima(self) -> int:
        """Capacidad máxima permitida en el catálogo."""
        return self.__capacidad_maxima

    def anadir(self, objeto: ObjetoCeleste) -> None:
        """Añade un objeto celeste verificando capacidad e identificador único.

        Raises:
            CapacidadMaximaError: Si el catálogo está lleno.
            ObjetoDuplicadoError: Si ya existe un objeto con el mismo identificador.
        """
        if len(self.objetos) >= self.capacidad_maxima:
            raise CapacidadMaximaError(
                f"No se puede registrar '{objeto.identificador}'. Capacidad máxima alcanzada.",
                len(self.objetos),
                self.capacidad_maxima,
            )
        if self.buscar_por_id(objeto.identificador) is not None:
            raise ObjetoDuplicadoError(
                f"Ya existe un objeto con identificador '{objeto.identificador}'."
            )
        self.objetos.append(objeto)

    def reemplazar_objetos(self, nuevos: list[ObjetoCeleste]) -> None:
        """Sustituye el contenido del catálogo pasando cada objeto por anadir().

        Comprueba la capacidad antes de tocar nada, de modo que si los datos no caben
        el catálogo queda intacto. Al usar anadir(), las subclases (por ejemplo
        CatalogoObservable) siguen notificando cada alta.

        Raises:
            CapacidadMaximaError: Si los nuevos objetos superan la capacidad máxima.
            ObjetoDuplicadoError: Si hay identificadores repetidos en los nuevos objetos.
        """
        nuevos = list(nuevos)
        _comprobar_identificadores_unicos(nuevos)
        if len(nuevos) > self.capacidad_maxima:
            raise CapacidadMaximaError(
                f"No se pueden cargar {len(nuevos)} objetos. Capacidad máxima: "
                f"{self.capacidad_maxima}.",
                len(nuevos),
                self.capacidad_maxima,
            )
        self.objetos = []
        for objeto in nuevos:
            self.anadir(objeto)

    def buscar_por_id(self, identificador: str) -> ObjetoCeleste | None:
        """Busca un objeto celeste por su identificador exacto."""
        for obj in self.objetos:
            if obj.identificador == identificador:
                return obj
        return None

    def resumen(self) -> str:
        """Genera un resumen del estado del catálogo (cumple el protocolo Resumible)."""
        return (
            f"Catálogo '{self.nombre}' con {len(self.objetos)}/{self.capacidad_maxima} "
            f"objetos registrados"
        )

    def eliminar(self, identificador: str) -> bool:
        """Elimina un objeto del catálogo buscando por su identificador.

        Args:
            identificador: Nombre o código único del objeto a eliminar.

        Returns:
            True si se ha eliminado con éxito, False si no existía.

        Raises:
            ValueError: Si el objeto pertenece a OBJETOS_PROTEGIDOS.
        """
        ident_limpio = identificador.strip()
        if ident_limpio in OBJETOS_PROTEGIDOS:
            raise ValueError(
                f"No se puede eliminar '{ident_limpio}' por ser un objeto celeste "
                "de referencia protegido."
            )

        for obj in self.objetos:
            if obj.identificador == ident_limpio:
                self.objetos.remove(obj)
                return True
        return False


def crear_catalogo_ejemplo(
    factor_capacidad: int = FACTOR_CAPACIDAD_POR_DEFECTO,
) -> CatalogoObservatorio:
    """Construye el catálogo de ejemplo de 8 objetos astronómicos."""
    elementos = [
        ObjetoCeleste("Sol", "Estrella", (10.68, 41.27)),
        ObjetoCeleste("Luna", "Luna", (83.82, -5.39)),
        ObjetoCeleste("Sirio", "Estrella", (101.29, -16.72)),
        ObjetoCeleste("Júpiter", "Planeta", (0.0, 0.0)),
        ObjetoCeleste("Saturno", "Planeta", (1.0, 1.0)),
        ObjetoCeleste("Neptuno", "Planeta", (83.63, 22.01)),
        ObjetoCeleste("M45", "Cúmulo", (56.75, 24.12)),
        ObjetoCeleste("Pluton", "Planeta", (88.79, 7.41)),
    ]
    return CatalogoObservatorio("Test Catalogo", elementos, factor_capacidad)


def mostrar_resumen(elemento: Resumible) -> str:
    """Imprime y devuelve el resumen polimórfico de cualquier entidad Resumible."""
    texto = elemento.resumen()
    print(texto)
    return texto


T = TypeVar("T")


class Repositorio(Generic[T]):
    """Estructura genérica tipada para almacenar colecciones de elementos en memoria."""

    def __init__(self) -> None:
        self._elementos: list[T] = []

    def agregar(self, item: T) -> None:
        """Añade un ítem de tipo T al repositorio."""
        self._elementos.append(item)

    def obtener_todos(self) -> list[T]:
        """Devuelve una copia superficial de todos los elementos almacenados."""
        return list(self._elementos)

    def __len__(self) -> int:
        return len(self._elementos)

    def __iter__(self) -> Iterator[T]:
        return iter(self._elementos)
