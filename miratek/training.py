"""
Entrenamiento completo con UN solo boton.

=== PASOS ===
1. Cargar los clips grabados.
2. EXAMEN HONESTO (para saber si de verdad funciona):
   - Con 2 o mas personas: se entrena SIN una persona y se le hace el examen
     a esa persona. Se repite con cada una. Asi medimos que tan bien funciona
     con alguien que el modelo NUNCA vio. Es el numero que importa.
   - Con 1 persona: se apartan clips completos (nunca vistos) para el examen.
     Ojo: este numero sale mas alto que con personas nuevas.
   En ambos casos el examen usa clips COMPLETOS, no frames sueltos. Antes se
   separaban frames casi identicos del mismo clip y el examen salia inflado.
3. MODELO FINAL: se entrena con todos los datos.

Los datos de examen nunca se usan para elegir el modelo ni para ajustar nada.
"""

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from . import __version__, config
from .augment import augment_clip, augment_transition, pad_window
from .features import FEATURE_SIZE, FEATURE_VERSION, window_features
from .mlp import MLP, TrainingCancelled, fit_temperature, fit_temperature_rows, softmax, train_mlp

MODEL_FORMAT = 1

__all__ = ["TrainConfig", "TrainReport", "TrainedModel", "TrainingError", "TrainingCancelled",
           "ModelError", "train_from_store"]


class TrainingError(Exception):
    """Error con un mensaje amigable para mostrar en pantalla."""


class ModelError(Exception):
    """El archivo del modelo no se pudo usar."""


@dataclass
class TrainConfig:
    window_s: float = config.CLIP_SECONDS
    aug_copies: int = 12          # Variaciones por clip para el modelo final
    eval_aug_copies: int = 6      # Menos variaciones en el examen (para que sea rapido)
    max_epochs: int = 60
    eval_max_epochs: int = 35
    hidden: tuple = (256, 128)
    dropout: tuple = (0.3, 0.2)
    lr: float = 1e-3
    weight_decay: float = 1e-4
    batch_size: int = 128
    smoothing: float = 0.05
    val_fraction: float = 0.15
    test_fraction: float = 0.2
    max_signer_folds: int = 6
    seed: int = 42
    input_noise: float = 0.05        # Ruido sobre las caracteristicas normalizadas al entrenar
    transition_fraction: float = 0.3  # Variaciones que empiezan con la cola de otra sena


@dataclass
class TrainReport:
    classes: list
    eval_mode: str                 # "personas" o "grabaciones"
    accuracy: float
    per_class: dict                # sena -> {"recall", "precision", "support"}
    confusion: list                # matriz [real][predicha]
    top_confusions: list           # [[real, predicha, veces], ...]
    per_signer: dict = field(default_factory=dict)
    per_category: dict = field(default_factory=dict)  # categoria -> aciertos
    n_clips: int = 0
    n_signers: int = 0
    clips_per_class: dict = field(default_factory=dict)
    trained_at: str = ""
    seconds: float = 0.0
    warnings: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        known = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        return cls(**known)


