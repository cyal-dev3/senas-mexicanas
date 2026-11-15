from pathlib import Path

import numpy as np

from miratek import config, synthetic
from miratek.features import PALM, window_features
from miratek.hands import RIGHT
from tools import import_public as ip


def _hand(seed=0):
    rng = np.random.default_rng(seed)
    image, world, _ = synthetic.generate_clip(synthetic.random_sign(rng, 1), synthetic.SynthSigner(seed=seed), rng)
    return image[10, RIGHT], world[10, RIGHT]


def test_file_names():
    assert ip.parse_dynamic(Path("S7-K-frontal-4.mp4")) == (7, "letra_k")
    assert ip.parse_dynamic(Path("S19-Ñ-Frontal.1.mp4")) == (19, "letra_enie")
    assert ip.parse_dynamic(Path("S3-Z-lateral-2.mp4")) == (3, "letra_z")
    assert ip.parse_dynamic(Path("otro.mp4")) is None
    assert ip.parse_static(Path("lsm-abc-B/train/N/S4-N-1-23.jpg")) == (4, "letra_n")
    assert ip.parse_static(Path("lsm-abc-B/train/otra/S4-N-1-23.jpg")) is None


def test_place_puts_the_hand_where_asked():
    image, _ = _hand()
    close_up = image.copy()
    close_up[:, :2] = (image[:, :2] - image[0, :2]) * 4 + 0.5   # la mano sola y de cerca, foto cuadrada
    out = ip.place(close_up[None], 1.0, (0.4, 0.55, 0.11))[0]
    xy = np.stack([out[:, 0] * ip.ASPECT, out[:, 1]], axis=-1)
    assert np.allclose(xy[0], (0.4, 0.55), atol=1e-5)
    assert abs(np.linalg.norm(xy[PALM] - xy[0], axis=-1).mean() - 0.11) < 1e-5


def test_photo_becomes_a_held_letter():
    image, world = _hand()
    img, wld, t = ip.hold_still(image, world, np.random.default_rng(0))
    assert abs(t[-1] - config.CLIP_SECONDS) < 0.1 and img.shape == (len(t), 21, 3) == wld.shape
    assert 0 < np.abs(img - image).max() < 0.02   # tiembla un poco, no se va
    feats = window_features(ip.to_slots(img, RIGHT), ip.to_slots(wld, RIGHT), t, ip.ASPECT, config.CLIP_SECONDS)
    assert np.isfinite(feats).all() and feats.any()


def test_best_window_follows_the_movement():
    t = np.arange(120) / 30.0   # 4 s de video; la mano solo se mueve en el ultimo tramo
    image = np.zeros((120, 21, 3), np.float32) + 0.5
    image[70:110, :, 0] += np.linspace(0, 0.3, 40)[:, None]
    image[110:, :, 0] += 0.3
    keep = ip.best_window(image, t)
    assert keep.start <= 70 and keep.stop >= 110
    assert t[keep][-1] - t[keep][0] <= config.CLIP_SECONDS + 1e-6
