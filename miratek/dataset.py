"""
Almacen de grabaciones.

Cada clip (una repeticion de una sena) se guarda como un archivo .npz:

    clips/<persona>/<sena>/<id_del_clip>.npz

Guardar un archivo por clip hace facil:
  - Borrar un clip malo (se borra un archivo).
  - Juntar grabaciones de varias personas (se copian archivos, sin choques).
  - Que un corte de luz no dane todo lo demas.

Solo guardamos numeros (posiciones de las manos), nunca video.
"""

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import __version__

CLIP_FORMAT = 1
_SAFE = set("abcdefghijklmnopqrstuvwxyz0123456789-_")


def is_safe_id(text):
    """True si el texto sirve como nombre de carpeta sin riesgos."""
    return bool(text) and len(text) <= 64 and set(text) <= _SAFE


@dataclass
class ClipRef:
    """Referencia a un clip en disco (sin cargarlo)."""
    path: Path
    signer_id: str
    sign_id: str
    clip_id: str


@dataclass
class Clip:
    image: np.ndarray   # (T, 2, 21, 3) posiciones en la imagen
    world: np.ndarray   # (T, 2, 21, 3) posiciones 3D en metros
    t: np.ndarray       # (T,) segundos desde el inicio del clip
    aspect: float       # ancho / alto del video
    sign_id: str
    signer_id: str
    clip_id: str


def new_clip_id():
    # Empieza con la hora en milisegundos: ordenar por nombre = ordenar por fecha
    return f"{int(time.time() * 1000):013x}-{uuid.uuid4().hex[:6]}"


class DatasetStore:
    def __init__(self, root):
        self.root = Path(root)
        self.clips_dir = self.root / "clips"
        self.clips_dir.mkdir(parents=True, exist_ok=True)
        self._signers_file = self.root / "personas.json"

    # ---------------- Guardar y borrar ----------------

    def save_clip(self, sign_id, signer_id, image, world, t, aspect):
        if not (is_safe_id(sign_id) and is_safe_id(signer_id)):
            raise ValueError(f"id invalido: {sign_id!r} / {signer_id!r}")
        clip_id = new_clip_id()
        folder = self.clips_dir / signer_id / sign_id
        folder.mkdir(parents=True, exist_ok=True)
        meta = {
            "format": CLIP_FORMAT,
            "app_version": __version__,
            "sign_id": sign_id,
            "signer_id": signer_id,
            "clip_id": clip_id,
            "aspect": float(aspect),
            "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        path = folder / f"{clip_id}.npz"
        tmp = folder / f"{clip_id}.tmp.npz"
        np.savez_compressed(
            tmp,
            image=np.asarray(image, np.float32),
            world=np.asarray(world, np.float32),
            t=np.asarray(t, np.float32),
            meta=np.array(json.dumps(meta)),
        )
        os.replace(tmp, path)  # Escritura atomica: o queda completo o no queda
        return ClipRef(path, signer_id, sign_id, clip_id)

    def delete(self, ref):
        try:
            Path(ref.path).unlink()
        except FileNotFoundError:
            pass

    def delete_signer(self, signer_id):
        import shutil
        folder = self.clips_dir / signer_id
        if is_safe_id(signer_id) and folder.is_dir():
            shutil.rmtree(folder)
        names = self.signer_names()
        if names.pop(signer_id, None) is not None:
            self._write_names(names)

    # ---------------- Leer ----------------

    def list_clips(self, signer_id=None):
        refs = []
        signer_dirs = [self.clips_dir / signer_id] if signer_id else self.clips_dir.iterdir()
        for sdir in signer_dirs:
            if not sdir.is_dir():
                continue
            for gdir in sdir.iterdir():
                if not gdir.is_dir():
                    continue
                for f in sorted(gdir.glob("*.npz")):
                    if f.name.endswith(".tmp.npz"):
                        continue
                    refs.append(ClipRef(f, sdir.name, gdir.name, f.stem))
        return refs

    @staticmethod
    def load(ref):
        with np.load(ref.path, allow_pickle=False) as data:
            meta = json.loads(str(data["meta"]))
            return Clip(
                image=data["image"].astype(np.float32),
                world=data["world"].astype(np.float32),
                t=data["t"].astype(np.float32),
                aspect=float(meta.get("aspect", 4 / 3)),
                sign_id=ref.sign_id,
                signer_id=ref.signer_id,
                clip_id=ref.clip_id,
            )

    def counts(self, signer_id=None):
        """{sena: numero de clips} (de una persona o de todas)."""
        out = {}
        for ref in self.list_clips(signer_id):
            out[ref.sign_id] = out.get(ref.sign_id, 0) + 1
        return out

    def counts_by_signer(self):
        out = {}
        for ref in self.list_clips():
            per = out.setdefault(ref.signer_id, {})
            per[ref.sign_id] = per.get(ref.sign_id, 0) + 1
        return out

    # ---------------- Nombres de las personas ----------------

    def signer_names(self):
        try:
            data = json.loads(self._signers_file.read_text(encoding="utf-8"))
            return {k: str(v) for k, v in data.items() if is_safe_id(k)}
        except (FileNotFoundError, ValueError):
            return {}

    def set_signer_name(self, signer_id, name):
        names = self.signer_names()
        if names.get(signer_id) != name:
            names[signer_id] = name
            self._write_names(names)

    def _write_names(self, names):
        tmp = self._signers_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self._signers_file)
