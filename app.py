"""
Mira&Tek - app de escritorio para grabar y entrenar senas de LSM.

Uso:
    python app.py            abre la app
    python app.py --demo     abre la app con una camara simulada (sin camara real)
"""

import multiprocessing
import sys


def main():
    multiprocessing.freeze_support()  # necesario dentro del .exe
    from miratek.ui.app import run
    sys.exit(run(sys.argv))


if __name__ == "__main__":
    main()
