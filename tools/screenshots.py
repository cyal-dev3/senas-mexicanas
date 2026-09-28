"""
Capturas de pantalla de la app en modo demostracion (sin camara real).

    python tools/screenshots.py CARPETA_DE_SALIDA

Crea datos sinteticos en una carpeta temporal, entrena un modelo rapido y
guarda una captura de cada pantalla. Sirve para revisar el diseno.
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="miratek_capturas_")
    os.environ["MIRATEK_DATA"] = tmp
    # Sin "offscreen": esa plataforma no tiene fuentes. Usamos una ventana invisible.

    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from miratek import config
    from miratek.dataset import DatasetStore
    from miratek.synthetic import fill_store
    from miratek.training import TrainConfig, train_from_store
    from miratek.ui import theme
    from miratek.ui.context import AppContext
    from miratek.ui.main_window import MainWindow
    from miratek.ui.settings import Settings
    from miratek.ui.workers import CameraController

    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(theme.stylesheet())
    app.setFont(theme.ui_font(14))

    store = DatasetStore(config.user_data_dir() / "datos")
    ids = ["hola", "gracias", "por_favor", "si", "no", "ayuda", "nada",
           "letra_a", "letra_b", "letra_c", "letra_d", "num_1", "num_2", "num_3", "num_20"]
    fill_store(store, n_signers=2, clips_per_sign=6, sign_ids=ids)
    settings = Settings(signer_id="persona-0", signer_name="Ana López")
    settings.save()
    ctx = AppContext(settings, store, CameraController(settings, demo=True), demo=True)
    model = train_from_store(store, TrainConfig(aug_copies=3, eval_aug_copies=2, max_epochs=20,
                                                eval_max_epochs=10))
    model.save(ctx.model_path)

    from PySide6.QtCore import Qt
    window = MainWindow(ctx)
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    window.resize(1440, 900)
    window.show()

    def shot(name, wait=700):
        QTest.qWait(wait)
        window.grab().save(str(out / f"{name}.png"))
        print("captura:", name)

    shot("1_inicio")
    window.navigate("record")
    shot("2_grabar_lista")
    window.pages["record"]._set_category(config.LETTERS)
    shot("3_grabar_abecedario")
    window.pages["record"]._set_category(config.WORDS)
    window.navigate("record", sign_id="gracias")
    shot("4_grabar_cuenta_regresiva", 1600)
    shot("5_grabar_grabando", 1800)
    window.navigate("train")
    shot("6_entrenar_resultados", 1500)
    window.navigate("live")
    shot("7_probar_en_vivo", 5000)
    window.navigate("share")
    shot("8_compartir")
    window.close()
    ctx.camera.shutdown()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "capturas")
