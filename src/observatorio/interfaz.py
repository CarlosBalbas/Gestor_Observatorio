"""Interfaz gráfica de usuario (GUI) basada en Tkinter para el Gestor del Observatorio."""

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from observatorio.logger import configurar_logger
from observatorio.modelo import (
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
    cargar_repositorio_json,
    guardar_repositorio_json,
)


class VentanaObservatorio(tk.Tk):
    """Ventana principal de la interfaz gráfica del Observatorio Astronómico."""

    def __init__(self, ruta_json: str | Path = "objetos_interfaz.json") -> None:
        super().__init__()
        self.title("Gestor de Observatorio Astronómico (v1.0.0)")
        self.geometry("850x600")
        self.minsize(700, 500)

        self.ruta_json = Path(ruta_json)
        self.logger = configurar_logger("observatorio_gui", "observatorio_gui.log")

        # Inicializar dominio y patrones
        catalogo_base = crear_catalogo_ejemplo()
        self.catalogo = CatalogoObservable(catalogo_base.nombre, catalogo_base.objetos)
        self.observador = AuditoriaLoggerObservador(self.logger)
        self.catalogo.suscribir(self.observador)

        self._construir_interfaz()
        self._actualizar_tabla()

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

        btn_factory = ttk.Button(
            frame_botones, text="Crear Telescopio (Factory)", command=self._on_crear_telescopio
        )
        btn_factory.pack(side=tk.LEFT, padx=5)

        btn_guardar = ttk.Button(frame_botones, text="Guardar JSON", command=self._on_guardar_json)
        btn_guardar.pack(side=tk.LEFT, padx=5)

        btn_cargar = ttk.Button(frame_botones, text="Cargar JSON", command=self._on_cargar_json)
        btn_cargar.pack(side=tk.LEFT, padx=5)

        btn_limpiar = ttk.Button(
            frame_botones, text="Refrescar Tabla", command=self._actualizar_tabla
        )
        btn_limpiar.pack(side=tk.LEFT, padx=5)

        btn_eliminar = ttk.Button(
            frame_botones, text="Eliminar Seleccionado", command=self._on_eliminar_objeto
        )
        btn_eliminar.pack(side=tk.LEFT, padx=5)

    def _actualizar_tabla(self) -> None:
        """Actualiza el contenido visual de la tabla y la etiqueta de capacidad."""
        for fila in self.tabla.get_children():
            self.tabla.delete(fila)

        for obj in self.catalogo.objetos:
            ar, dec = obj.coordenadas
            self.tabla.insert(
                "", tk.END, values=(obj.identificador, obj.tipo, f"{ar:.2f}", f"{dec:.2f}")
            )

        self.lbl_estado.config(
            text=f"Catálogo: {len(self.catalogo.objetos)} / {self.catalogo.capacidad_maxima} objetos"
        )

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
            ar = float(ar_str)
            dec = float(dec_str)
            nuevo_obj = ObjetoCeleste(ident, tipo_astro, (ar, dec))
            self.catalogo.anadir(nuevo_obj)
            self._actualizar_tabla()
            messagebox.showinfo("Éxito", f"Objeto '{ident}' añadido correctamente al catálogo.")
            self.txt_id.delete(0, tk.END)
            self.txt_tipo.delete(0, tk.END)
            self.txt_ar.delete(0, tk.END)
            self.txt_dec.delete(0, tk.END)
        except ValueError as e:
            messagebox.showerror("Error de Formato / Rango", str(e))
        except CapacidadMaximaError as e:
            messagebox.showwarning("Capacidad Máxima", str(e))

    def _on_crear_telescopio(self) -> None:
        """Demuestra el uso del patrón Factory Method mediante un diálogo gráfico."""
        tipo_optico = messagebox.askquestion(
            "Patrón Factory",
            "¿Qué tipo de telescopio deseas crear?\n\n- Sí: Refractor (Lentes)\n- No: Reflector (Espejos)",
            icon=messagebox.QUESTION,
        )
        tipo_str = "refractor" if tipo_optico == "yes" else "reflector"
        telescopio = FabricaTelescopios.crear_telescopio(tipo_str, "Telescopio GUI")
        messagebox.showinfo(
            "Telescopio Creado",
            f"Instanciado mediante Factory:\n\n{telescopio.descripcion_tecnica()}",
        )

    def _on_guardar_json(self) -> None:
        """Guarda el catálogo actual en fichero JSON usando las funciones de persistencia."""
        try:
            repo: Repositorio[ObjetoCeleste] = Repositorio()
            for obj in self.catalogo.objetos:
                repo.agregar(obj)
            guardar_repositorio_json(repo, self.ruta_json, self.logger)
            messagebox.showinfo(
                "Persistencia", f"Catálogo guardado con éxito en '{self.ruta_json}'."
            )
        except PersistenciaError as e:
            messagebox.showerror("Error de Persistencia", str(e))

    def _on_cargar_json(self) -> None:
        """Carga y reemplaza el catálogo desde un fichero JSON."""
        if not self.ruta_json.exists():
            messagebox.showwarning("Aviso", f"No existe el archivo '{self.ruta_json}' para cargar.")
            return
        try:
            repo = cargar_repositorio_json(self.ruta_json, self.logger)
            self.catalogo.objetos = repo.obtener_todos()
            self._actualizar_tabla()
            messagebox.showinfo(
                "Persistencia",
                f"Cargados {len(self.catalogo.objetos)} objetos desde '{self.ruta_json}'.",
            )
        except PersistenciaError as e:
            messagebox.showerror("Error de Carga", str(e))

    def _on_eliminar_objeto(self) -> None:
        """Elimina el objeto celeste seleccionado controlando los elementos protegidos."""
        seleccion = self.tabla.selection()
        if not seleccion:
            messagebox.showwarning(
                "Aviso", "Por favor, selecciona un objeto de la tabla para eliminar."
            )
            return

        item = self.tabla.item(seleccion)
        valores = item.get("values")
        if not valores:
            return

        identificador_a_borrar = valores[0]

        # Lista de objetos protegidos por defecto del catálogo de ejemplo
        PROTEGIDOS = {"Sol", "Luna", "Sirio", "Júpiter", "Saturno", "Neptuno", "M45", "Pluton"}

        if identificador_a_borrar in PROTEGIDOS:
            messagebox.showerror(
                "Acción no permitida",
                f"El objeto '{identificador_a_borrar}' forma parte de los cuerpos celestes base del observatorio y NO se puede eliminar.",
            )
            return

        confirmar = messagebox.askyesno(
            "Confirmar eliminación",
            f"¿Estás seguro de que deseas eliminar el objeto personalizado '{identificador_a_borrar}'?",
        )
        if not confirmar:
            return

        # Intentamos borrar usando el método protegido del catálogo
        try:
            exito = self.catalogo.eliminar(identificador_a_borrar)
            if exito:
                self._actualizar_tabla()
                self.logger.info(
                    "Objeto '%s' eliminado desde la interfaz gráfica.", identificador_a_borrar
                )
                messagebox.showinfo(
                    "Éxito", f"Objeto '{identificador_a_borrar}' eliminado correctamente."
                )
        except ValueError as e:
            messagebox.showerror("Error de Dominio", str(e))


def iniciar_interfaz() -> None:
    """Función de lanzamiento de la GUI."""
    app = VentanaObservatorio()
    app.mainloop()


if __name__ == "__main__":
    iniciar_interfaz()
