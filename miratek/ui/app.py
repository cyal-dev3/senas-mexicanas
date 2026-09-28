"""Arranque de la app de escritorio."""

import argparse
import logging
import logging.handlers
import os
import sys
import traceback

from .. import __version__, config


def _setup_logging():
    folder = config.user_data_dir() / "logs"
    folder.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(folder / "miratek.log", maxBytes=1_000_000,
                                                   backupCount=2, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[handler])
    logging.getLogger(__name__).info("Mira&Tek %s iniciando (Python %s)", __version__, sys.version.split()[0])


def _close_splash():
    """Cierra la pantalla de carga del .exe (si existe)."""
    try:
        import pyi_splash  # solo existe dentro del .exe
        pyi_splash.close()
    except Exception:
        pass


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="MiraTek", description="Mira&Tek: grabar y entrenar señas LSM")
    parser.add_argument("--demo", action="store_true", help="usar una cámara simulada")
    parser.add_argument("--datos", help="carpeta de datos alternativa")
    parser.add_argument("--autoprueba", action="store_true", help="revisa que el .exe funcione y sale")
    return parser.parse_args(argv[1:])


def run(argv):
    args = parse_args(argv)
    if args.datos:
        os.environ["MIRATEK_DATA"] = args.datos
    _setup_logging()
    if args.autoprueba:
        from .selftest import run_selftest
        return run_selftest()

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMessageBox

    from ..dataset import DatasetStore
    from . import sounds, theme
    from .context import AppContext
    from .dialogs import WelcomeDialog
    from .main_window import MainWindow
    from .settings import Settings
    from .workers import CameraController

    if sys.platform == "win32":
        try:  # icono propio en la barra de tareas (no el de Python)
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MiraTek.LSM")
        except Exception:
            pass

    app = QApplication(argv)
    app.setApplicationName(config.APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(theme.stylesheet())
    app.setFont(theme.ui_font(14))
    icon = config.resource_path("assets", "icon.png")
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    def excepthook(exc_type, exc, tb):
        logging.getLogger("miratek").error("Error no controlado:\n%s",
                                           "".join(traceback.format_exception(exc_type, exc, tb)))
        QMessageBox.warning(None, config.APP_NAME,
                            "Algo salió mal, pero tus grabaciones están a salvo.\n"
                            "Si vuelve a pasar, envía tu archivo desde «Compartir» para revisarlo.")
    sys.excepthook = excepthook

    settings = Settings.load()
    sounds.enabled = settings.sounds
    sounds.prepare()
    store = DatasetStore(config.user_data_dir() / "datos")
    camera = CameraController(settings, demo=args.demo)
    ctx = AppContext(settings, store, camera, demo=args.demo)

    _close_splash()
    if not settings.signer_id:
        dialog = WelcomeDialog()
        if not dialog.exec():
            return 0
        settings.new_signer(dialog.value())
    store.set_signer_name(settings.signer_id, settings.signer_name)

    window = MainWindow(ctx)
    window.show()
    return app.exec()
