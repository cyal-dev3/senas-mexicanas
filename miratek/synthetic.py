"""
Senas SINTETICAS: manos falsas generadas con matematicas.

No sirven para reconocer LSM de verdad. Sirven para:
  - Probar todo el sistema (grabar, entrenar, reconocer) sin camara.
  - El modo demostracion de la app (python app.py --demo).

Cada sena sintetica tiene una forma de mano (que tan doblado esta cada dedo),
un lugar frente al cuerpo y un movimiento (arriba-abajo, circulo, etc.).
Cada "persona" sintetica cambia un poco el tamano, la posicion y la velocidad.
"""

import zlib
from dataclasses import dataclass

import numpy as np

from .hands import LEFT, RIGHT

# ---- Mano canonica (derecha, dedos hacia arriba, palma hacia la camara) ----
# Unidades: largo de la palma = 1. x a la derecha, y hacia abajo, z hacia el fondo.
_MCP = {  # base de cada dedo: (indice de landmark, posicion, direccion extendida, segmentos)
    "thumb": (1, (-0.30, -0.18, -0.05), (-0.60, -0.80, 0.0), (0.32, 0.28, 0.24)),
    "index": (5, (-0.24, -0.92, 0.0), (-0.12, -1.0, 0.0), (0.42, 0.26, 0.21)),
    "middle": (9, (-0.02, -1.00, 0.0), (0.0, -1.0, 0.0), (0.47, 0.29, 0.23)),
    "ring": (13, (0.18, -0.94, 0.0), (0.10, -1.0, 0.0), (0.44, 0.27, 0.21)),
    "pinky": (17, (0.36, -0.80, 0.0), (0.22, -1.0, 0.0), (0.34, 0.21, 0.19)),
}
_FINGER_ORDER = ("thumb", "index", "middle", "ring", "pinky")
_PALM_NORMAL = np.array([0.0, 0.0, -1.0])  # hacia la camara
_THUMB_ACROSS = np.array([0.7, -0.3, -0.6])
_BEND = np.array([1.4, 1.7, 1.2])  # angulos maximos de cada articulacion

PALM_METERS = 0.085  # largo tipico de una palma real


