# Gestor Observatorio Astronómico

Proyecto desarrollado para la asignatura Técnicas de Programación Avanzada.

## Integrantes

- Carlos Balbás
- Lucas Parreño
- Victor Llorente

## Versión

v1.0.0

## Instalación

Crear entorno virtual:

```bash
python -m venv .venv

Activar el entorno virtual en Windows:

.venv\Scripts\activate

Instalar dependencias:

pip install -r requirements.txt
pip install -e ".[dev]"

Ejecución:

python -m observatorio --demo
python -m observatorio --gui
python -m observatorio --version

Funcionalidades principales:

- Gestión de objetos celestes.
- Persistencia JSON y SQLite.
- Validación mediante expresiones regulares.
- Logging.
- Factory Method y Observer.
- Interfaz gráfica con Tkinter.
- Pruebas automáticas con pytest.