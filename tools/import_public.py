"""
Suma personas de conjuntos de datos PUBLICOS al almacen de grabaciones.

El modelo aprende de las manos de quienes graban; con una sola persona falla con
gente nueva. Estos dos conjuntos (CC BY 4.0) traen el abecedario de LSM hecho por
20 personas cada uno:

  - Mexican Sign Language Alphabet (static signs only), 21 letras en fotos.
    https://doi.org/10.5281/zenodo.10067509
  - Mexican Sign Language Alphabet (dynamic signs only), J K N~ Q X Z en video.
    https://doi.org/10.5281/zenodo.14689869
    Navarrete-Lopez y Lopez-Nava (CICESE).

Son fotos y videos: aqui se les pasa el MISMO detector de manos que usan las apps
y se guardan como clips normales (solo puntos de la mano, nunca imagenes), con
una "persona" por participante (zenodo-e-s01, zenodo-d-s01, ...).

    python tools/import_public.py <carpeta con los .7z ya descomprimidos> [--store CARPETA]

Por defecto escribe en el almacen de la app de PC. Se puede volver a correr: lo ya
detectado queda en <carpeta>/cache y las personas "zenodo-*" se reemplazan.
"""

import argparse
import os
import re
import sys
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from miratek import config  # noqa: E402
from miratek.dataset import DatasetStore  # noqa: E402
from miratek.features import PALM  # noqa: E402
from miratek.hands import LEFT, RIGHT  # noqa: E402

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp"}
VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
ASPECT = 4 / 3            # los clips se guardan como si vinieran de la camara de la PC
STATIC_FPS = 20.0
PREFIX = "zenodo-"
LETTER_IDS = {s.name: s.id for s in config.SIGNS if s.category == config.LETTERS}
LETTER_IDS.update({"NN": "letra_enie", "ENIE": "letra_enie", "Ñ": "letra_enie"})


# ============================================================
# Detector de manos (el mismo modelo que las apps)
# ============================================================

class Landmarker:
    """HandLandmarker de MediaPipe para fotos sueltas o para video."""

    def __init__(self, video):
        from mediapipe.tasks.python.core import base_options
        from mediapipe.tasks.python.vision import hand_landmarker
        from mediapipe.tasks.python.vision.core import image as mp_image
        from mediapipe.tasks.python.vision.core import vision_task_running_mode as running_mode

        model = config.resource_path("assets", "hand_landmarker.task").read_bytes()
        mode = running_mode.VisionTaskRunningMode
        options = hand_landmarker.HandLandmarkerOptions(
            base_options=base_options.BaseOptions(model_asset_buffer=model),
            running_mode=mode.VIDEO if video else mode.IMAGE,
            num_hands=2, min_hand_detection_confidence=0.5, min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5)
        self._lm = hand_landmarker.HandLandmarker.create_from_options(options)
        self._mp_image = mp_image
        self._video = video
        self._ts = 0

    def detect(self, bgr, dt_ms=50):
        """(etiqueta, imagen (21,3), mundo (21,3), aspecto) de la mano mas grande, o None."""
        import cv2
        rgb = cv2.cvtColor(cv2.flip(bgr, 1), cv2.COLOR_BGR2RGB)  # espejo, igual que la camara de las apps
        image = self._mp_image.Image(image_format=self._mp_image.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        if self._video:
            self._ts += int(dt_ms)
            result = self._lm.detect_for_video(image, self._ts)
        else:
            result = self._lm.detect(image)
        best = None
        for lms, world, handed in zip(result.hand_landmarks, result.hand_world_landmarks, result.handedness):
            img = np.array([[p.x, p.y, p.z] for p in lms], np.float32)
            wld = np.array([[p.x, p.y, p.z] for p in world], np.float32)
            size = float(np.linalg.norm(img[PALM, :2] - img[0, :2], axis=1).mean())
            if best is None or size > best[0]:
                best = (size, handed[0].category_name, img, wld)
        return None if best is None else best[1:] + (rgb.shape[1] / rgb.shape[0],)

    def new_video(self):
        self._ts += 2000  # el rastreo no debe seguir la mano del video anterior

    def close(self):
        self._lm.close()


# ============================================================
# Deteccion con cache (correr MediaPipe sobre miles de archivos tarda)
# ============================================================

def _cached(cache_dir, path, compute):
    key = f"{zlib.crc32(str(path).encode()):08x}-{path.stem}.npz"
    file = cache_dir / key
    if file.exists():
        try:
            with np.load(file, allow_pickle=False) as data:
                return {k: data[k] for k in data.files}
        except Exception:
            pass  # archivo a medias de una corrida interrumpida: se vuelve a calcular
    out = compute()
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = file.with_name(f"{file.stem}.{os.getpid()}.tmp.npz")
    np.savez_compressed(tmp, **out)
    os.replace(tmp, file)
    return out


def detect_photo(lm, path):
    import cv2
    bgr = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)  # imread falla con acentos en la ruta
    hit = lm.detect(bgr) if bgr is not None else None
    if hit is None:
        return {"ok": np.array(False)}
    label, img, wld, aspect = hit
    return {"ok": np.array(True), "right": np.array(label == "Right"), "image": img, "world": wld,
            "aspect": np.array(aspect)}