def _unit(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


def hand_shape(curls):
    """Los 21 puntos de una mano derecha con los dedos doblados segun 'curls'."""
    pts = np.zeros((21, 3))
    for name, curl in zip(_FINGER_ORDER, curls):
        base_idx, base, direction, segments = _MCP[name]
        d0 = _unit(direction)
        bend_to = _unit(_THUMB_ACROSS) if name == "thumb" else _PALM_NORMAL
        angles = np.cumsum(_BEND * (0.55 if name == "thumb" else 1.0) * curl)
        p = np.array(base, dtype=np.float64)
        pts[base_idx] = p
        for k, (seg, ang) in enumerate(zip(segments, angles)):
            p = p + seg * _unit(np.cos(ang) * d0 + np.sin(ang) * bend_to)
            pts[base_idx + 1 + k] = p
    return pts


def _rotation(roll, yaw, pitch):
    cr, sr = np.cos(roll), np.sin(roll)
    cy, sy = np.cos(yaw), np.sin(yaw)
    cp, sp = np.cos(pitch), np.sin(pitch)
    rz = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    return rz @ ry @ rx


@dataclass
class SynthSign:
    curls: tuple            # 5 numeros de 0 (extendido) a 1 (doblado)
    roll: float             # giro de la mano (radianes)
    yaw: float
    location: tuple         # (x, y) de la muneca en la imagen, de 0 a 1
    motion: str             # static, updown, side, circle, forward, tap, wave
    amplitude: float        # tamano del movimiento (en palmas)
    cycles: float           # cuantas veces se repite el movimiento
    two_hands: bool = False
    is_nothing: bool = False


@dataclass
class SynthSigner:
    size: float = 1.0          # tamano de la mano
    distance: float = 1.0      # que tan cerca esta de la camara
    offset: tuple = (0.0, 0.0)
    speed: float = 1.0
    amplitude: float = 1.0
    roll: float = 0.0
    curl_noise: float = 0.05
    left_handed: bool = False
    seed: int = 0


MOTIONS = ("static", "updown", "side", "circle", "forward", "tap", "wave")


def random_sign(rng, index=0):
    """Inventa una sena sintetica distinta a las demas."""
    curls = tuple(float(c) for c in rng.choice([0.0, 0.15, 0.85, 1.0], size=5))
    return SynthSign(
        curls=curls,
        roll=float(rng.uniform(-0.6, 0.6)),
        yaw=float(rng.uniform(-0.5, 0.5)),
        location=(float(rng.uniform(0.45, 0.75)), float(rng.uniform(0.3, 0.7))),
        motion=MOTIONS[index % len(MOTIONS)],
        amplitude=float(rng.uniform(0.5, 1.1)),
        cycles=float(rng.choice([1.0, 1.5, 2.0])),
        two_hands=bool(rng.random() < 0.3),
    )


def sign_for_id(sign_id):
    """Sena sintetica fija para cada id (siempre la misma, para el modo demo)."""
    if sign_id == "nada":
        return SynthSign((0.3,) * 5, 0.0, 0.0, (0.6, 0.85), "static", 0.3, 1.0, is_nothing=True)
    seed = zlib.crc32(sign_id.encode())
    return random_sign(np.random.default_rng(seed), index=seed)


def random_signer(rng):
    return SynthSigner(
        size=float(rng.uniform(0.85, 1.15)),
        distance=float(rng.uniform(0.85, 1.2)),
        offset=(float(rng.uniform(-0.05, 0.05)), float(rng.uniform(-0.05, 0.05))),
        speed=float(rng.uniform(0.8, 1.25)),
        amplitude=float(rng.uniform(0.8, 1.2)),
        roll=float(rng.uniform(-0.12, 0.12)),
        left_handed=bool(rng.random() < 0.15),
        seed=int(rng.integers(1 << 30)),
    )


def _motion_offset(motion, phase, amplitude, cycles):
    """Desplazamiento (dx, dy, escala) de la muneca en la fase 0..1 de la sena."""
    w = 2 * np.pi * cycles * phase
    if motion == "updown":
        return 0.0, amplitude * np.sin(w), 1.0
    if motion == "side":
        return amplitude * np.sin(w), 0.0, 1.0
    if motion == "circle":
        return amplitude * np.cos(w) - amplitude, amplitude * np.sin(w), 1.0
    if motion == "forward":
        return 0.0, 0.0, 1.0 + 0.25 * amplitude * np.sin(w)
    if motion == "tap":
        return 0.0, 0.6 * amplitude * abs(np.sin(2 * w)), 1.0
    if motion == "wave":
        return 0.3 * amplitude * np.sin(2 * w), 0.0, 1.0
    return 0.0, 0.0, 1.0


def _pose_hand(curls, roll, yaw, wrist_xy, palm_px, aspect, mirror):
    """Coloca una mano en la imagen. Devuelve (image (21,3), world (21,3))."""
    shape = hand_shape(curls)
    if mirror:
        shape[:, 0] *= -1  # mano izquierda = espejo de la derecha
    rot = _rotation(-roll if mirror else roll, -yaw if mirror else yaw, 0.15)
    local = shape @ rot.T
    iso = local * palm_px
    image = np.empty((21, 3))
    image[:, 0] = (wrist_xy[0] * aspect + iso[:, 0]) / aspect
    image[:, 1] = wrist_xy[1] + iso[:, 1]
    image[:, 2] = iso[:, 2] / aspect
    center = local[[0, 5, 9, 13, 17]].mean(axis=0)
    world = (local - center) * PALM_METERS
    return image.astype(np.float32), world.astype(np.float32)


class Performer:
    """Una persona sintetica que hace senas a lo largo del tiempo."""

    def __init__(self, signer, aspect=4 / 3, rng=None):
        self.signer = signer
        self.aspect = aspect
        self.rng = rng or np.random.default_rng(signer.seed)
        self._sign_curls = {}

    def hands_at(self, sign, t, sign_start, sign_duration):
        """Manos en el instante t para una sena que empieza en sign_start."""
        s = self.signer
        rng = self.rng
        palm_px = 0.13 * s.size * s.distance
        phase = (t - sign_start) / sign_duration
        dominant = LEFT if s.left_handed else RIGHT
        mirror_dom = s.left_handed

        # Reposo: manos abajo, un poco relajadas
        rest = (0.62 + s.offset[0], 0.95 + s.offset[1])
        if mirror_dom:
            rest = (1.0 - rest[0], rest[1])
        image = np.full((2, 21, 3), np.nan, np.float32)
        world = np.full((2, 21, 3), np.nan, np.float32)

        if sign.is_nothing or phase < 0 or phase > 1:
            # Movimientos naturales que NO son senas
            drift = 0.03 * np.sin(t * 1.3 + s.seed % 7)
            loc = (rest[0] + drift, rest[1] + 0.02 * np.cos(t * 0.9))
            if sign.is_nothing and 0 <= phase <= 1 and (s.seed + int(sign_start * 10)) % 3 == 0:
                loc = (0.55 + 0.04 * np.sin(t * 7), 0.28 + 0.02 * np.cos(t * 5))  # rascarse la cara
            if loc[1] < 0.98 or rng.random() < 0.5:
                curls = tuple(np.clip(np.array((0.3, 0.35, 0.4, 0.45, 0.5)) + 0.05 * np.sin(t), 0, 1))
                img, wld = _pose_hand(curls, 0.2 + s.roll, 0.1, loc, palm_px, self.aspect, mirror_dom)
                image[dominant], world[dominant] = img, wld
            return self._noise(image, world)

        # Transicion suave: 20% ir al lugar, 60% movimiento, 20% regresar
        target = (sign.location[0] + s.offset[0], sign.location[1] + s.offset[1])
        if mirror_dom:
            target = (1.0 - target[0], target[1])
        if phase < 0.2:
            k = phase / 0.2
            base = (rest[0] + (target[0] - rest[0]) * k, rest[1] + (target[1] - rest[1]) * k)
            move_phase = 0.0
        elif phase > 0.8:
            k = (phase - 0.8) / 0.2
            base = (target[0] + (rest[0] - target[0]) * k, target[1] + (rest[1] - target[1]) * k)
            move_phase = 1.0
        else:
            base = target
            move_phase = (phase - 0.2) / 0.6

        dx, dy, scale = _motion_offset(sign.motion, move_phase, sign.amplitude * s.amplitude, sign.cycles)
        if mirror_dom:
            dx = -dx
        wrist = (base[0] + dx * palm_px / self.aspect, base[1] + dy * palm_px)
        curls = self._curls(sign)
        img, wld = _pose_hand(curls, sign.roll + s.roll, sign.yaw, wrist, palm_px * scale,
                              self.aspect, mirror_dom)
        image[dominant], world[dominant] = img, wld

        if sign.two_hands:
            other = 1 - dominant
            wrist2 = (1.0 - wrist[0] + 0.02, wrist[1] + 0.03)
            img2, wld2 = _pose_hand(curls, sign.roll + s.roll, sign.yaw, wrist2, palm_px * scale,
                                    self.aspect, not mirror_dom)
            image[other], world[other] = img2, wld2
        return self._noise(image, world)

    def _curls(self, sign):
        key = id(sign)
        if key not in self._sign_curls:
            noise = self.rng.normal(0, self.signer.curl_noise, 5)
            self._sign_curls[key] = tuple(np.clip(np.array(sign.curls) + noise, 0, 1))
        return self._sign_curls[key]

    def _noise(self, image, world):
        image = image + self.rng.normal(0, 0.0015, image.shape).astype(np.float32)
        world = world + self.rng.normal(0, 0.0015, world.shape).astype(np.float32)
        return image, world


def fill_store(store, n_signers=3, n_signs=5, clips_per_sign=8, seed=0, with_nothing=True, sign_ids=None):
    """Llena un almacen con grabaciones sinteticas de varias personas (pruebas y demo)."""
    rng = np.random.default_rng(seed)
    if sign_ids is not None:
        signs = {sid: sign_for_id(sid) for sid in sign_ids}
    else:
        signs = {f"sena{i}": random_sign(rng, i) for i in range(n_signs)}
        if with_nothing:
            signs["nada"] = sign_for_id("nada")
    signers = [random_signer(rng) for _ in range(n_signers)]
    for k, signer in enumerate(signers):
        signer_id = f"persona-{k}"
        store.set_signer_name(signer_id, f"Persona {k + 1}")
        for sign_id, sign in signs.items():
            for _ in range(clips_per_sign):
                image, world, t = generate_clip(sign, signer, rng)
                store.save_clip(sign_id, signer_id, image, world, t, 4 / 3)
    return signs, signers


def generate_clip(sign, signer, rng, duration=2.0, fps=30.0, aspect=4 / 3):
    """Un clip sintetico como los que graba la app: (image, world, t)."""
    performer = Performer(signer, aspect, rng)
    n = int(round(duration * fps))
    t = (np.arange(n) / fps + rng.normal(0, 0.002, n)).astype(np.float32)
    t = np.maximum.accumulate(t)
    start = float(rng.uniform(0.1, 0.45))
    length = float(np.clip(1.25 / signer.speed, 0.9, 1.5))
    image = np.empty((n, 2, 21, 3), np.float32)
    world = np.empty((n, 2, 21, 3), np.float32)
    for i, ti in enumerate(t):
        image[i], world[i] = performer.hands_at(sign, float(ti), start, length)
    # A veces MediaPipe pierde la mano un frame
    drop = rng.random(n) < 0.03
    image[drop] = np.nan
    world[drop] = np.nan
    return image, world, t
