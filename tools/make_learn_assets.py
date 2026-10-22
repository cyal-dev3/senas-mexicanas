"""
Animaciones para la seccion "Aprender" del celular.

De las grabaciones de esta PC elige, para cada sena, el clip mas representativo
(el mas parecido al promedio de su sena) y guarda solo las posiciones de las
manos, cuadro por cuadro. La app las dibuja como un esqueleto animado.

    python tools/make_learn_assets.py [salida.json]

Por defecto escribe assets/learn_clips.json (no se sube a git: sale de las
grabaciones de las personas). Gradle lo copia a las dos apps de Android.
"""

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from miratek import config  # noqa: E402
from miratek.dataset import DatasetStore  # noqa: E402
from miratek.features import window_features  # noqa: E402

FPS = 15
DEFAULT_OUT = ROOT / "assets" / "learn_clips.json"


def pick_clip(clips):
    """El clip mas cercano al promedio de su sena (entre los que tienen manos casi siempre)."""
    good = [c for c in clips if np.isfinite(c.image[:, :, 0, 0]).any(axis=1).mean() >= 0.85] or clips
    feats = np.stack([window_features(c.image, c.world, c.t, c.aspect, config.CLIP_SECONDS) for c in good])
    scale = feats.std(axis=0) + 1e-3
    center = feats.mean(axis=0)
    return good[int(np.argmin((((feats - center) / scale) ** 2).sum(axis=1)))]


def frames_of(clip):
    t = clip.t - clip.t[0]
    steps = np.arange(0, t[-1] + 1e-6, 1.0 / FPS)
    frames = []
    for ts in steps:
        i = int(np.argmin(np.abs(t - ts)))
        frame = []
        for slot in (0, 1):
            pts = clip.image[i, slot, :, :2].astype(np.float64)  # en float32, 0.333 se imprime con 16 decimales
            frame.append(None if not np.isfinite(pts).all() else np.round(pts, 3).tolist())
        frames.append(frame)
    return frames


def main(out=DEFAULT_OUT):
    store = DatasetStore(config.user_data_dir() / "datos")
    names = store.signer_names()
    by_sign = {}
    for ref in store.list_clips():
        by_sign.setdefault(ref.sign_id, []).append(ref)
    signs = {}
    for sign_id, refs in sorted(by_sign.items()):
        clips = [store.load(r) for r in refs]
        clips = [c for c in clips if len(c.t) >= 8]
        if not clips:
            continue
        clip = pick_clip(clips)
        frames = frames_of(clip)
        visible = [i for i, f in enumerate(frames) if f[0] or f[1]]
        signs[sign_id] = {
            "signer": names.get(clip.signer_id, clip.signer_id),
            "aspect": round(float(clip.aspect), 4),
            "cover": visible[len(visible) // 2] if visible else 0,
            "frames": frames,
        }
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"version": 1, "fps": FPS, "signs": signs}, separators=(",", ":")), encoding="utf-8")
    print(f"Animaciones de {len(signs)} señas -> {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return out


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUT)
