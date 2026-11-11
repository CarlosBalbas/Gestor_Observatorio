"""Interfaz gráfica de usuario (GUI) basada en Tkinter para el Gestor del Observatorio.

Concurrencia: las operaciones de disco (guardar/cargar JSON y exportar a SQLite) se
ejecutan en un hilo de trabajo (ThreadPoolExecutor con un único hilo) para que la
ventana no se congele. Tkinter NO es seguro entre hilos, así que el hilo de trabajo
nunca toca widgets ni el catálogo: recibe una copia de los datos, devuelve un resultado
y el hilo principal lo recoge sondeando el Future con ``after()``.
"""

import tkinter as tk
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

from observatorio import __version__
from observatorio.config import ConfiguracionObservatorio
from observatorio.logger import configurar_logger
from observatorio.modelo import (
    OBJETOS_PROTEGIDOS,
    CapacidadMaximaError,
    ObjetoCeleste,
    PersistenciaError,
    Repositorio,
    crear_catalogo_ejemplo,
)
from observatorio.patrones import (
    AuditoriaLoggerObservador,
    CatalogoObservable,
    FabricaTelescopios,
)
from observatorio.persistencia import (
    GestorSQLiteObservatorio,
    cargar_repositorio_json,
    guardar_repositorio_json,
)


def _repositorio_desde(objetos: list[ObjetoCeleste]) -> Repositorio[ObjetoCeleste]:
    """Construye un Repositorio a partir de una lista de objetos."""
    repo: Repositorio[ObjetoCeleste] = Repositorio()
    for obj in objetos:
        repo.agregar(obj)
    return repo