class TrainedModel:
    """Modelo listo para usar: red + normalizacion + lista de senas."""

    def __init__(self, mlp, mean, std, classes, temperature=1.0, window_s=config.CLIP_SECONDS,
                 report=None):
        self.mlp = mlp
        self.mean = mean.astype(np.float32)
        self.std = std.astype(np.float32)
        self.classes = list(classes)
        self.temperature = float(temperature)
        self.window_s = float(window_s)
        self.report = report

    def predict_proba(self, features):
        x = (np.atleast_2d(features) - self.mean) / self.std
        return softmax(self.mlp.logits(x.astype(np.float32)), self.temperature)

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        meta = {
            "format": MODEL_FORMAT,
            "feature_version": FEATURE_VERSION,
            "app_version": __version__,
            "classes": self.classes,
            "temperature": self.temperature,
            "window_s": self.window_s,
            "dropout": list(self.mlp.dropout),
            "report": self.report.to_dict() if self.report else None,
        }
        arrays = {f"w{i}": w for i, w in enumerate(self.mlp.weights)}
        arrays.update({f"b{i}": b for i, b in enumerate(self.mlp.biases)})
        tmp = path.with_name(path.stem + ".tmp.npz")
        np.savez_compressed(tmp, mean=self.mean, std=self.std, meta=np.array(json.dumps(meta)), **arrays)
        os.replace(tmp, path)

    @classmethod
    def load(cls, path):
        try:
            with np.load(path, allow_pickle=False) as data:
                meta = json.loads(str(data["meta"]))
                n_layers = sum(1 for k in data.files if k.startswith("w"))
                weights = [np.asarray(data[f"w{i}"], np.float32) for i in range(n_layers)]
                biases = [np.asarray(data[f"b{i}"], np.float32) for i in range(n_layers)]
                mean, std = np.asarray(data["mean"], np.float32), np.asarray(data["std"], np.float32)
            classes = list(meta["classes"])
            if meta.get("feature_version") != FEATURE_VERSION or mean.shape != (FEATURE_SIZE,):
                raise ModelError("Este modelo es de otra versión de la app. Vuelve a entrenar.")
            # Que todo encaje: capas encadenadas, una salida por sena, numeros validos
            if (not weights or std.shape != mean.shape or weights[0].shape[0] != FEATURE_SIZE
                    or weights[-1].shape[1] != len(classes) or len(classes) < 2
                    or any(w.ndim != 2 or b.shape != (w.shape[1],) for w, b in zip(weights, biases))
                    or any(a.shape[1] != b.shape[0] for a, b in zip(weights[:-1], weights[1:]))
                    or not all(np.isfinite(a).all() for a in weights + biases + [mean, std])
                    or not all(isinstance(c, str) for c in classes)):
                raise ModelError("El archivo del modelo está dañado.")
            std = np.where(std > 0, std, 1.0).astype(np.float32)
            temperature = float(meta.get("temperature", 1.0))
            if not np.isfinite(temperature) or temperature <= 0:
                temperature = 1.0
            report = TrainReport.from_dict(meta["report"]) if isinstance(meta.get("report"), dict) else None
        except ModelError:
            raise
        except Exception as exc:
            raise ModelError("El archivo del modelo está dañado.") from exc
        mlp = MLP(weights[0].shape[0], weights[-1].shape[1],
                  hidden=tuple(w.shape[1] for w in weights[:-1]), dropout=meta.get("dropout", ()))
        mlp.weights = weights
        mlp.biases = biases
        return cls(mlp, mean, std, classes, temperature, float(meta.get("window_s", config.CLIP_SECONDS)), report)


# ============================================================
# Ayudantes
# ============================================================

def _clip_features(clip, window_s, rng=None, prefix=None):
    """Caracteristicas del clip tal cual, o de una variacion (con rng).

    prefix: otro clip cuya cola aparece al inicio de la ventana (transicion).
    Los bordes se rellenan con pad_window: si la persona tenia las manos abajo
    al inicio, el modelo lo ve asi (hold_edges inventaba una mano ahi).
    """
    if rng is None:
        return window_features(clip.image, clip.world, clip.t, clip.aspect, window_s, mirror=clip.mirror)
    if prefix is not None:
        image, world, t, t_end = augment_transition(clip.image, clip.world, clip.t, clip.aspect,
                                                    (prefix.image, prefix.world, prefix.t), rng, window_s)
    else:
        image, world, t, t_end = augment_clip(clip.image, clip.world, clip.t, clip.aspect, rng)
        image, world, t = pad_window(image, world, t, t_end, window_s)
    return window_features(image, world, t, clip.aspect, window_s, t_end=t_end, mirror=clip.mirror)


