"""
De frames a numeros: la parte mas importante para que el modelo funcione
con cualquier persona.

Una sena dura mas o menos 1-2 segundos. Tomamos una VENTANA de frames
(ej: los ultimos 2 segundos) y la convertimos en un vector de 728 numeros.
Esta misma funcion se usa al ENTRENAR y al RECONOCER EN VIVO, asi nunca
quedan desincronizados.

=== QUE NORMALIZAMOS Y POR QUE ===
  - Tiempo: la ventana se remuestrea a 16 pasos fijos, sin importar si la
    camara da 15 o 30 frames por segundo.
  - Forma de la mano: puntos 3D relativos a la muneca y divididos entre el
    tamano de la palma. Asi da igual si la mano es chica o grande, o si
    esta cerca o lejos de la camara.
  - Movimiento: trayectoria de la muneca relativa a su posicion promedio,
    medida en "palmas". Da igual en que parte de la imagen estes.
  - Mano dominante: si la sena la hace la mano izquierda, la reflejamos como
    espejo. Asi el modelo sirve para personas zurdas y diestras.
"""


import numpy as np

from .hands import LEFT, RIGHT

FEATURE_VERSION = 1
N_STEPS = 16        # Pasos de tiempo dentro de la ventana
N_SEGMENTS = 4      # Para promedios por "etapa" de la sena (inicio ... fin)
MAX_GAP = 0.25      # Huecos sin mano mas cortos que esto se rellenan
PALM = [5, 9, 13, 17]
FEATURE_SIZE = 2 * N_SEGMENTS * 60 + 2 * 60 + N_STEPS * 4 + N_STEPS * 2 + 2 * N_SEGMENTS * 2 \
    + N_SEGMENTS * 2 + 2 * N_SEGMENTS
DEFAULT_PALM = 0.12  # Tamano de palma de respaldo (en alturas de imagen)


def _nanmean(a, axis):
    """Promedio ignorando NaN; devuelve NaN donde no hay ningun dato."""
    mask = ~np.isnan(a)
    count = mask.sum(axis=axis)
    total = np.where(mask, a, 0.0).sum(axis=axis)
    with np.errstate(invalid="ignore", divide="ignore"):
        return total / count


