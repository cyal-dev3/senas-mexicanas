"""
Paquetes para compartir: UN archivo .zip con grabaciones y/o modelo.

Flujo pensado para personas no tecnicas:
  1. Cada persona graba y presiona "Crear archivo para enviar".
  2. Manda ese archivo (WhatsApp, correo, USB) a quien coordina.
  3. Quien coordina lo abre con "Abrir archivo recibido": las grabaciones se
     juntan con las suyas (sin duplicados) y entrena con todas.
  4. Puede mandar de vuelta un archivo con el modelo final para que todas lo usen.
"""

import json
import re
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import __version__, config
from .dataset import is_safe_id

PACKAGE_FORMAT = 1
MANIFEST = "manifest.json"
MODEL_MEMBER = "modelo/modelo.npz"
ANDROID_MEMBER = "modelo/modelo_android.json"  # el mismo modelo, para el celular
LOG_MEMBER = "diagnostico/miratek.log"
_CLIP_RE = re.compile(r"^clips/([a-z0-9_-]{1,64})/([a-z0-9_-]{1,64})/([a-z0-9_-]{1,64})\.npz$")
MAX_UNCOMPRESSED = 2 * 1024 ** 3  # 2 GB: proteccion contra archivos maliciosos


class PackageError(Exception):
    """Mensaje amigable si el archivo no sirve."""


@dataclass
class ImportResult:
    added: int = 0
    skipped: int = 0
    signers: dict = field(default_factory=dict)
    model_path: Path | None = None
    manifest: dict = field(default_factory=dict)


def export_package(store, dest_dir, author_name, model_path=None, log_path=None, include_clips=True):
    """Crea el .zip y regresa su ruta."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    refs = store.list_clips() if include_clips else []
    names = store.signer_names()
    has_model = bool(model_path and Path(model_path).exists())
    if not refs and not has_model:
        raise PackageError("Todavía no hay grabaciones ni modelo para enviar.")

    kind = "grabaciones" if refs else "modelo"
    stamp = time.strftime("%Y-%m-%d_%H%M")
    filename = f"{config.APP_ID}_{config.slugify(author_name)}_{kind}_{stamp}.zip"
    path = dest_dir / filename

    manifest = {
        "format": PACKAGE_FORMAT,
        "app_version": __version__,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "author": author_name,
        "signers": {sid: names.get(sid, sid) for sid in sorted({r.signer_id for r in refs})},
        "clips": len(refs),
        "has_model": has_model,
    }
    tmp = path.with_suffix(".tmp")
    # Los .npz ya vienen comprimidos: guardarlos sin volver a comprimir es mas rapido
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_STORED) as zf:
        for ref in refs:
            zf.write(ref.path, f"clips/{ref.signer_id}/{ref.sign_id}/{ref.clip_id}.npz")
        if has_model:
            zf.write(model_path, MODEL_MEMBER)
            try:
                from .export_android import android_model_json
                from .training import TrainedModel
                zf.writestr(ANDROID_MEMBER, android_model_json(TrainedModel.load(model_path)),
                            compress_type=zipfile.ZIP_DEFLATED)
            except Exception:
                pass  # si el modelo no es valido, igual mandamos las grabaciones
        if log_path and Path(log_path).exists():
            zf.write(log_path, LOG_MEMBER, compress_type=zipfile.ZIP_DEFLATED)
        zf.writestr(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2),
                    compress_type=zipfile.ZIP_DEFLATED)
    tmp.replace(path)
    return path


def read_manifest(zip_path):
    try:
        with zipfile.ZipFile(zip_path) as zf:
            return json.loads(zf.read(MANIFEST).decode("utf-8"))
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        raise PackageError("Este archivo no es un paquete de Mira&Tek.") from exc


def import_package(store, zip_path, models_dir):
    """Junta las grabaciones del paquete con las nuestras (sin duplicados)."""
    result = ImportResult()
    result.manifest = read_manifest(zip_path)
    if result.manifest.get("format", 0) > PACKAGE_FORMAT:
        raise PackageError("Este archivo es de una versión más nueva de la app. Actualiza la app.")

    with zipfile.ZipFile(zip_path) as zf:
        members = zf.infolist()
        if sum(m.file_size for m in members) > MAX_UNCOMPRESSED:
            raise PackageError("El archivo es demasiado grande.")
        for info in members:
            match = _CLIP_RE.match(info.filename)
            if match:
                signer_id, sign_id, clip_id = match.groups()
                target = store.clips_dir / signer_id / sign_id / f"{clip_id}.npz"
                if target.exists():
                    result.skipped += 1
                    continue
                data = zf.read(info)
                if not _valid_clip(data):
                    result.skipped += 1
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp = target.with_name(f"{clip_id}.tmp.npz")
                tmp.write_bytes(data)
                tmp.replace(target)
                result.added += 1
                result.signers[signer_id] = result.signers.get(signer_id, 0) + 1
            elif info.filename == MODEL_MEMBER:
                models_dir = Path(models_dir)
                models_dir.mkdir(parents=True, exist_ok=True)
                target = models_dir / f"recibido_{time.strftime('%Y%m%d_%H%M%S')}.npz"
                target.write_bytes(zf.read(info))
                result.model_path = target
            # Cualquier otro archivo se ignora (no extraemos nada inesperado)

    names = result.manifest.get("signers", {})
    for signer_id, name in names.items():
        if is_safe_id(signer_id) and isinstance(name, str):
            known = store.signer_names()
            if signer_id not in known:
                store.set_signer_name(signer_id, name[:40])
    return result


def _valid_clip(data):
    """Revisa que el clip se pueda leer y tenga la forma correcta."""
    import io
    try:
        with np.load(io.BytesIO(data), allow_pickle=False) as npz:
            image, world, t = npz["image"], npz["world"], npz["t"]
            json.loads(str(npz["meta"]))
            return (image.ndim == 4 and image.shape[1:] == (2, 21, 3)
                    and world.shape == image.shape and t.shape == (image.shape[0],))
    except Exception:
        return False