def _build_set(clips, class_index, window_s, copies, rng, tick=None, transition_fraction=0.0):
    feats, labels = [], []
    for i, clip in enumerate(clips):
        label = class_index[clip.sign_id]
        feats.append(_clip_features(clip, window_s))
        labels.append(label)
        for _ in range(copies):
            prefix = None
            if len(clips) > 1 and rng.random() < transition_fraction:
                j = int(rng.integers(len(clips) - 1))
                prefix = clips[j if j < i else j + 1]  # cualquier otro clip (otra sena o "nada")
            feats.append(_clip_features(clip, window_s, rng, prefix))
            labels.append(label)
        if tick:
            tick((i + 1) / len(clips))
    if not feats:
        return np.zeros((0, FEATURE_SIZE), np.float32), np.zeros(0, np.int64)
    return np.stack(feats), np.asarray(labels, np.int64)


def _stratified_split(labels, fraction, rng):
    """Aparta 'fraction' de los clips de cada sena (al menos 1 si hay 3 o mas)."""
    labels = np.asarray(labels)
    held = np.zeros(len(labels), bool)
    for c in np.unique(labels):
        idx = np.flatnonzero(labels == c)
        rng.shuffle(idx)
        k = int(round(len(idx) * fraction))
        k = max(1, k) if len(idx) >= 3 else 0
        k = min(k, len(idx) - 1)
        held[idx[:k]] = True
    return ~held, held


def _fit(train_clips, classes, cfg, copies, epochs, rng, progress, should_cancel):
    """Entrena un modelo con esos clips (separa una parte para validacion)."""
    class_index = {c: i for i, c in enumerate(classes)}
    labels = [class_index[c.sign_id] for c in train_clips]
    tr_mask, va_mask = _stratified_split(labels, cfg.val_fraction, rng)
    tr = [c for c, m in zip(train_clips, tr_mask) if m]
    va = [c for c, m in zip(train_clips, va_mask) if m]

    def build_tick(frac):
        progress(0.4 * frac)
        if should_cancel and should_cancel():
            raise TrainingCancelled()

    x_tr, y_tr = _build_set(tr, class_index, cfg.window_s, copies, rng, build_tick, cfg.transition_fraction)
    x_va, y_va = _build_set(va, class_index, cfg.window_s, 2, rng)
    mean = x_tr.mean(axis=0)
    std = x_tr.std(axis=0)
    # Piso: un numero casi constante al grabar no debe disparar la red con gente nueva
    varying = std[std >= 1e-3]
    floor = 0.05 * float(np.median(varying)) if varying.size else 0.0
    std = np.where(std < 1e-3, 1.0, np.maximum(std, floor))
    x_tr = ((x_tr - mean) / std).astype(np.float32)
    x_va = ((x_va - mean) / std).astype(np.float32)

    def on_epoch(epoch, total, _loss):
        progress(0.4 + 0.6 * (epoch + 1) / total)

    mlp = train_mlp(x_tr, y_tr, x_va, y_va, len(classes), hidden=cfg.hidden, dropout=cfg.dropout,
                    lr=cfg.lr, weight_decay=cfg.weight_decay, batch_size=cfg.batch_size,
                    max_epochs=epochs, smoothing=cfg.smoothing, input_noise=cfg.input_noise,
                    seed=int(rng.integers(1 << 30)), on_epoch=on_epoch, should_cancel=should_cancel)
    temperature = fit_temperature(mlp.logits(x_va), y_va) if len(y_va) else 1.0
    return TrainedModel(mlp, mean, std, classes, temperature, cfg.window_s)


