"""
Data augmentation: variaciones realistas de cada clip para que el modelo
aprenda mejor con pocos datos.

A diferencia de "ruido en cada numero", aqui simulamos cosas que de verdad
pasan frente a una camara:
  - La persona esta mas cerca o mas lejos (escala).
  - Esta mas a la izquierda, derecha, arriba o abajo (traslacion).
  - La camara esta un poco chueca (giro).
  - Hace la sena mas rapido o mas lento (velocidad).
  - Empieza la sena un poco antes o despues (ventana corrida).
  - MediaPipe pierde la mano en algunos frames.

Las variaciones se aplican SOLO al entrenar, nunca a los datos de examen.
"""

import numpy as np

from .features import _nanmean


def augment_clip(image, world, t, aspect, rng):
    """Devuelve (image, world, t, t_end) con variaciones aleatorias."""
    image = np.array(image, dtype=np.float32, copy=True)
    world = np.array(world, dtype=np.float32, copy=True)
    t = np.asarray(t, np.float32)

    # Velocidad: la misma sena, un poco mas rapida o lenta
    speed = rng.uniform(0.85, 1.18)
    t_new = (t - t[0]) / speed

    # Camara: escala, giro y traslacion (en coordenadas cuadradas)
    x = image[..., 0] * aspect
    y = image[..., 1]
    cx = _nanmean(x[:, :, 0].ravel(), axis=0)
    cy = _nanmean(y[:, :, 0].ravel(), axis=0)
    if not np.isfinite(cx):
        cx, cy = aspect / 2, 0.5
    theta = rng.uniform(-0.14, 0.14)  # ~8 grados
    scale = rng.uniform(0.82, 1.18)  # cerca o lejos (tambien celulares)
    dx, dy = rng.uniform(-0.09, 0.09, size=2)
    c, s = np.cos(theta), np.sin(theta)
    xc, yc = x - cx, y - cy
    image[..., 0] = ((c * xc - s * yc) * scale + cx + dx) / aspect
    image[..., 1] = (s * xc + c * yc) * scale + cy + dy
    image[..., 2] *= scale
    wx, wy = world[..., 0].copy(), world[..., 1].copy()
    world[..., 0] = c * wx - s * wy
    world[..., 1] = s * wx + c * wy

    # Temblor pequeno (como el ruido normal de MediaPipe)
    image[..., :2] += rng.normal(0, 0.002, image[..., :2].shape).astype(np.float32)
    world += rng.normal(0, 0.0015, world.shape).astype(np.float32)

    # Perdidas de deteccion en algunos frames
    drop = rng.random((len(t), 2)) < 0.05
    image[drop] = np.nan
    world[drop] = np.nan

    # Ventana corrida: empezar/terminar un poco antes o despues
    t_end = float(t_new[-1] + rng.uniform(-0.4, 0.3))
    return image, world, t_new, t_end