class VentanaObservatorio(tk.Tk):
    """Ventana principal de la interfaz gráfica del Observatorio Astronómico."""

    INTERVALO_SONDEO_MS = 50
    """Cada cuánto comprueba el hilo principal si ha terminado la tarea en segundo plano."""

    def __init__(
        self,
        ruta_json: str | Path = "objetos_interfaz.json",
        config: ConfiguracionObservatorio | None = None,
    ) -> None:
        """Crea la ventana, el catálogo observable y el hilo de trabajo para la E/S.

        Args:
            ruta_json: Fichero JSON que usan los botones Guardar/Cargar JSON.
            config: Configuración de la aplicación (capacidad, ruta SQLite, log).
        """
        super().__init__()
        self.config_app = config if config is not None else ConfiguracionObservatorio()
        self.title(f"Gestor de Observatorio Astronómico (v{__version__})")
        self.geometry("1150x620")
        self.minsize(1100, 520)

        self.ruta_json = Path(ruta_json)
        self.ruta_sqlite = Path(self.config_app.ruta_sqlite)
        self.logger = configurar_logger(
            "observatorio_gui", "observatorio_gui.log", self.config_app.nivel_log
        )

        # Concurrencia: un único hilo de trabajo serializa las operaciones de disco.
        self._ejecutor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="observatorio-io")
        self._tarea_actual: Future[Any] | None = None
        self._id_sondeo: str | None = None
        self._botones_es: list[ttk.Button] = []

        # Inicializar dominio y patrones
        factor = self.config_app.factor_capacidad
        catalogo_base = crear_catalogo_ejemplo(factor)
        self.catalogo = CatalogoObservable(catalogo_base.nombre, catalogo_base.objetos, factor)
        self.observador = AuditoriaLoggerObservador(self.logger)
        self.catalogo.suscribir(self.observador)

        self._construir_interfaz()
        self._actualizar_tabla()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _construir_interfaz(self) -> None:
        """Construye los componentes visuales de la ventana."""
        estilo = ttk.Style()
        estilo.theme_use("clam")

        # Contenedor superior (Título y Estado)
        frame_superior = ttk.Frame(self, padding=10)
        frame_superior.pack(fill=tk.X, side=tk.TOP)

        lbl_titulo = ttk.Label(
            frame_superior,
            text="🔭 Gestor de Observatorio Astronómico Nebrija",
            font=("Calibri", 14, "bold"),
        )
        lbl_titulo.pack(side=tk.LEFT)

        self.lbl_estado = ttk.Label(
            frame_superior, text="", font=("Calibri", 10, "italic"), foreground="#235284"
        )
        self.lbl_estado.pack(side=tk.RIGHT)

        # Contenedor central (Tabla de Objetos Celestes)
        frame_centro = ttk.Frame(self, padding=10)
        frame_centro.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

        columnas = ("identificador", "tipo", "ar", "dec")
        self.tabla = ttk.Treeview(
            frame_centro, columns=columnas, show="headings", selectmode="browse"
        )

        self.tabla.heading("identificador", text="Identificador / Nombre")
        self.tabla.heading("tipo", text="Tipo Astronómico")
        self.tabla.heading("ar", text="Ascensión Recta (º)")
        self.tabla.heading("dec", text="Declinación (º)")

        self.tabla.column("identificador", width=250, anchor=tk.W)
        self.tabla.column("tipo", width=150, anchor=tk.W)
        self.tabla.column("ar", width=120, anchor=tk.CENTER)
        self.tabla.column("dec", width=120, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(frame_centro, orient=tk.VERTICAL, command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=scrollbar.set)

        self.tabla.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Contenedor inferior (Formulario de alta y Botones de acción)
        frame_inferior = ttk.LabelFrame(
            self, text=" Gestión y Control del Observatorio ", padding=15
        )
        frame_inferior.pack(fill=tk.X, padx=10, pady=10, side=tk.BOTTOM)

        # Fila 1 del formulario: Añadir Objeto Celeste
        lbl_id = ttk.Label(frame_inferior, text="Identificador:")
        lbl_id.grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.txt_id = ttk.Entry(frame_inferior, width=20)
        self.txt_id.grid(row=0, column=1, padx=5, pady=5)

        lbl_tipo = ttk.Label(frame_inferior, text="Tipo:")
        lbl_tipo.grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.txt_tipo = ttk.Entry(frame_inferior, width=18)
        self.txt_tipo.grid(row=0, column=3, padx=5, pady=5)

        lbl_ar = ttk.Label(frame_inferior, text="AR (0-360):")
        lbl_ar.grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)
        self.txt_ar = ttk.Entry(frame_inferior, width=10)
        self.txt_ar.grid(row=0, column=5, padx=5, pady=5)

        lbl_dec = ttk.Label(frame_inferior, text="DEC (-90-90):")
        lbl_dec.grid(row=0, column=6, sticky=tk.W, padx=5, pady=5)
        self.txt_dec = ttk.Entry(frame_inferior, width=10)
        self.txt_dec.grid(row=0, column=7, padx=5, pady=5)

        btn_anadir = ttk.Button(
            frame_inferior, text="Añadir Objeto", command=self._on_anadir_objeto
        )
        btn_anadir.grid(row=0, column=8, padx=10, pady=5)

        # Fila 2: Botones de utilidades
        frame_botones = ttk.Frame(frame_inferior)
        frame_botones.grid(row=1, column=0, columnspan=9, pady=10)

        acciones: list[tuple[str, Callable[[], None], bool]] = [
            ("Crear Telescopio (Factory)", self._on_crear_telescopio, False),
            ("Guardar JSON", self._on_guardar_json, True),
            ("Cargar JSON", self._on_cargar_json, True),
            ("Exportar SQLite", self._on_exportar_sqlite, True),
            ("Refrescar Tabla", self._actualizar_tabla, False),
            ("Eliminar Seleccionado", self._on_eliminar_objeto, False),
        ]
        for texto, comando, es_entrada_salida in acciones:
            boton = ttk.Button(frame_botones, text=texto, command=comando)
            boton.pack(side=tk.LEFT, padx=5)
            if es_entrada_salida:
                self._botones_es.append(boton)

    # ------------------------------------------------------------------ concurrencia

    @property
    def ocupada(self) -> bool:
        """Indica si hay una operación de disco en curso en el hilo de trabajo."""
        return self._tarea_actual is not None

    def _ejecutar_en_segundo_plano(
        self,
        descripcion: str,
        tarea: Callable[[], Any],
        al_terminar: Callable[[Any], None],
    ) -> None:
        """Lanza ``tarea`` en el hilo de trabajo y llama a ``al_terminar`` en el principal.

        Args:
            descripcion: Texto que se muestra en la barra de estado mientras dura.
            tarea: Función sin argumentos que se ejecuta fuera del hilo de Tkinter.
                No debe tocar widgets ni el catálogo.
            al_terminar: Recibe el resultado de ``tarea``; se ejecuta en el hilo principal.
        """
        if self.ocupada:
            messagebox.showwarning("Operación en curso", "Espera a que termine la anterior.")
            return
        self._fijar_ocupada(True, descripcion)
        self._tarea_actual = self._ejecutor.submit(tarea)
        self._id_sondeo = self.after(self.INTERVALO_SONDEO_MS, self._comprobar_tarea, al_terminar)

    def _comprobar_tarea(self, al_terminar: Callable[[Any], None]) -> None:
        """Sondea el Future desde el hilo principal y entrega el resultado al terminar."""
        tarea = self._tarea_actual
        if tarea is None:
            return
        if not tarea.done():
            self._id_sondeo = self.after(
                self.INTERVALO_SONDEO_MS, self._comprobar_tarea, al_terminar
            )
            return
        self._tarea_actual = None
        self._id_sondeo = None
        self._fijar_ocupada(False)
        try:
            resultado = tarea.result()
        except PersistenciaError as error:
            messagebox.showerror("Error de Persistencia", str(error))
            return
        al_terminar(resultado)

    def _fijar_ocupada(self, ocupada: bool, descripcion: str = "") -> None:
        """Activa o desactiva los botones de E/S y actualiza la barra de estado."""
        estado = ["disabled"] if ocupada else ["!disabled"]
        for boton in self._botones_es:
            boton.state(estado)
        if ocupada:
            self.lbl_estado.config(text=f"⏳ {descripcion}...")
            self.config(cursor="watch")
        else:
            self.config(cursor="")
            self._actualizar_tabla()

    def destroy(self) -> None:
        """Cancela el sondeo pendiente y espera al hilo de trabajo antes de cerrar."""
        if self._id_sondeo is not None:
            self.after_cancel(self._id_sondeo)
            self._id_sondeo = None
        self._ejecutor.shutdown(wait=True, cancel_futures=True)
        super().destroy()

    # ------------------------------------------------------------------ tabla

    def _actualizar_tabla(self) -> None:
        """Actualiza el contenido visual de la tabla y la etiqueta de capacidad."""
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)

        for obj in self.catalogo.objetos:
            ar, dec = obj.coordenadas
            # El identificador es único en el catálogo: se usa como iid de la fila.
            self.tabla.insert(
                "",
                tk.END,
                iid=obj.identificador,
                values=(obj.identificador, obj.tipo, f"{ar:.2f}", f"{dec:.2f}"),
            )

        self.lbl_estado.config(
            text=f"Catálogo: {len(self.catalogo.objetos)} / {self.catalogo.capacidad_maxima} objetos"
        )

    # ------------------------------------------------------------------ acciones

    def _on_anadir_objeto(self) -> None:
        """Controlador para añadir un objeto recogiendo los datos del formulario."""
        ident = self.txt_id.get().strip()
        tipo_astro = self.txt_tipo.get().strip()
        ar_str = self.txt_ar.get().strip()
        dec_str = self.txt_dec.get().strip()

        if not ident or not tipo_astro or not ar_str or not dec_str:
            messagebox.showerror(
                "Error de validación", "Todos los campos del formulario son obligatorios."
            )
            return

        try:
            ar = float(ar_str.replace(",", "."))
            dec = float(dec_str.replace(",", "."))
            nuevo_obj = ObjetoCeleste(ident, tipo_astro, (ar, dec))
            self.catalogo.anadir(nuevo_obj)
        except CapacidadMaximaError as e:
            messagebox.showwarning("Capacidad Máxima", str(e))
            return
        except ValueError as e:
            # Incluye ObjetoDuplicadoError y los float() mal escritos.
            messagebox.showerror("Error de Formato / Rango", str(e))
            return

        self._actualizar_tabla()
        messagebox.showinfo("Éxito", f"Objeto '{ident}' añadido correctamente al catálogo.")
        for campo in (self.txt_id, self.txt_tipo, self.txt_ar, self.txt_dec):
            campo.delete(0, tk.END)

    def _on_crear_telescopio(self) -> None:
        """Demuestra el uso del patrón Factory Method mediante un diálogo gráfico."""
        tipo_optico = messagebox.askquestion(
            "Patrón Factory",
            "¿Qué tipo de telescopio deseas crear?\n\n"
            "- Sí: Refractor (Lentes)\n- No: Reflector (Espejos)",
            icon=messagebox.QUESTION,
        )
        tipo_str = "refractor" if tipo_optico == "yes" else "reflector"
        telescopio = FabricaTelescopios.crear_telescopio(tipo_str, "Telescopio GUI")
        messagebox.showinfo(
            "Telescopio Creado",
            f"Instanciado mediante Factory:\n\n{telescopio.descripcion_tecnica()}",
        )

    def _on_guardar_json(self) -> None:
        """Guarda el catálogo en JSON en segundo plano."""
        # Copia hecha en el hilo principal: el hilo de trabajo no lee self.catalogo.
        # Basta una copia superficial porque ObjetoCeleste es inmutable.
        instantanea = list(self.catalogo.objetos)
        ruta = self.ruta_json

        def tarea() -> int:
            guardar_repositorio_json(_repositorio_desde(instantanea), ruta, self.logger)
            return len(instantanea)

        def al_terminar(total: int) -> None:
            messagebox.showinfo("Persistencia", f"{total} objetos guardados en '{ruta}'.")

        self._ejecutar_en_segundo_plano("Guardando JSON", tarea, al_terminar)

    def _on_cargar_json(self) -> None:
        """Lee el JSON en segundo plano y aplica el resultado al catálogo en el principal."""
        ruta = self.ruta_json
        if not ruta.exists():
            messagebox.showwarning("Aviso", f"No existe el archivo '{ruta}' para cargar.")
            return

        def tarea() -> list[ObjetoCeleste]:
            return cargar_repositorio_json(ruta, self.logger).obtener_todos()

        def al_terminar(objetos: list[ObjetoCeleste]) -> None:
            # Se pasa por el dominio: respeta capacidad y unicidad y notifica al Observer.
            try:
                self.catalogo.reemplazar_objetos(objetos)
            except CapacidadMaximaError as e:
                messagebox.showwarning("Capacidad Máxima", str(e))
                return
            except ValueError as e:
                messagebox.showerror("Error de Carga", str(e))
                return
            self._actualizar_tabla()
            messagebox.showinfo("Persistencia", f"Cargados {len(objetos)} objetos desde '{ruta}'.")

        self._ejecutar_en_segundo_plano("Cargando JSON", tarea, al_terminar)

    def _on_exportar_sqlite(self) -> None:
        """Exporta el catálogo a SQLite en segundo plano (una sola transacción)."""
        instantanea = list(self.catalogo.objetos)
        ruta = self.ruta_sqlite

        def tarea() -> int:
            # La conexión se crea, usa y cierra dentro del hilo de trabajo.
            return GestorSQLiteObservatorio(ruta).guardar_repositorio(
                _repositorio_desde(instantanea)
            )

        def al_terminar(total: int) -> None:
            self.logger.info("GUI: %d objetos exportados a SQLite '%s'.", total, ruta)
            messagebox.showinfo("SQLite", f"{total} objetos exportados a '{ruta}'.")

        self._ejecutar_en_segundo_plano("Exportando a SQLite", tarea, al_terminar)

    def _on_eliminar_objeto(self) -> None:
        """Elimina el objeto celeste seleccionado controlando los elementos protegidos."""
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showwarning(
                "Aviso", "Por favor, selecciona un objeto de la tabla para eliminar."
            )
            return

        # El iid es el identificador como str (los valores de la fila pueden llegar
        # convertidos a int por Tcl si el identificador parece un número).
        identificador_a_borrar = str(seleccion[0])

        if identificador_a_borrar in OBJETOS_PROTEGIDOS:
            messagebox.showerror(
                "Acción no permitida",
                f"El objeto '{identificador_a_borrar}' forma parte de los cuerpos celestes "
                "base del observatorio y NO se puede eliminar.",
            )
            return

        confirmar = messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Estás seguro de que deseas eliminar el objeto '{identificador_a_borrar}'?",
        )
        if not confirmar:
            return

        try:
            exito = self.catalogo.eliminar(identificador_a_borrar)
        except ValueError as e:
            messagebox.showerror("Error de Dominio", str(e))
            return
        if exito:
            self._actualizar_tabla()
            self.logger.info(
                "Objeto '%s' eliminado desde la interfaz gráfica.", identificador_a_borrar
            )
            messagebox.showinfo(
                "Éxito", f"Objeto '{identificador_a_borrar}' eliminado correctamente."
            )


def iniciar_interfaz(config: ConfiguracionObservatorio | None = None) -> None:
    """Función de lanzamiento de la GUI."""
    app = VentanaObservatorio(config=config)
    app.mainloop()


if __name__ == "__main__":
    iniciar_interfaz()