def detect_video(lm, path):
    import cv2
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    if not 5 <= fps <= 240:
        fps = 30.0
    lm.new_video()
    images, worlds, rights, aspect = [], [], [], ASPECT
    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        hit = lm.detect(bgr, 1000.0 / fps)
        if hit is None:
            images.append(np.full((21, 3), np.nan, np.float32))
            worlds.append(np.full((21, 3), np.nan, np.float32))
        else:
            label, img, wld, aspect = hit
            images.append(img)
            worlds.append(wld)
            rights.append(label == "Right")
    cap.release()
    n = len(images)
    if n == 0 or not rights:
        return {"ok": np.array(False)}
    return {"ok": np.array(True), "right": np.array(np.mean(rights) >= 0.5), "image": np.stack(images),
            "world": np.stack(worlds), "aspect": np.array(aspect), "t": np.arange(n) / fps}


# ============================================================
# De la deteccion a un clip como los de la app
# ============================================================

def reference_placements(store):
    """Donde y de que tamano aparece la mano en las grabaciones propias de letras.

    Las fotos publicas son de la mano sola y de cerca; en la app la persona esta a
    un brazo de distancia. Cada clip publico se recoloca con una posicion y un
    tamano tomados de aqui (por casilla), para que se vea como uno propio.
    Devuelve {casilla: [(x cuadrada, y, palma), ...]}.
    """
    out = {LEFT: [], RIGHT: []}
    for ref in store.list_clips():
        if ref.signer_id.startswith(PREFIX) or config.category_of(ref.sign_id) != config.LETTERS:
            continue
        clip = store.load(ref)
        for slot in (LEFT, RIGHT):
            pts = clip.image[:, slot]
            seen = ~np.isnan(pts[:, 0, 0])
            if seen.mean() < 0.7 or (~np.isnan(clip.image[:, 1 - slot, 0, 0])).mean() > 0.2:
                continue
            xy = np.stack([pts[seen][..., 0] * clip.aspect, pts[seen][..., 1]], axis=-1)
            palm = np.linalg.norm(xy[:, PALM] - xy[:, :1], axis=-1).mean(axis=-1)
            out[slot].append((float(np.median(xy[:, 0, 0])), float(np.median(xy[:, 0, 1])), float(np.median(palm))))
    fallback = {LEFT: [(0.9, 0.55, 0.11)], RIGHT: [(0.4, 0.55, 0.11)]}
    return {slot: out[slot] or fallback[slot] for slot in out}


def place(image, src_aspect, target):
    """Mueve y escala los puntos (T, 21, 3) para que la muneca y la palma queden como 'target'."""
    x = image[..., 0] * src_aspect
    y = image[..., 1]
    palm = np.linalg.norm(np.stack([x[:, PALM] - x[:, :1], y[:, PALM] - y[:, :1]], axis=-1), axis=-1).mean(axis=-1)
    wx, wy, size = np.nanmedian(x[:, 0]), np.nanmedian(y[:, 0]), np.nanmedian(palm)
    tx, ty, tsize = target
    k = tsize / size
    out = image.copy()
    out[..., 0] = ((x - wx) * k + tx) / ASPECT
    out[..., 1] = (y - wy) * k + ty
    out[..., 2] = image[..., 2] * k
    return out.astype(np.float32)


