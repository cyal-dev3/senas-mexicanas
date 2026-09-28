import numpy as np
import pytest

from conftest import fill_store
from miratek.training import TrainConfig, TrainedModel, TrainingError, train_from_store

FAST = TrainConfig(aug_copies=4, eval_aug_copies=2, max_epochs=25, eval_max_epochs=15)


def test_needs_enough_data(store):
    with pytest.raises(TrainingError):
        train_from_store(store, FAST)


def test_leave_one_signer_out(store, tmp_path):
    fill_store(store, n_signers=3, n_signs=4, clips_per_sign=6)
    messages = []
    model = train_from_store(store, FAST, progress=lambda f, m: messages.append((f, m)))
    report = model.report
    assert report.eval_mode == "personas"
    assert set(report.per_signer) == {"persona-0", "persona-1", "persona-2"}
    assert report.accuracy > 0.7, report
    assert messages[-1][0] == 1.0
    fractions = [f for f, _ in messages]
    assert fractions == sorted(fractions), "el progreso nunca debe ir hacia atras"

    path = tmp_path / "modelo.npz"
    model.save(path)
    loaded = TrainedModel.load(path)
    x = np.random.default_rng(0).standard_normal((3, model.mean.shape[0])).astype(np.float32)
    assert np.allclose(model.predict_proba(x), loaded.predict_proba(x), atol=1e-6)
    assert loaded.report.accuracy == report.accuracy


def test_single_signer_warns(store):
    fill_store(store, n_signers=1, n_signs=3, clips_per_sign=6, with_nothing=False)
    model = train_from_store(store, FAST)
    assert model.report.eval_mode == "grabaciones"
    assert any("1 persona" in w for w in model.report.warnings)
    assert any("Nada" in w for w in model.report.warnings)
