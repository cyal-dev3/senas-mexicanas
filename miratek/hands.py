"""
Deteccion de manos con MediaPipe.

MediaPipe encuentra 21 puntos (landmarks) en cada mano:
  - Punto 0: muneca
  - Puntos 1-4: pulgar, 5-8: indice, 9-12: medio, 13-16: anular, 17-20: menique

Por cada mano guardamos DOS versiones de esos puntos:
  - image: posicion en la imagen (x, y de 0 a 1). Sirve para saber DONDE esta
           la mano y COMO se mueve.
  - world: posicion 3D en metros, centrada en la mano. Sirve para saber la
           FORMA de la mano sin importar que tan lejos este de la camara.

Si una mano no aparece, sus valores son NaN ("no es un numero"), que es mas
claro que llenarlos con ceros.
"""

import os
import sys
from dataclasses import dataclass

import numpy as np

from . import config

LEFT, RIGHT = 0, 1  # Posicion de cada mano en los arreglos

# Conexiones entre puntos para dibujar el "esqueleto" de la mano
HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)

# Si la unica mano visible "cambia de etiqueta" pero sigue en el mismo lugar,
# es la misma mano: MediaPipe a veces confunde izquierda y derecha.
CONTINUITY_DISTANCE = 0.10


@dataclass
class FrameHands:
    """Manos detectadas en UN frame."""
    image: np.ndarray  # (2, 21, 3) float32, [LEFT] y [RIGHT]; NaN si no hay mano
    world: np.ndarray  # (2, 21, 3) float32

    @property
    def present(self):
        return ~np.isnan(self.image[:, 0, 0])

    @property
    def any(self):
        return bool(self.present.any())


def empty_hands():
    nan = np.full((2, 21, 3), np.nan, dtype=np.float32)
    return FrameHands(nan, nan.copy())


def assign_slots(detections, previous=None):
    """Decide cual mano va en la posicion izquierda y cual en la derecha.

    detections: lista de (etiqueta 'Left'/'Right', imagen (21,3), mundo (21,3)).
    previous: FrameHands del frame anterior (para la continuidad).

    Arregla dos errores comunes de MediaPipe:
      1. Dos manos con la misma etiqueta: cada una sigue en la posicion del
         frame anterior; si no hay anterior, se usa la convencion observada de
         MediaPipe ("Right" = la mano mas a la izquierda de la imagen en espejo).
      2. Una sola mano que cambia de etiqueta sin moverse: se queda donde estaba.
    """
    hands = empty_hands()
    if not detections:
        return hands

    if len(detections) >= 2:
        a, b = detections[0], detections[1]
        if a[0] == b[0]:
            # Misma etiqueta. Si en el frame anterior habia dos manos, cada una se
            # queda en la posicion de la mas cercana. Si no, decidimos por la
            # posicion horizontal con la convencion que de verdad da MediaPipe en
            # nuestras imagenes (ya en espejo): la etiqueta "Right" cae en la mano
            # que se ve MAS A LA IZQUIERDA de la imagen (medido en 2025 clips).
            if previous is not None and previous.present.all():
                d_straight = (np.linalg.norm(previous.image[LEFT, 0, :2] - a[1][0, :2])
                              + np.linalg.norm(previous.image[RIGHT, 0, :2] - b[1][0, :2]))
                d_swapped = (np.linalg.norm(previous.image[LEFT, 0, :2] - b[1][0, :2])
                             + np.linalg.norm(previous.image[RIGHT, 0, :2] - a[1][0, :2]))
                slots = [(LEFT, a), (RIGHT, b)] if d_straight <= d_swapped else [(LEFT, b), (RIGHT, a)]
            else:
                a, b = sorted((a, b), key=lambda d: d[1][0, 0])
                slots = [(RIGHT, a), (LEFT, b)]
        else:
            slots = [(RIGHT if d[0] == "Right" else LEFT, d) for d in (a, b)]
    else:
        det = detections[0]
        slot = RIGHT if det[0] == "Right" else LEFT
        if previous is not None:
            prev_present = previous.present
            other = 1 - slot
            if prev_present[other] and not prev_present[slot]:
                distance = np.linalg.norm(previous.image[other, 0, :2] - det[1][0, :2])
                if distance < CONTINUITY_DISTANCE:
                    slot = other
        slots = [(slot, det)]

    for slot, (_, image, world) in slots:
        hands.image[slot] = image
        hands.world[slot] = world
    return hands


class HandDetector:
    """Envuelve el HandLandmarker de MediaPipe en modo video."""

    def __init__(self, model_path=None, min_detection=0.6, min_presence=0.5, min_tracking=0.5):
        # Silenciar los mensajes internos de MediaPipe en la terminal
        os.environ.setdefault("GLOG_minloglevel", "2")
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
        if getattr(sys, "frozen", False):
            # Dentro del .exe, matplotlib (que MediaPipe carga) usaria una carpeta
            # temporal y rehace su cache de fuentes cada vez: ~4 s mas lento.
            os.environ["MPLCONFIGDIR"] = str(config.user_data_dir() / "matplotlib")
        # Importamos aqui (y no arriba) porque MediaPipe tarda unos segundos en
        # cargar; asi la ventana aparece rapido.
        from mediapipe.tasks.python.core import base_options
        from mediapipe.tasks.python.vision import hand_landmarker
        from mediapipe.tasks.python.vision.core import image as mp_image
        from mediapipe.tasks.python.vision.core import vision_task_running_mode as running_mode

        path = model_path or config.resource_path("assets", "hand_landmarker.task")
        # Leemos el modelo a memoria en vez de pasar la ruta: MediaPipe falla con
        # rutas que tienen acentos o n (ej: C:\Users\Pena\...).
        with open(path, "rb") as f:
            model_bytes = f.read()

        options = hand_landmarker.HandLandmarkerOptions(
            base_options=base_options.BaseOptions(model_asset_buffer=model_bytes),
            running_mode=running_mode.VisionTaskRunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=min_detection,
            min_hand_presence_confidence=min_presence,
            min_tracking_confidence=min_tracking,
        )
        self._landmarker = hand_landmarker.HandLandmarker.create_from_options(options)
        self._mp_image = mp_image
        self._last_ts = -1
        self._previous = None

    def detect(self, rgb, timestamp_ms):
        """Detecta manos en un frame RGB (ya volteado como espejo)."""
        # MediaPipe exige que el tiempo siempre avance
        timestamp_ms = max(int(timestamp_ms), self._last_ts + 1)
        self._last_ts = timestamp_ms

        image = self._mp_image.Image(image_format=self._mp_image.ImageFormat.SRGB,
                                     data=np.ascontiguousarray(rgb))
        result = self._landmarker.detect_for_video(image, timestamp_ms)

        detections = []
        for lms, world, handedness in zip(result.hand_landmarks,
                                          result.hand_world_landmarks,
                                          result.handedness):
            label = handedness[0].category_name
            img = np.array([[p.x, p.y, p.z] for p in lms], dtype=np.float32)
            wld = np.array([[p.x, p.y, p.z] for p in world], dtype=np.float32)
            detections.append((label, img, wld))

        hands = assign_slots(detections, self._previous)
        self._previous = hands
        return hands

    def close(self):
        try:
            self._landmarker.close()
        except Exception:
            pass
