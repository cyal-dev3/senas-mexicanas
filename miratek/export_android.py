"""
Exporta el modelo entrenado a un archivo JSON para la app de Android.

El archivo lleva todo lo que el celular necesita: la lista de senas (con su
nombre y categoria), la normalizacion y los pesos de la red. Los pesos van
como numeros float32 en base64 para que el archivo sea chico.
"""

import base64
import json
import os
import time
from pathlib import Path

import numpy as np

from . import __version__, config
from .features import FEATURE_SIZE, FEATURE_VERSION

ANDROID_FORMAT = 1


def _b64(array):
    return base64.b64encode(np.ascontiguousarray(array, dtype="<f4").tobytes()).decode("ascii")


def android_model_dict(model):
    signs = [{"id": c, "name": config.sign_name(c), "category": config.category_of(c),
              "number": config.number_value(c)} for c in model.classes]
    layers = [{"in": int(w.shape[0]), "out": int(w.shape[1]), "w": _b64(w), "b": _b64(b)}
              for w, b in zip(model.mlp.weights, model.mlp.biases)]
    r = model.report
    report = None
    if r is not None:
        report = {"accuracy": r.accuracy, "eval_mode": r.eval_mode, "n_signers": r.n_signers,
                  "n_clips": r.n_clips, "trained_at": r.trained_at, "per_category": r.per_category}
    return {
        "format": ANDROID_FORMAT,
        "feature_version": FEATURE_VERSION,
        "feature_size": FEATURE_SIZE,
        "app_version": __version__,
        "exported": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "window_s": model.window_s,
        "temperature": model.temperature,
        "signs": signs,
        "mean": _b64(model.mean),
        "std": _b64(model.std),
        "layers": layers,
        "report": report,
    }


def android_model_json(model):
    return json.dumps(android_model_dict(model), ensure_ascii=False)


def export_android_model(model, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(android_model_json(model), encoding="utf-8")
    os.replace(tmp, path)
    return path


def export_for_phone(model, dest_dir):
    """Archivo listo para mandar al celular (se abre desde la app de Android)."""
    name = f"{config.APP_ID}_modelo_celular_{time.strftime('%Y-%m-%d_%H%M')}.json"
    return export_android_model(model, Path(dest_dir) / name)
