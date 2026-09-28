"""
Reconocimiento en vivo, estable y sin parpadeos.

Antes se predecia cada frame por separado: la respuesta saltaba de una sena
a otra y, con las manos quietas, igual "adivinaba" algo. Ahora:
  1. Se juntan los ultimos ~2 segundos de frames (una ventana).
  2. Se calcula la prediccion cada pocos frames con la MISMA funcion de
     caracteristicas del entrenamiento.
  3. Se suavizan las probabilidades (promedio movil).
  4. Una sena solo se "confirma" si gana varias veces seguidas con buena
     confianza, y no se repite mientras la sigas sosteniendo.
  5. La clase "Nada" y la falta de manos significan "no hay sena".
"""

from collections import deque
from dataclasses import dataclass

import numpy as np

from . import config
from .features import window_features


@dataclass
class Prediction:
    sign_id: str | None       # sena con mayor probabilidad (None si no hay manos)
    confidence: float         # 0..1
    top: list                 # [(sena, probabilidad), ...] las 3 mas probables
    hands_visible: bool


@dataclass
class SignEvent:
    sign_id: str
    confidence: float
    t: float


SENSITIVITY = {  # (umbral de confianza, predicciones seguidas necesarias)
    "baja": (0.75, 4),
    "media": (0.6, 3),
    "alta": (0.45, 2),
}


class LiveRecognizer:
    def __init__(self, model, aspect=4 / 3, hop=2, smoothing=0.5, sensitivity="media", cooldown_s=0.8):
        self.model = model
        self.aspect = aspect
        self.hop = hop
        self.smoothing = smoothing
        self.cooldown_s = cooldown_s
        self.set_sensitivity(sensitivity)
        self.nothing_index = model.classes.index(config.NOTHING_ID) if config.NOTHING_ID in model.classes else None
        self._mask = None
        self.reset()

    def set_sensitivity(self, level):
        self.threshold, self.min_hits = SENSITIVITY.get(level, SENSITIVITY["media"])

    def set_allowed(self, sign_ids=None):
        """Limita las senas posibles (ej: solo letras al deletrear). None = todas."""
        if sign_ids is None:
            self._mask = None
        else:
            allowed = set(sign_ids) | {config.NOTHING_ID}
            self._mask = np.array([c in allowed for c in self.model.classes])
        self._probs = None
        self._candidate, self._hits, self._armed_block = None, 0, None

    def reset(self):
        self._frames = deque()
        self._count = 0
        self._probs = None
        self._candidate = None
        self._hits = 0
        self._armed_block = None   # sena ya confirmada que sigue en pantalla
        self._last_emit_t = -1e9
        self._last_hand_t = -1e9
        self.last_prediction = None

    def push(self, t, hands):
        """Agrega un frame. Devuelve (Prediction o None, SignEvent o None)."""
        horizon = self.model.window_s + 0.3
        self._frames.append((t, hands.image, hands.world))
        while self._frames and t - self._frames[0][0] > horizon:
            self._frames.popleft()
        if hands.any:
            self._last_hand_t = t
        self._count += 1
        if self._count % self.hop:
            return None, None

        if t - self._last_hand_t > 0.5:
            # Sin manos: no hay sena. Olvidamos el promedio para empezar limpio.
            self._probs = None
            self._candidate, self._hits, self._armed_block = None, 0, None
            self.last_prediction = Prediction(None, 0.0, [], False)
            return self.last_prediction, None

        span = self._frames[-1][0] - self._frames[0][0]
        if span < 0.5 * self.model.window_s:
            return None, None  # todavia no hay suficiente historia

        times = np.array([f[0] for f in self._frames], np.float32)
        image = np.stack([f[1] for f in self._frames])
        world = np.stack([f[2] for f in self._frames])
        feats = window_features(image, world, times, self.aspect, self.model.window_s, t_end=t)
        probs = self.model.predict_proba(feats)[0]
        if self._mask is not None and self._mask.any():
            probs = np.where(self._mask, probs, 0.0)
            probs = probs / max(probs.sum(), 1e-9)
        if self._probs is None:
            self._probs = probs
        else:
            self._probs = self.smoothing * self._probs + (1 - self.smoothing) * probs

        order = np.argsort(self._probs)[::-1]
        best = int(order[0])
        conf = float(self._probs[best])
        sign_id = self.model.classes[best]
        top = [(self.model.classes[i], float(self._probs[i])) for i in order[:3]]
        self.last_prediction = Prediction(sign_id, conf, top, True)
        return self.last_prediction, self._update_events(best, conf, t)

    def _update_events(self, best, conf, t):
        is_sign = best != self.nothing_index and conf >= self.threshold
        if not is_sign:
            self._candidate, self._hits = None, 0
            if best == self.nothing_index or conf < 0.7 * self.threshold:
                self._armed_block = None  # la persona ya solto la sena
            return None
        if best == self._candidate:
            self._hits += 1
        else:
            self._candidate, self._hits = best, 1
            if self._armed_block is not None and best != self._armed_block:
                self._armed_block = None
        if (self._hits >= self.min_hits and best != self._armed_block
                and t - self._last_emit_t >= self.cooldown_s):
            self._armed_block = best
            self._last_emit_t = t
            return SignEvent(self.model.classes[best], conf, t)
        return None