def hold_still(image, world, rng, seconds=config.CLIP_SECONDS):
    """Una foto convertida en un clip de letra sostenida: la mano casi quieta, con el
    temblor natural de quien la mantiene (un vaiven lento) y el ruido del detector."""
    n = int(round(seconds * STATIC_FPS))
    t = np.arange(n) / STATIC_FPS
    drift = np.cumsum(rng.normal(0, 0.0012, (n, 1, 2)), axis=0)
    drift -= drift.mean(axis=0)
    img = np.repeat(image[None], n, axis=0).astype(np.float32)
    img[..., :2] += (drift + rng.normal(0, 0.001, (n, 21, 2))).astype(np.float32)
    wld = np.repeat(world[None], n, axis=0) + rng.normal(0, 0.001, (n, 21, 3))
    return img, wld.astype(np.float32), t.astype(np.float32)


def best_window(image, t, seconds=config.CLIP_SECONDS):
    """Los 'seconds' del video donde la mano se ve mas y se mueve mas."""
    if t[-1] - t[0] <= seconds:
        return slice(0, len(t))
    seen = ~np.isnan(image[:, 0, 0])
    speed = np.zeros(len(t))
    step = np.linalg.norm(np.diff(image[:, 0, :2], axis=0), axis=-1)
    speed[1:] = np.nan_to_num(step, nan=0.0)
    score = seen * (0.02 + speed)
    best, best_score = 0, -1.0
    for i in range(len(t)):
        j = int(np.searchsorted(t, t[i] + seconds, side="right"))
        if t[min(j, len(t)) - 1] - t[i] < seconds - 0.2:
            break
        total = float(score[i:j].sum())
        if total > best_score:
            best, best_score = i, total
    return slice(best, int(np.searchsorted(t, t[best] + seconds, side="right")))


def to_slots(points, slot):
    """(T, 21, 3) de una mano -> (T, 2, 21, 3) con la otra casilla vacia."""
    out = np.full((len(points), 2, 21, 3), np.nan, np.float32)
    out[:, slot] = points
    return out


# ============================================================
# Como estan ordenados los archivos de cada conjunto
# ============================================================

def parse_dynamic(path):
    """S<persona>-<letra>-<vista>-<repeticion>.mp4 -> (persona, id de la sena).

    Algunos archivos usan un punto antes de la repeticion (S19-Q-Frontal.1.mp4).
    """
    m = re.match(r"^S(\d+)-(.+?)-[A-Za-z]+[-.]\d+$", path.stem)
    if not m:
        return None
    sign = LETTER_IDS.get(m.group(2).upper())
    return (int(m.group(1)), sign) if sign else None


def parse_static(path):
    """Las fotos van en .../<train|test>/<letra>/S<persona>-... -> (persona, id de la sena)."""
    m = re.match(r"^S(\d+)\D", path.stem)
    sign = LETTER_IDS.get(path.parent.name.upper())
    return (int(m.group(1)), sign) if m and sign else None


# ============================================================
# Importar
# ============================================================

def _rng_for(path):
    return np.random.default_rng(zlib.crc32(path.name.encode()))


def video_clip(det, slot, targets):
    """Clip (image, world, t) de un video ya detectado, o None si casi no se ve la mano."""
    image, world, t = det["image"], det["world"], det["t"].astype(np.float64)
    step = max(1, int(round((len(t) - 1) / max(t[-1] - t[0], 1e-6) / 30.0)))  # 60 fps -> 30 fps
    image, world, t = image[::step], world[::step], t[::step]
    keep = best_window(image, t)
    image, world, t = image[keep], world[keep], t[keep] - t[keep][0]
    seen = ~np.isnan(image[:, 0, 0])
    if seen.mean() < config.MIN_HAND_FRACTION or seen.sum() < 5:
        return None
    first = int(np.argmax(seen))
    image, world, t = image[first:], world[first:], t[first:] - t[first]
    missing = config.CLIP_SECONDS - t[-1]
    if missing > 0.05:
        # Video corto: antes de la sena la mano ya estaba ahi, quieta (como al deletrear)
        n = int(np.ceil(missing * 30.0))
        image = np.concatenate([np.repeat(image[:1], n, axis=0), image])
        world = np.concatenate([np.repeat(world[:1], n, axis=0), world])
        t = np.concatenate([np.arange(n) / 30.0, t + n / 30.0])
    return place(image, float(det["aspect"]), targets), world, t.astype(np.float32)


