"""Patrones de diseño aplicados al dominio del Observatorio Astronómico (Factory y Observer)."""

import logging
from typing import Protocol

from observatorio.modelo import (
    FACTOR_CAPACIDAD_POR_DEFECTO,
    CapacidadMaximaError,
    CatalogoObservatorio,
    ObjetoCeleste,
    Telescopio,
    TelescopioReflector,
    TelescopioRefractor,
)


class FabricaTelescopios:
    """Patrón Factory para instanciar subclases de Telescopio según su tipo óptico."""

    @staticmethod
    def crear_telescopio(
        tipo_optico: str,
        nombre: str,
        horas_uso: int = 0,
        diametro_mm: int | None = None,
    ) -> Telescopio:
        """Crea una instancia concreta de Telescopio.

        Args:
            tipo_optico: 'refractor' o 'reflector'.
            nombre: Nombre del telescopio.
            horas_uso: Horas iniciales de uso.
            diametro_mm: Diámetro opcional en milímetros.

        Returns:
            Instancia de TelescopioRefractor o TelescopioReflector.

        Raises:
            ValueError: Si el tipo óptico no está soportado.
        """
        tipo_norm = tipo_optico.strip().lower()
        if tipo_norm == "refractor":
            diametro = 100 if diametro_mm is None else diametro_mm
            return TelescopioRefractor(nombre, horas_uso, diametro)
        if tipo_norm == "reflector":
            diametro = 200 if diametro_mm is None else diametro_mm
            return TelescopioReflector(nombre, horas_uso, diametro)
        raise ValueError(f"Tipo de telescopio desconocido: '{tipo_optico}'")


class ObservadorCatalogo(Protocol):
    """Interfaz Observer para recibir notificaciones sobre eventos del catálogo."""

    def al_anadir_objeto(self, catalogo: CatalogoObservatorio, objeto: ObjetoCeleste) -> None:
        """Se invoca cuando un objeto celeste se registra con éxito."""
        ...

    def al_fallar_capacidad(
        self, catalogo: CatalogoObservatorio, error: CapacidadMaximaError
    ) -> None:
        """Se invoca cuando se intenta superar la capacidad máxima del catálogo."""
        ...


class AuditoriaLoggerObservador:
    """Observador concreto que registra eventos del catálogo en el sistema de logging."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self.eventos_registrados: list[str] = []

    def al_anadir_objeto(self, catalogo: CatalogoObservatorio, objeto: ObjetoCeleste) -> None:
        mensaje = (
            f"[OBSERVER] Añadido '{objeto.identificador}' ({objeto.tipo}) "
            f"al catálogo '{catalogo.nombre}' ({len(catalogo.objetos)}/{catalogo.capacidad_maxima})"
        )
        self.eventos_registrados.append(mensaje)
        self._logger.info(mensaje)

    def al_fallar_capacidad(
        self, catalogo: CatalogoObservatorio, error: CapacidadMaximaError
    ) -> None:
        mensaje = (
            f"[OBSERVER] Alerta de capacidad en '{catalogo.nombre}': {error} "
            f"({error.capacidad_actual}/{error.capacidad_maxima})"
        )
        self.eventos_registrados.append(mensaje)
        self._logger.warning(mensaje)


class CatalogoObservable(CatalogoObservatorio):
    """Extensión de CatalogoObservatorio que implementa el sujeto del patrón Observer."""

    def __init__(
        self,
        nombre: str,
        objetos_iniciales: list[ObjetoCeleste] | None = None,
        factor_capacidad: int = FACTOR_CAPACIDAD_POR_DEFECTO,
    ) -> None:
        super().__init__(nombre, objetos_iniciales, factor_capacidad)
        self._observadores: list[ObservadorCatalogo] = []

    def suscribir(self, observador: ObservadorCatalogo) -> None:
        """Registra un nuevo observador."""
        if observador not in self._observadores:
            self._observadores.append(observador)

    def desuscribir(self, observador: ObservadorCatalogo) -> None:
        """Elimina un observador previamente registrado."""
        if observador in self._observadores:
            self._observadores.remove(observador)

    def anadir(self, objeto: ObjetoCeleste) -> None:
        """Añade un objeto al catálogo y notifica a todos los observadores suscritos."""
        try:
            super().anadir(objeto)
        except CapacidadMaximaError as error:
            for obs in self._observadores:
                obs.al_fallar_capacidad(self, error)
            raise
        else:
            for obs in self._observadores:
                obs.al_anadir_objeto(self, objeto)
