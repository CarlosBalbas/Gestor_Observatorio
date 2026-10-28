"""Punto de entrada para la ejecución mediante `python -m observatorio`."""

import sys

from observatorio.cli import main

if __name__ == "__main__":
    sys.exit(main())
