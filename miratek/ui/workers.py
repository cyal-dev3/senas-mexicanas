"""
Trabajo pesado en hilos separados, para que la ventana nunca se congele:
  - CameraWorker: lee la camara y detecta manos (~30 veces por segundo).
  - TrainWorker: entrena el modelo.
"""

import logging
import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QImage

from ..camera import CAMERA_HELP, CameraError, CameraSource, SyntheticSource
from ..hands import FrameHands
from ..training import TrainingCancelled, TrainingError, train_from_store

log = logging.getLogger(__name__)


@dataclass
class FramePacket:
    t: float              # segundos (reloj monotono)
    image: QImage
    hands: FrameHands
    aspect: float         # ancho / alto


class CameraWorker(QThread):
    frame = Signal(object)
    status = Signal(str, str)  # (estado, mensaje): starting, running, error

    def __init__(self, camera_index=0, demo=False, parent=None):
        super().__init__(parent)
        self.camera_index = camera_index
        self.demo = demo
        self._stop = False
        self.source = None

    def stop(self):
        self._stop = True

    def run(self):
        detector = None
        self.status.emit("starting", "Encendiendo la cámara…")
        try:
            self.source = SyntheticSource() if self.demo else CameraSource(self.camera_index)
            self.source.open()
            if not self.source.provides_hands:
                self.status.emit("starting", "Preparando el detector de manos…")
                from ..hands import HandDetector
                detector = HandDetector()
        except CameraError as exc:
            self.status.emit("error", str(exc))
            return
        except Exception:
            log.exception("No se pudo iniciar la camara")
            self.status.emit("error", CAMERA_HELP)
            return

        self.status.emit("running", "")
        failures = 0
        try:
            while not self._stop:
                if self.source.provides_hands:
                    rgb, hands = self.source.read_with_hands()
                else:
                    rgb = self.source.read()
                    if rgb is None:
                        failures += 1
                        if failures > 30:
                            self.status.emit("error", "La cámara dejó de responder. " + CAMERA_HELP)
                            return
                        time.sleep(0.03)
                        continue
                    failures = 0
                    hands = detector.detect(rgb, time.monotonic() * 1000)
                t = time.monotonic()
                h, w = rgb.shape[:2]
                image = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
                self.frame.emit(FramePacket(t, image, hands, w / h))
        except Exception:
            log.exception("Error leyendo la camara")
            self.status.emit("error", "Algo falló con la cámara. Intenta de nuevo.")
        finally:
            if detector is not None:
                detector.close()
            self.source.release()


class CameraController(QObject):
    """Enciende la camara solo cuando alguna pantalla la necesita."""

    frame = Signal(object)
    status = Signal(str, str)

    def __init__(self, settings, demo=False, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.demo = demo
        self._users = set()
        self._worker = None
        self.state = "stopped"
        self.message = ""

    def acquire(self, user):
        self._users.add(user)
        if self._worker is None:
            self._start()

    def release(self, user):
        self._users.discard(user)
        if not self._users:
            self._stop()

    def restart(self):
        self._stop()
        if self._users:
            self._start()

    def perform_demo(self, sign_id):
        """Solo en modo demo: la camara falsa hace esa sena."""
        if self._worker is not None and isinstance(self._worker.source, SyntheticSource):
            self._worker.source.perform(sign_id)

    def _start(self):
        worker = CameraWorker(self.settings.camera_index, self.demo)
        worker.frame.connect(self.frame)
        worker.status.connect(self._on_status)
        worker.finished.connect(lambda w=worker: self._on_finished(w))
        self._worker = worker
        worker.start()

    def _stop(self):
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.frame.disconnect(self.frame)
            worker.stop()
            worker.wait(3000)
        self._on_status("stopped", "")

    def _on_status(self, state, message):
        if self.sender() is not None and self.sender() is not self._worker and state != "stopped":
            return  # aviso de un hilo viejo
        self.state, self.message = state, message
        self.status.emit(state, message)

    def _on_finished(self, worker):
        if worker is self._worker and self.state != "error":
            self._worker = None

    def shutdown(self):
        self._users.clear()
        self._stop()


class TrainWorker(QThread):
    progress = Signal(float, str)
    done = Signal(object)    # TrainedModel
    failed = Signal(str)

    def __init__(self, store, model_path, parent=None):
        super().__init__(parent)
        self.store = store
        self.model_path = model_path
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            model = train_from_store(self.store, progress=lambda f, m: self.progress.emit(f, m),
                                     should_cancel=lambda: self._cancel)
            # Guardamos el anterior por si el nuevo sale peor
            fresh = self.model_path.with_name("modelo_nuevo.npz")
            model.save(fresh)
            if self.model_path.exists():
                self.model_path.replace(self.model_path.with_name("modelo_anterior.npz"))
            fresh.replace(self.model_path)
            self.done.emit(model)
        except TrainingCancelled:
            self.failed.emit("Cancelaste el entrenamiento.")
        except TrainingError as exc:
            self.failed.emit(str(exc))
        except Exception:
            log.exception("Fallo el entrenamiento")
            self.failed.emit("Algo salió mal al entrenar. Intenta de nuevo.")