def _predict_clips(model, clips):
    """Predicciones del examen, igual que en la app: cada modo solo compite
    con su categoria (una letra O nunca se confunde con el numero 0 porque
    al deletrear no hay numeros). 'Nada' compite contra todo."""
    if not clips:
        return np.zeros(0, np.int64), []
    feats = np.stack([_clip_features(c, model.window_s) for c in clips])
    logits = model.mlp.logits(((feats - model.mean) / model.std).astype(np.float32))
    cats = np.array([config.category_of(c) for c in model.classes])
    is_nothing = np.array([c == config.NOTHING_ID for c in model.classes])
    preds = []
    for clip, z in zip(clips, logits):
        if clip.sign_id == config.NOTHING_ID:
            preds.append(int(z.argmax()))
        else:
            mask = (cats == config.category_of(clip.sign_id)) | is_nothing
            preds.append(int(np.where(mask, z, -np.inf).argmax()))
    # Los logits del examen sirven para calibrar la confianza con personas nuevas
    index = {c: i for i, c in enumerate(model.classes)}
    rows = [(z, index[clip.sign_id]) for clip, z in zip(clips, logits) if clip.sign_id in index]
    return np.asarray(preds, np.int64), rows


# ============================================================
# Entrenamiento principal
# ============================================================

def train_from_store(store, cfg=None, progress=None, should_cancel=None):
    """Entrena con todo lo grabado. progress(fraccion 0..1, mensaje)."""
    cfg = cfg or TrainConfig()
    started = time.time()
    rng = np.random.default_rng(cfg.seed)
    report_progress = progress or (lambda f, m: None)
    warnings = []

    # ---------- 1. Cargar clips ----------
    report_progress(0.0, "Leyendo tus grabaciones…")
    refs = store.list_clips()
    loaded = []
    for i, ref in enumerate(refs):
        try:
            clip = store.load(ref)
            if len(clip.t) >= 2:
                loaded.append(clip)
        except Exception:
            pass  # un clip danado no debe tumbar todo el entrenamiento
        if i % 25 == 0:
            report_progress(0.08 * (i + 1) / max(1, len(refs)), "Leyendo tus grabaciones…")
            if should_cancel and should_cancel():
                raise TrainingCancelled()
    # Las senas se eligen con los clips que SI se pudieron leer
    counts = {}
    for clip in loaded:
        counts[clip.sign_id] = counts.get(clip.sign_id, 0) + 1
    classes = sorted(c for c, n in counts.items() if n >= config.MIN_CLIPS_PER_CLASS)
    excluded = sorted(c for c, n in counts.items() if n < config.MIN_CLIPS_PER_CLASS)
    if len(classes) < 2:
        raise TrainingError(
            "Todavía no hay suficientes grabaciones. Graba al menos 2 señas con "
            f"{config.MIN_CLIPS_PER_CLASS} clips o más cada una.")
    if excluded:
        warnings.append("No se usaron " + ", ".join(config.sign_name(c) for c in excluded)
                        + f": necesitan al menos {config.MIN_CLIPS_PER_CLASS} grabaciones.")
    if config.NOTHING_ID not in classes:
        warnings.append("Graba la seña «Nada» para que el modelo sepa cuándo no estás "
                        "haciendo ninguna seña.")
    clips = [c for c in loaded if c.sign_id in classes]
    class_index = {c: i for i, c in enumerate(classes)}
    signers = sorted({c.signer_id for c in clips})

    # ---------- 2. Examen honesto ----------
    # Cualquier persona con 2 o mas senas sirve de examen: se le examina en lo que
    # grabo. (Antes se pedia la mitad de las senas y el examen caia en silencio al
    # reparto por grabaciones, que sale inflado.)
    per_signer_classes = {s: {c.sign_id for c in clips if c.signer_id == s} for s in signers}
    eligible = [s for s in signers if len(per_signer_classes[s]) >= 2]
    eligible.sort(key=lambda s: -sum(1 for c in clips if c.signer_id == s))
    folds = []
    if len(eligible) >= 2:
        eval_mode = "personas"
        for s in eligible[:cfg.max_signer_folds]:
            train = [c for c in clips if c.signer_id != s]
            fold_classes = sorted({c.sign_id for c in train})
            test = [c for c in clips if c.signer_id == s and c.sign_id in fold_classes]
            if len(fold_classes) >= 2 and test:
                folds.append((s, train, test, fold_classes))
    if not folds:
        eval_mode = "grabaciones"
        labels = [class_index[c.sign_id] for c in clips]
        tr_mask, te_mask = _stratified_split(labels, cfg.test_fraction, rng)
        train = [c for c, m in zip(clips, tr_mask) if m]
        test = [c for c, m in zip(clips, te_mask) if m]
        folds.append((None, train, test, sorted({c.sign_id for c in train})))
        if len(signers) == 1:
            warnings.append("Solo hay grabaciones de 1 persona. Con otras personas puede "
                            "fallar más: pide a más gente que grabe.")

    n = len(classes)
    confusion = np.zeros((n, n), np.int64)
    per_signer = {}
    exam_rows = []  # logits del examen: calibran la confianza del modelo final
    eval_span = 0.57 / len(folds)
    for k, (signer, train, test, fold_classes) in enumerate(folds):
        base = 0.08 + k * eval_span
        label = (f"Examen con personas nuevas ({k + 1} de {len(folds)})…"
                 if eval_mode == "personas" else "Haciendo el examen…")
        model = _fit(train, fold_classes, cfg, cfg.eval_aug_copies, cfg.eval_max_epochs, rng,
                     lambda f, b=base, m=label: report_progress(b + eval_span * f, m), should_cancel)
        pred, rows = _predict_clips(model, test)
        exam_rows.extend(rows)
        true_idx = [class_index[c.sign_id] for c in test]
        pred_idx = [class_index[fold_classes[p]] for p in pred]
        for t_i, p_i in zip(true_idx, pred_idx):
            confusion[t_i, p_i] += 1
        if signer is not None and len(test):
            per_signer[signer] = float(np.mean(np.array(true_idx) == np.array(pred_idx)))

    # ---------- 3. Modelo final con todos los datos ----------
    final = _fit(clips, classes, cfg, cfg.aug_copies, cfg.max_epochs, rng,
                 lambda f: report_progress(0.65 + 0.33 * f, "Entrenando el modelo final…"),
                 should_cancel)
    if eval_mode == "personas" and exam_rows:
        # La temperatura se ajusta con personas que el modelo NO vio: asi "80% seguro"
        # significa 80% tambien con gente nueva, no solo con quien grabo.
        final.temperature = fit_temperature_rows(exam_rows)
    report_progress(0.99, "Guardando…")

    total = confusion.sum()
    per_class = {}
    for i, c in enumerate(classes):
        support = int(confusion[i].sum())
        predicted = int(confusion[:, i].sum())
        per_class[c] = {
            "recall": float(confusion[i, i] / support) if support else None,
            "precision": float(confusion[i, i] / predicted) if predicted else None,
            "support": support,
        }
    off = [(int(confusion[i, j]), classes[i], classes[j])
           for i in range(n) for j in range(n) if i != j and confusion[i, j] > 0]
    off.sort(reverse=True)
    per_category = {}
    for cat in config.CATEGORIES:
        rows = [i for i, c in enumerate(classes) if config.category_of(c) == cat and c != config.NOTHING_ID]
        support = confusion[rows].sum() if rows else 0
        if support:
            per_category[cat] = float(sum(confusion[i, i] for i in rows) / support)
    final.report = TrainReport(
        classes=classes,
        eval_mode=eval_mode,
        accuracy=float(np.trace(confusion) / total) if total else 0.0,
        per_class=per_class,
        confusion=confusion.tolist(),
        top_confusions=[[a, b, cnt] for cnt, a, b in off[:3]],
        per_signer=per_signer,
        per_category=per_category,
        n_clips=len(clips),
        n_signers=len(signers),
        clips_per_class={c: counts[c] for c in classes},
        trained_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        seconds=round(time.time() - started, 1),
        warnings=warnings,
    )
    report_progress(1.0, "¡Listo!")
    return final
