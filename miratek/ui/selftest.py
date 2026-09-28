"""
Autoprueba del .exe (MiraTek.exe --autoprueba).

Revisa que todo lo empaquetado funcione: detector de manos, entrenamiento,
exportacion al celular y la interfaz. Escribe el resultado en
%LOCALAPPDATA%\\MiraTek\\autoprueba.txt y sale con codigo 0 si todo esta bien.
"""

import os
import tempfile
import traceback
from pathlib import Path

import numpy as np

from .. import config


def run_selftest():
    lines = []
    failed = False

    def check(name, fn):
        nonlocal failed
        try:
            fn()
            lines.append(f"OK    {name}")
        except Exception:
            failed = True
            lines.append(f"FALLA {name}\n{traceback.format_exc()}")

    def detector():
        from ..hands import HandDetector
        det = HandDetector()
        hands = det.detect(np.zeros((480, 640, 3), np.uint8), 1000)
        det.close()
        assert not hands.any

    def training():
        from ..dataset import DatasetStore
        from ..export_android import export_android_model
        from ..synthetic import fill_store
        from ..training import TrainConfig, TrainedModel, train_from_store
        with tempfile.TemporaryDirectory() as tmp:
            store = DatasetStore(Path(tmp) / "datos")
            fill_store(store, n_signers=2, n_signs=3, clips_per_sign=4)
            model = train_from_store(store, TrainConfig(aug_copies=2, eval_aug_copies=1, max_epochs=5,
                                                        eval_max_epochs=3))
            model.save(Path(tmp) / "m.npz")
            TrainedModel.load(Path(tmp) / "m.npz")
            export_android_model(model, Path(tmp) / "m.json")

    def interface():
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        from ..dataset import DatasetStore
        from . import theme
        from .context import AppContext
        from .main_window import MainWindow
        from .settings import Settings
        from .workers import CameraController
        app = QApplication.instance() or QApplication([])
        app.setStyleSheet(theme.stylesheet())
        settings = Settings(signer_id="prueba-0000", signer_name="Prueba")
        with tempfile.TemporaryDirectory() as tmp:
            store = DatasetStore(Path(tmp) / "datos")
            ctx = AppContext(settings, store, CameraController(settings, demo=True), demo=True)
            window = MainWindow(ctx)
            for key in ("record", "train", "live", "share", "home"):
                window.navigate(key)
                app.processEvents()
            window.close()

    check("Detector de manos (MediaPipe)", detector)
    check("Entrenamiento y exportación", training)
    check("Interfaz", interface)
    report = config.user_data_dir() / "autoprueba.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 1 if failed else 0
