# Gestor Observatorio Astronómico

Proyecto desarrollado para la asignatura Técnicas de Programación Avanzada (Universidad Nebrija).

## Integrantes

- Carlos Balbás
- Lucas Parreño
- Victor Llorente

## Versión

v1.0.0

## Requisitos

- Python 3.10 o superior.
- Tkinter para la interfaz gráfica. Viene incluido con el instalador oficial de Python en
  Windows y macOS; en Linux puede requerir el paquete del sistema `python3-tk`.
  Se comprueba con:

```bash
python -m tkinter
```

## Instalación

```bash
# 1. Crear el entorno virtual
python -m venv .venv

# 2. Activarlo
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux / macOS

# 3. Instalar dependencias y el paquete en modo editable
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e ".[dev]"
```

## Ejecución

```bash
python -m observatorio --demo                              # demostración automática completa
python -m observatorio --demo --config config.example.json # con configuración personalizada
python -m observatorio --gui                               # interfaz gráfica (Tkinter)
python -m observatorio --version                           # versión
```

La configuración (`config.example.json`) define rutas de ficheros, nivel de log y
`factor_capacidad` (capacidad máxima del catálogo = objetos iniciales × factor).

## Calidad, pruebas y documentación

```bash
python -m black --check src tests
python -m ruff check src tests
python -m pytest                    # incluye informe de cobertura
python -m pdoc observatorio -o docs # referencia de la API en docs/
```

Las pruebas de la interfaz gráfica se omiten automáticamente (`skip`) si Tkinter no está
disponible; el resto de la suite se ejecuta igualmente.

## Funcionalidades principales

- Gestión de objetos celestes con validación (rango de coordenadas, identificador único).
- Persistencia JSON y SQLite (guardado de repositorios en una única transacción).
- Validación de registros mediante expresiones regulares (`re` y `regex`).
- Logging en consola y fichero.
- Patrones Factory Method y Observer.
- Interfaz gráfica con Tkinter; las operaciones de disco se ejecutan en un hilo de trabajo
  para que la ventana no se bloquee.
- Pruebas automáticas con pytest (unitarias, de interfaz y de integración).
