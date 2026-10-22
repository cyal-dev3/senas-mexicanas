"""
Trabajo pesado en hilos separados, para que la ventana nunca se congele:
  - CameraWorker: lee la camara y detecta manos (~30 veces por segundo).
  - TrainWorker: entrena el modelo.
  - ImportWorker / ExportWorker: abren y crean los archivos para compartir.
"""

import logging
import os
import time
from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtGui import QImage

from ..camera import CAMERA_HELP, CameraError, CameraSource, SyntheticSource
from ..hands import FrameHands
from ..package import ImportResult, PackageError, export_package, import_package
from ..training import TrainingCancelled, TrainingError, train_from_store

log = logging.getLogger(__name__)

OTHER_CAMERA = "O elige otra cámara en Ajustes (el engrane junto a tu nombre)."


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
        self.ended = False  # True cuando la ventana ya recibio "finished"
        self.source = None

    def stop(self):
        self._stop = True

    def run(self):
        detector = None
        try:
            self.status.emit("starting", "Encendiendo la cámara…")
            try:
                self.source = SyntheticSource() if self.demo else CameraSource(self.camera_index)
                self.source.open()
                if not self.source.provides_hands and not self._stop:
                    self.status.emit("starting", "Preparando el detector de manos…")
                    from ..hands import HandDetector
                    if not self._stop:  # preparar el detector tarda: quiza ya no lo necesitan
                        detector = HandDetector()
            except CameraError as exc:
                self.status.emit("error", f"{exc} {OTHER_CAMERA}")
                return
            except Exception:
                log.exception("No se pudo iniciar la camara o el detector")
                self.status.emit("error", "No pude preparar la cámara o el detector de manos. Intenta de nuevo.")
                return
            if self._stop:
                return
            self.status.emit("running", "")
            self._loop(detector)
        except Exception:
            log.exception("Error leyendo la camara")
            self.status.emit("error", "Algo falló con la cámara. Intenta de nuevo.")
        finally:
            if detector is not None:
                detector.close()
            self._release()

    def _loop(self, detector):
        failures = 0
        while not self._stop:
            if self.source.provides_hands:
                rgb, hands = self.source.read_with_hands()
            else:
                rgb = self.source.read()
                if rgb is None:
                    failures += 1
                    if failures > 30:
                        self.status.emit("error", f"La cámara dejó de responder. {CAMERA_HELP} {OTHER_CAMERA}")
                        return
                    time.sleep(0.03)
                    continue
                failures = 0
                hands = detector.detect(rgb, time.monotonic() * 1000)
            t = time.monotonic()
            h, w = rgb.shape[:2]
            image = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
            self.frame.emit(FramePacket(t, image, hands, w / h))

    def _release(self):
        if self.source is not None:
            try:
                self.source.release()
            except Exception:
                log.exception("No se pudo liberar la camara")