def photo_clip(det, slot, targets, rng):
    image = place(det["image"][None], float(det["aspect"]), targets)[0]
    return hold_still(image, det["world"], rng)


def collect(root, cache_dir, per_letter):
    """Detecta las manos de todos los archivos utiles. Devuelve {persona: [(sena, tipo, ruta, deteccion)]}."""
    videos, photos = [], {}
    for path in sorted(root.rglob("*")):
        ext = path.suffix.lower()
        if ext in VIDEO_EXT and parse_dynamic(path):
            videos.append(path)
        elif ext in IMAGE_EXT and parse_static(path):
            photos.setdefault(parse_static(path) + (path.parent.parent.parent.name,), []).append(path)
    # De las fotos, solo unas cuantas por persona, letra y grupo, repartidas a lo largo de la sesion
    chosen = []
    for key, paths in sorted(photos.items()):
        idx = np.unique(np.linspace(0, len(paths) - 1, min(per_letter, len(paths))).round().astype(int))
        chosen += [paths[i] for i in idx]
    print(f"{len(videos)} videos y {len(chosen)} fotos (de {sum(map(len, photos.values()))})")
    people = {}
    lm_video, lm_photo = Landmarker(video=True), Landmarker(video=False)
    try:
        for kind, paths, lm, detect, parse in (("d", videos, lm_video, detect_video, parse_dynamic),
                                               ("e", chosen, lm_photo, detect_photo, parse_static)):
            for i, path in enumerate(paths):
                det = _cached(cache_dir / kind, path, lambda: detect(lm, path))
                if bool(det["ok"]):
                    person, sign = parse(path)
                    people.setdefault(f"{PREFIX}{kind}-s{person:02d}", []).append((sign, kind, path, det))
                if i % 200 == 199:
                    print(f"  {'videos' if kind == 'd' else 'fotos'}: {i + 1} de {len(paths)}", flush=True)
    finally:
        lm_video.close()
        lm_photo.close()
    return people


def import_public(root, store, per_letter=3):
    root = Path(root)
    people = collect(root, root / "cache", per_letter)
    placements = reference_placements(store)
    for signer in list(store.signer_names()) + [d.name for d in store.clips_dir.iterdir() if d.is_dir()]:
        if signer.startswith(PREFIX):
            store.delete_signer(signer)
    total = skipped = 0
    for signer, items in sorted(people.items()):
        # Cada persona hace todo con la misma mano: se decide por mayoria, porque el
        # detector a veces confunde izquierda y derecha cuando solo ve la mano.
        right = np.mean([bool(det["right"]) for _, _, _, det in items]) >= 0.5
        slot = RIGHT if right else LEFT
        for sign, kind, path, det in items:
            rng = _rng_for(path)
            target = placements[slot][int(rng.integers(len(placements[slot])))]
            clip = video_clip(det, slot, target) if kind == "d" else photo_clip(det, slot, target, rng)
            if clip is None:
                skipped += 1
                continue
            image, world, t = clip
            store.save_clip(sign, signer, to_slots(image, slot), to_slots(world, slot), t, ASPECT,
                            mirror=not right)
            total += 1
        kind_name = "abecedario en video" if "-d-" in signer else "abecedario en fotos"
        store.set_signer_name(signer, f"Zenodo {signer[-3:].upper()} ({kind_name})")
    print(f"{total} clips de {len(people)} personas guardados en {store.root} ({skipped} sin mano visible)")
    return total


def main():
    parser = argparse.ArgumentParser(description="Suma personas de conjuntos publicos de LSM al almacen.")
    parser.add_argument("carpeta", help="carpeta con los conjuntos de Zenodo ya descomprimidos")
    parser.add_argument("--store", default=None, help="almacen de grabaciones (por defecto, el de la app de PC)")
    parser.add_argument("--fotos-por-letra", type=int, default=3,
                        help="fotos por persona, letra y grupo de variacion (hay 3 grupos)")
    args = parser.parse_args()
    store = DatasetStore(args.store or config.user_data_dir() / "datos")
    import_public(args.carpeta, store, args.fotos_por_letra)


if __name__ == "__main__":
    main()