def _nanmedian0(a):
    """Mediana a lo largo del eje 0 ignorando NaN (np.nanmedian es muy lento aqui)."""
    s = np.sort(a, axis=0)  # los NaN quedan al final
    n = (~np.isnan(a)).sum(axis=0)
    lo = np.take_along_axis(s, np.maximum((n - 1) // 2, 0)[None], axis=0)[0]
    hi = np.take_along_axis(s, np.maximum(n // 2, 0)[None], axis=0)[0]
    return np.where(n > 0, (lo + hi) / 2.0, np.nan)


def _resample_slot(t, values, present, grid):
    """Valores de UNA mano en los instantes 'grid' (interpolando)."""
    out = np.full((len(grid), values.shape[1]), np.nan, dtype=np.float64)
    tp = t[present]
    if len(tp) == 0:
        return out, np.zeros(len(grid), bool)
    vp = values[present].astype(np.float64)
    j = np.searchsorted(tp, grid, side="left")
    jn = np.minimum(j, len(tp) - 1)
    jp = np.maximum(j - 1, 0)
    has_next = j < len(tp)
    has_prev = j > 0
    dn = np.where(has_next, tp[jn] - grid, np.inf)
    dp = np.where(has_prev, grid - tp[jp], np.inf)
    use_n = dn <= MAX_GAP
    use_p = dp <= MAX_GAP
    both = use_n & use_p
    if both.any():
        w = (dp[both] / (dp[both] + dn[both]))[:, None]
        out[both] = vp[jp[both]] * (1 - w) + vp[jn[both]] * w
    only_n = use_n & ~use_p
    out[only_n] = vp[jn[only_n]]
    only_p = use_p & ~use_n
    out[only_p] = vp[jp[only_p]]
    return out, use_n | use_p


def resample_window(image, world, t, window_s, t_end=None):
    """Remuestrea la ventana [t_end - window_s, t_end] a N_STEPS pasos."""
    t = np.asarray(t, np.float64)
    if t_end is None:
        t_end = float(t[-1])
    grid = np.linspace(t_end - window_s, t_end, N_STEPS)
    n = len(t)
    img = np.full((N_STEPS, 2, 21, 3), np.nan)
    wld = np.full((N_STEPS, 2, 21, 3), np.nan)
    present = np.zeros((N_STEPS, 2), bool)
    image = np.asarray(image).reshape(n, 2, 63)
    world = np.asarray(world).reshape(n, 2, 63)
    for s in (LEFT, RIGHT):
        vals = np.concatenate([image[:, s], world[:, s]], axis=1)
        mask = ~np.isnan(vals[:, 0]) & ~np.isnan(vals[:, 63])
        out, ok = _resample_slot(t, vals, mask, grid)
        img[:, s] = out[:, :63].reshape(N_STEPS, 21, 3)
        wld[:, s] = out[:, 63:].reshape(N_STEPS, 21, 3)
        present[:, s] = ok
    return img, wld, present


def _palm_size(points):
    """Tamano de la palma: distancia promedio de la muneca a la base de los dedos."""
    return np.linalg.norm(points[..., PALM, :] - points[..., :1, :], axis=-1).mean(axis=-1)


def _segment_mean(a):
    """(N_STEPS, ...) -> (N_SEGMENTS, ...) promediando cada etapa."""
    seg = a.reshape((N_SEGMENTS, N_STEPS // N_SEGMENTS) + a.shape[1:])
    return _nanmean(seg, axis=1)


def features_from_resampled(img, wld, present, aspect, mirror=None):
    """Calcula el vector de 728 numeros a partir de la ventana remuestreada.

    mirror: True si la persona hace las senas con la mano izquierda (se refleja
    como espejo para que la mano dominante quede a la derecha), False si con la
    derecha, None para adivinarlo con la mano que mas aparece y se mueve. Lo
    mejor es decirlo: con la otra mano en reposo a la vista, adivinar falla.
    """
    xy = np.stack([img[..., 0] * aspect, img[..., 1]], axis=-1)  # coords "cuadradas"
    wld = wld.copy()
    present = present.copy()

    # --- Mano dominante: la que aparece mas y se mueve mas va a la derecha ---
    wrist = xy[:, :, 0, :]
    steps = np.linalg.norm(np.diff(wrist, axis=0), axis=-1)
    palm_px = _palm_size(xy)
    scale = _nanmean(_nanmedian0(palm_px), axis=0)
    if not np.isfinite(scale) or scale <= 1e-6:
        scale = DEFAULT_PALM
    path = np.nansum(steps, axis=0) / scale
    energy = present.sum(axis=0) * (1.0 + path)
    do_mirror = (energy[LEFT] > 1.2 * energy[RIGHT] + 1e-6) if mirror is None else bool(mirror)
    if do_mirror:
        xy = xy[:, ::-1].copy()
        xy[..., 0] = aspect - xy[..., 0]
        wld = wld[:, ::-1].copy()
        wld[..., 0] = -wld[..., 0]
        present = present[:, ::-1].copy()
        palm_px = palm_px[:, ::-1]
        wrist = xy[:, :, 0, :]

    # --- Forma de la mano (3D, relativa a la muneca, en "palmas") ---
    palm_w = _nanmedian0(_palm_size(wld))
    palm_w = np.where(np.isfinite(palm_w) & (palm_w > 1e-6), palm_w, 1.0)
    shape = (wld[:, :, 1:, :] - wld[:, :, :1, :]) / palm_w[None, :, None, None]
    shape = shape.reshape(N_STEPS, 2, 60)
    shape_seg = _segment_mean(shape).transpose(1, 0, 2)            # (2, 4, 60)
    shape_speed = _nanmean(np.abs(np.diff(shape, axis=0)), axis=0)  # (2, 60)

    # --- Movimiento de la muneca ---
    wrist_mean = _nanmean(wrist, axis=0)                            # (2, 2)
    motion = (wrist - wrist_mean[None]) / scale                     # (16, 2, 2)
    palm_med = _nanmedian0(palm_px)
    with np.errstate(invalid="ignore", divide="ignore"):
        depth = np.log(palm_px / palm_med[None])                    # (16, 2) acercar/alejar
    center = np.array([aspect / 2.0, 0.5])
    absolute = _segment_mean((wrist - center) / scale).transpose(1, 0, 2)  # (2, 4, 2)
    inter = _segment_mean((wrist[:, RIGHT] - wrist[:, LEFT]) / scale)      # (4, 2)
    presence = _segment_mean(present.astype(np.float64)).T                 # (2, 4)

    vec = np.concatenate([
        shape_seg.ravel(), shape_speed.ravel(), motion.ravel(), depth.ravel(),
        absolute.ravel(), inter.ravel(), presence.ravel(),
    ])
    vec = np.nan_to_num(vec, nan=0.0, posinf=0.0, neginf=0.0)
    return np.clip(vec, -10.0, 10.0).astype(np.float32)


def window_features(image, world, t, aspect, window_s, t_end=None, mirror=None):
    """Vector de caracteristicas para la ventana que termina en t_end."""
    if len(t) == 0:
        return np.zeros(FEATURE_SIZE, np.float32)
    img, wld, present = resample_window(image, world, t, window_s, t_end)
    return features_from_resampled(img, wld, present, aspect, mirror)
