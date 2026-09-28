"""
Fuentes de video: la camara real (OpenCV) o una camara simulada para el
modo demostracion y las pruebas automaticas.
"""

import os
import time

import numpy as np

from . import config, synthetic
from .hands import empty_hands

os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")  # abre mas rapido en Windows


class CameraError(Exception):
    pass


CAMERA_HELP = ("No pude abrir la cámara. Revisa que no la esté usando otra app (Zoom, Teams, "
               "Meet) y que Windows permita usarla: Configuración › Privacidad › Cámara.")


class CameraSource:
    provides_hands = False

    def __init__(self, index=0):
        self.index = index
        self._cap = None

    def open(self):
        import cv2
        backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY] if os.name == "nt" else [cv2.CAP_ANY]
        for backend in backends:
            cap = cv2.VideoCapture(self.index, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
                cap.set(cv2.CAP_PROP_FPS, 30)
                ok, frame = cap.read()
                if ok and frame is not None:
                    self._cap = cap
                    return
            cap.release()
        raise CameraError(CAMERA_HELP)

    def read(self):
        """Frame en RGB, ya volteado como espejo (o None si fallo)."""
        import cv2
        ok, frame = self._cap.read()
        if not ok or frame is None:
            return None
        return cv2.cvtColor(cv2.flip(frame, 1), cv2.COLOR_BGR2RGB)

    def release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None


def probe_cameras(max_index=4):
    """Indices de camaras que responden (tarda ~1 s por camara)."""
    import cv2
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
        if cap.isOpened() and cap.read()[0]:
            found.append(i)
        cap.release()
    return found


class SyntheticSource:
    """Camara falsa: una 'persona' sintetica que hace senas en un fondo oscuro."""

    provides_hands = True

    def __init__(self, fps=30.0, seed=7):
        self.fps = fps
        self.rng = np.random.default_rng(seed)
        self.performer = synthetic.Performer(synthetic.SynthSigner(seed=seed), 4 / 3, self.rng)
        self._signs = {}
        self._queue = None
        self._start = None
        self._t0 = time.monotonic()
        self._next_auto = 1.0
        self._auto_ids = [s.id for s in config.SIGNS if s.id != config.NOTHING_ID]
        h, w = config.CAMERA_HEIGHT, config.CAMERA_WIDTH
        yy, xx = np.mgrid[0:h, 0:w]
        glow = np.exp(-(((xx - w * 0.5) / (w * 0.6)) ** 2 + ((yy - h * 0.35) / (h * 0.7)) ** 2))
        base = np.stack([10 + 14 * glow, 34 + 40 * glow, 44 + 46 * glow], axis=-1)  # turquesa oscuro
        self._background = base.astype(np.uint8)

    def open(self):
        self._t0 = time.monotonic()

    def perform(self, sign_id, delay=0.25):
        """Programa una sena (lo usa la grabacion en modo demo)."""
        self._queue = (sign_id, time.monotonic() - self._t0 + delay)

    def _sign(self, sign_id):
        if sign_id not in self._signs:
            self._signs[sign_id] = synthetic.sign_for_id(sign_id)
        return self._signs[sign_id]

    def read_with_hands(self):
        time.sleep(1.0 / self.fps)
        t = time.monotonic() - self._t0
        if self._queue is None and t > self._next_auto:
            sign_id = self._auto_ids[int(self.rng.integers(len(self._auto_ids)))]
            self._queue = (sign_id, t)
            self._next_auto = t + 3.2
        hands = empty_hands()
        if self._queue is not None:
            sign_id, start = self._queue
            image, world = self.performer.hands_at(self._sign(sign_id), t, start, 1.25)
            hands.image[:], hands.world[:] = image, world
            if t > start + 1.6:
                self._queue = None
        else:
            image, world = self.performer.hands_at(self._sign(config.NOTHING_ID), t, -10, 1.0)
            hands.image[:], hands.world[:] = image, world
        return self._background.copy(), hands

    def release(self):
        pass