class CameraController(QObject):
    """
    Enciende la camara solo cuando alguna pantalla la necesita.

    Apagarla nunca bloquea la ventana: el hilo viejo termina solo (queda en
    _retiring) y uno nuevo espera a que el anterior suelte la camara, asi nunca
    hay dos hilos abriendo la misma. Al soltarla quedan unos segundos de gracia:
    pasar de Grabar a Probar no vuelve a abrir la camara ni el detector de manos.
    """

    frame = Signal(object)
    status = Signal(str, str)
    GRACE_MS = 8000

    def __init__(self, settings, demo=False, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.demo = demo
        self._users = set()
        self._worker = None          # el hilo que entrega los frames
        self._retiring = []          # hilos a los que ya se les pidio parar (aun no terminan)
        self._start_pending = False  # encender en cuanto los hilos viejos suelten la camara
        self._grace = QTimer(self, singleShot=True, interval=self.GRACE_MS)
        self._grace.timeout.connect(self._stop)
        self.state = "stopped"
        self.message = ""

    def acquire(self, user):
        self._users.add(user)
        self._grace.stop()
        if self._worker is None and not self._start_pending:
            self._start()

    def release(self, user):
        self._users.discard(user)
        if not self._users and (self._worker is not None or self._start_pending):
            self._grace.start()  # se apaga en unos segundos, si nadie la vuelve a pedir

    def restart(self):
        """Vuelve a abrir la camara (por ejemplo, despues de un error o al cambiarla)."""
        self._stop()
        if self._users:
            self._start()

    def busy_indices(self):
        """Camaras que esta app tiene abiertas ahora (para no molestarlas al buscar otras)."""
        workers = [w for w in (self._worker, *self._retiring) if w is not None and not w.ended]
        return {w.camera_index for w in workers if not w.demo}

    def perform_demo(self, sign_id):
        """Solo en modo demo: la camara falsa hace esa sena."""
        if self._worker is not None and isinstance(self._worker.source, SyntheticSource):
            self._worker.source.perform(sign_id)

    def _start(self):
        self._grace.stop()
        if self._retiring:
            # El hilo anterior todavia tiene la camara: arrancamos cuando la suelte
            self._start_pending = True
            self._set_state("starting", "Encendiendo la cámara…")
            return
        self._start_pending = False
        worker = CameraWorker(self.settings.camera_index, self.demo)
        worker.frame.connect(self.frame)
        worker.status.connect(self._on_worker_status)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()

    def _stop(self):
        """Pide al hilo que pare, sin esperarlo (la ventana no se congela)."""
        self._grace.stop()
        self._start_pending = False
        worker, self._worker = self._worker, None
        if worker is not None:
            try:
                worker.frame.disconnect(self.frame)
            except (RuntimeError, TypeError):
                pass
            worker.stop()
            if not worker.ended:
                self._retiring.append(worker)  # guardamos la referencia hasta que termine
        self._set_state("stopped", "")

    def _set_state(self, state, message):
        self.state, self.message = state, message
        self.status.emit(state, message)

    def _on_worker_status(self, state, message):
        if self.sender() is not self._worker:
            return  # aviso de un hilo viejo
        self._set_state(state, message)

    def _on_worker_finished(self):
        worker = self.sender()
        if not isinstance(worker, CameraWorker):
            return
        worker.ended = True
        if worker in self._retiring:
            self._retiring.remove(worker)
        if worker is self._worker:
            self._worker = None  # termino solo (por un error): acquire o restart la vuelven a abrir
            if self.state != "error":
                self._set_state("stopped", "")
        if self._start_pending and not self._retiring:
            if self._users:
                self._start()
            else:
                self._start_pending = False

    def alive_threads(self):
        """Hilos de camara que todavia no terminan."""
        return [w for w in (self._worker, *self._retiring) if w is not None and not w.isFinished()]

    def shutdown(self, timeout_ms=5000):
        """Apaga la camara y espera de verdad a los hilos. False si alguno sigue vivo."""
        self._users.clear()
        self._stop()
        deadline = time.monotonic() + timeout_ms / 1000
        for worker in list(self._retiring):
            left = int((deadline - time.monotonic()) * 1000)
            if left <= 0 or not worker.wait(left):
                break
        return not self.alive_threads()


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


@dataclass
class FileImport:
    """Lo que paso con cada archivo recibido."""
    name: str
    result: ImportResult | None = None
    error: str = ""


class ImportWorker(QThread):
    """Abre los archivos recibidos uno por uno, sin congelar la ventana."""

    progress = Signal(int, int, str)  # (archivos listos, total, archivo que se esta abriendo)
    done = Signal(list)               # [FileImport, ...]

    def __init__(self, store, files, models_dir, parent=None):
        super().__init__(parent)
        self.store = store
        self.files = list(files)
        self.models_dir = models_dir

    def run(self):
        results = []
        total = len(self.files)
        for i, path in enumerate(self.files):
            name = os.path.basename(path)
            self.progress.emit(i, total, name)
            try:
                results.append(FileImport(name, import_package(self.store, path, self.models_dir)))
            except PackageError as exc:
                results.append(FileImport(name, error=str(exc)))
            except Exception:
                log.exception("No se pudo importar %s", path)
                results.append(FileImport(name, error="No pude abrir este archivo."))
        self.progress.emit(total, total, "")
        self.done.emit(results)


class ExportWorker(QThread):
    """Crea el archivo para enviar."""

    done = Signal(object)  # ruta del archivo
    failed = Signal(str)

    def __init__(self, store, dest_dir, author, model_path=None, log_path=None, include_clips=True,
                 parent=None):
        super().__init__(parent)
        self.args = (store, dest_dir, author)
        self.kwargs = dict(model_path=model_path, log_path=log_path, include_clips=include_clips)

    def run(self):
        try:
            path = export_package(*self.args, **self.kwargs)
        except PackageError as exc:
            self.failed.emit(str(exc))
        except OSError:
            log.exception("No se pudo crear el paquete")
            self.failed.emit("No pude crear el archivo. Revisa que haya espacio en la computadora.")
        except Exception:
            log.exception("No se pudo crear el paquete")
            self.failed.emit("No pude crear el archivo. Intenta de nuevo.")
        else:
            self.done.emit(path)
