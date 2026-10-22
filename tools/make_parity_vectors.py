"""
Genera datos de prueba para verificar que la app de Android calcula EXACTAMENTE
lo mismo que Python (caracteristicas, modelo y reglas de frases).

    python tools/make_parity_vectors.py

Escribe android/core/src/test/resources/parity/*.json. Las pruebas de Kotlin
(FeaturesParityTest, ModelParityTest, PhraseParityTest) los leen.
Hay que volver a correrlo si cambia features.py, phrase.py o el formato del modelo.
"""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from miratek import config, synthetic  # noqa: E402
from miratek.augment import augment_clip, pad_window  # noqa: E402
from miratek.dataset import DatasetStore  # noqa: E402
from miratek.export_android import android_model_dict  # noqa: E402
from miratek.features import window_features  # noqa: E402
from miratek.phrase import PhraseBuilder  # noqa: E402
from miratek.training import TrainConfig, train_from_store  # noqa: E402

OUT = ROOT / "android" / "core" / "src" / "test" / "resources" / "parity"


def _nan_to_none(array):
    return [[None if np.isnan(v) else round(float(v), 6) for v in row] for row in array]


def feature_cases():
    rng = np.random.default_rng(123)
    cases = []

    def add(image, world, t, aspect, window_s=2.0, t_end=None, mirror=None, name=""):
        # Redondeamos las entradas ANTES de calcular: asi el archivo es chico y ambos
        # lados (Python y Kotlin) calculan con exactamente los mismos numeros.
        image = np.round(np.asarray(image, np.float32), 6)
        world = np.round(np.asarray(world, np.float32), 6)
        t = np.round(np.asarray(t, np.float64), 6)
        feats = window_features(image, world, t, aspect, window_s, t_end=t_end, mirror=mirror)
        cases.append({
            "name": name,
            "aspect": aspect,
            "window_s": window_s,
            "t_end": float(t[-1]) if t_end is None else float(t_end),
            "mirror": mirror,
            "times": [float(v) for v in np.asarray(t, np.float64)],
            "image": _nan_to_none(np.asarray(image, np.float32).reshape(len(t), 126)),
            "world": _nan_to_none(np.asarray(world, np.float32).reshape(len(t), 126)),
            "expected": [round(float(v), 7) for v in feats],
        })

    signs = [synthetic.random_sign(rng, i) for i in range(4)]
    signs[2].two_hands = True
    for i, sign in enumerate(signs):
        signer = synthetic.random_signer(rng)
        signer.left_handed = i == 1
        image, world, t = synthetic.generate_clip(sign, signer, rng)
        add(image, world, t, 4 / 3, name=f"clip{i}")
        add(image, world, t, 0.75, name=f"clip{i}_portrait")
    # Nada, clip corto, ventana corrida con bordes sostenidos y huecos largos
    image, world, t = synthetic.generate_clip(synthetic.sign_for_id("nada"), synthetic.random_signer(rng), rng)
    add(image, world, t, 4 / 3, name="nada")
    add(image[:20], world[:20], t[:20], 4 / 3, name="short")
    aug = augment_clip(image, world, t, 4 / 3, rng)
    p_img, p_wld, p_t = pad_window(aug[0], aug[1], aug[2], aug[3], 2.0)
    add(p_img, p_wld, p_t, 4 / 3, t_end=aug[3], name="augmented")
    # Lateralidad explicita: zurda (espejo) y diestra (sin espejo) con la otra mano a la vista
    two = image.copy()
    two[:, 0] = image[:, 1] * np.float32(0.9) + np.float32(0.05)
    two_w = world.copy()
    two_w[:, 0] = world[:, 1] * np.float32(0.8)
    add(two, two_w, t, 4 / 3, mirror=True, name="mirror_true")
    add(two, two_w, t, 4 / 3, mirror=False, name="mirror_false")
    gap_img, gap_wld = image.copy(), world.copy()
    gap_img[10:30] = np.nan
    gap_wld[10:30] = np.nan
    add(gap_img, gap_wld, t, 4 / 3, name="gap")
    return cases


def model_cases(cases):
    with tempfile.TemporaryDirectory() as tmp:
        store = DatasetStore(Path(tmp) / "datos")
        ids = ["hola", "gracias", "nada", "letra_a", "letra_b", "num_2", "num_20"]
        synthetic.fill_store(store, n_signers=2, clips_per_sign=5, sign_ids=ids)
        model = train_from_store(store, TrainConfig(aug_copies=2, eval_aug_copies=1, max_epochs=8, hidden=(48, 24),
                                                    eval_max_epochs=4))
    feats = np.array([c["expected"] for c in cases], np.float32)
    probs = model.predict_proba(feats)
    return android_model_dict(model), {"features": feats.tolist(),
                                       "expected": np.round(probs, 8).tolist()}


def phrase_cases():
    sequences = [
        ["hola", "letra_a", "letra_n", "letra_a", "|", "gracias"],
        ["num_20", "num_3", "|", "num_10", "num_6", "|", "num_1", "num_0", "num_0"],
        ["num_7", "num_20", "num_30", "num_15", "num_2"],
        ["letra_enie", "letra_o", "nada", "letra_s", "|", "hola"],
        ["num_100", "num_20", "num_5", "num_2", "|", "num_100", "num_15", "num_16"],
    ]
    out = []
    for seq in sequences:
        p = PhraseBuilder()
        for token in seq:
            if token == "|":
                p.close()
            else:
                p.add(token)
        out.append({"tokens": seq, "expected": p.texts})
    used = sorted({t for seq in sequences for t in seq if t != "|"})
    signs = [{"id": s, "name": config.sign_name(s), "category": config.category_of(s),
              "number": config.number_value(s)} for s in used]
    return {"signs": signs, "cases": out}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    cases = feature_cases()
    (OUT / "features.json").write_text(json.dumps({"cases": cases}), encoding="utf-8")
    model, predictions = model_cases(cases)
    (OUT / "model.json").write_text(json.dumps(model), encoding="utf-8")
    (OUT / "predictions.json").write_text(json.dumps(predictions), encoding="utf-8")
    (OUT / "phrase.json").write_text(json.dumps(phrase_cases(), ensure_ascii=False), encoding="utf-8")
    print(f"{len(cases)} casos de caracteristicas escritos en {OUT}")


if __name__ == "__main__":
    main()
