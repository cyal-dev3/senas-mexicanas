import numpy as np

from miratek.hands import FrameHands, empty_hands
from miratek.recognizer import LiveRecognizer


class ScriptedModel:
    """Modelo falso que devuelve las probabilidades que le digamos."""
    classes = ["hola", "gracias", "nada"]
    window_s = 1.0

    def __init__(self):
        self.next = np.array([0.0, 0.0, 1.0])

    def predict_proba(self, _features):
        return self.next[None]


def _hands():
    h = empty_hands()
    h.image[1] = np.random.default_rng(0).random((21, 3)).astype(np.float32)
    h.world[1] = h.image[1] * 0.05
    return FrameHands(h.image, h.world)


def _run(rec, model, probs, frames, t0, dt=1 / 30, hands=None):
    events = []
    model.next = np.array(probs, dtype=float)
    t = t0
    for _ in range(frames):
        t += dt
        _, event = rec.push(t, hands if hands is not None else _hands())
        if event:
            events.append(event.sign_id)
    return events, t


def test_emits_once_per_held_sign_and_rearms_after_nothing():
    model = ScriptedModel()
    rec = LiveRecognizer(model, smoothing=0.0, cooldown_s=0.2)
    _, t = _run(rec, model, [0, 0, 1], 30, 0.0)            # solo "nada"
    events, t = _run(rec, model, [0.9, 0.05, 0.05], 60, t)  # sostiene "hola" 2 s
    assert events == ["hola"]
    _, t = _run(rec, model, [0.05, 0.05, 0.9], 20, t)       # regresa a reposo
    events, t = _run(rec, model, [0.9, 0.05, 0.05], 20, t)
    assert events == ["hola"]


def test_low_confidence_never_emits():
    model = ScriptedModel()
    rec = LiveRecognizer(model, smoothing=0.0)
    events, _ = _run(rec, model, [0.4, 0.35, 0.25], 90, 0.0)
    assert events == []


def test_no_hands_resets():
    model = ScriptedModel()
    rec = LiveRecognizer(model, smoothing=0.0)
    events, t = _run(rec, model, [0.9, 0.05, 0.05], 40, 0.0, hands=empty_hands())
    assert events == []
    assert rec.last_prediction is not None and not rec.last_prediction.hands_visible


def test_large_absolute_times_match_small_ones():
    """Con la PC encendida muchos dias, los tiempos son enormes: debe dar lo mismo."""
    from miratek import synthetic
    from miratek.features import window_features

    rng = np.random.default_rng(0)
    image, world, t = synthetic.generate_clip(synthetic.random_sign(rng, 2), synthetic.random_signer(rng), rng)

    class Capture(ScriptedModel):
        window_s = 2.0

        def __init__(self):
            super().__init__()
            self.seen = []

        def predict_proba(self, features):
            self.seen.append(features)
            return self.next[None]

    def run(offset):
        model = Capture()
        rec = LiveRecognizer(model, hop=len(t))
        for ti, img, wld in zip(t, image, world):
            rec.push(offset + float(ti), FrameHands(img, wld))
        return model.seen[-1]

    base = run(0.0)
    days = run(24 * 3600 * 24.0)  # 24 dias de uptime
    assert np.allclose(base, days, atol=1e-4)
    assert np.allclose(base, window_features(image, world, t, 4 / 3, 2.0), atol=1e-4)


def test_single_nothing_does_not_break_word_but_half_second_does():
    model = ScriptedModel()
    rec = LiveRecognizer(model, smoothing=0.0)
    _, t = _run(rec, model, [0.9, 0.05, 0.05], 40, 0.0)
    model.next = np.array([0.05, 0.05, 0.9])
    preds = []
    for _ in range(4):
        t += 1 / 30
        pred, _ = rec.push(t, _hands())
        if pred:
            preds.append(pred)
    assert preds and not any(p.word_break for p in preds), "una sola 'nada' no corta la palabra"
    for _ in range(20):
        t += 1 / 30
        pred, _ = rec.push(t, _hands())
        if pred:
            preds.append(pred)
    assert preds[-1].word_break
    # Tambien sin manos
    rec2 = LiveRecognizer(model, smoothing=0.0)
    _, t2 = _run(rec2, model, [0.9, 0.05, 0.05], 40, 0.0)
    last = None
    for _ in range(40):
        t2 += 1 / 30
        pred, _ = rec2.push(t2, empty_hands())
        last = pred or last
    assert last.word_break and not last.hands_visible


def test_sign_of_another_category_never_becomes_a_confident_letter():
    class WithLetter(ScriptedModel):
        classes = ["hola", "gracias", "letra_a", "nada"]

    model = WithLetter()
    rec = LiveRecognizer(model, smoothing=0.0, cooldown_s=0.2)
    rec.set_allowed(["letra_a"])
    # Casi todo apunta a "hola" (una palabra): al deletrear no debe salir la A
    events, t = _run(rec, model, [0.85, 0.05, 0.08, 0.02], 60, 0.0)
    assert events == []
    # Una A de verdad si sale
    events, _ = _run(rec, model, [0.1, 0.05, 0.8, 0.05], 60, t)
    assert events == ["letra_a"]
