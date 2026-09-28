import zipfile

import numpy as np
import pytest

from conftest import fill_store
from miratek.dataset import DatasetStore
from miratek.hands import LEFT, RIGHT, assign_slots, empty_hands
from miratek.package import PackageError, export_package, import_package


def test_save_count_delete(store):
    fill_store(store, n_signers=2, n_signs=2, clips_per_sign=3)
    assert store.counts("persona-0") == {"sena0": 3, "sena1": 3, "nada": 3}
    refs = store.list_clips("persona-1")
    store.delete(refs[0])
    assert sum(store.counts("persona-1").values()) == 8
    clip = store.load(refs[1])
    assert clip.image.shape[1:] == (2, 21, 3) and clip.t.ndim == 1
    store.delete_signer("persona-1")
    assert "persona-1" not in store.counts_by_signer()


def test_export_import_roundtrip(store, tmp_path):
    fill_store(store, n_signers=2, n_signs=2, clips_per_sign=2)
    model = tmp_path / "m.npz"
    np.savez(model, x=np.zeros(3))
    pkg = export_package(store, tmp_path / "out", "María Peña", model_path=model)
    assert pkg.name.startswith("MiraTek_maria-pena_")

    other = DatasetStore(tmp_path / "otra")
    result = import_package(other, pkg, tmp_path / "modelos")
    assert result.added == 12 and result.skipped == 0
    assert result.model_path is not None and result.model_path.exists()
    assert other.signer_names() == store.signer_names()
    again = import_package(other, pkg, tmp_path / "modelos")
    assert again.added == 0 and again.skipped == 12  # sin duplicados


def test_rejects_non_packages_and_ignores_unsafe_members(store, tmp_path):
    bad = tmp_path / "x.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("hola.txt", "no soy un paquete")
    with pytest.raises(PackageError):
        import_package(store, bad, tmp_path / "m")

    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("manifest.json", '{"format": 1}')
        zf.writestr("../../fuera.npz", b"x")
        zf.writestr("clips/a/b/../../../c.npz", b"x")
    result = import_package(store, evil, tmp_path / "m")
    assert result.added == 0
    assert not (tmp_path / "fuera.npz").exists()


def _det(label, x):
    img = np.zeros((21, 3), np.float32)
    img[:, 0] = x
    return (label, img, img * 0.1)


def test_duplicate_labels_split_by_position():
    hands = assign_slots([_det("Right", 0.7), _det("Right", 0.3)])
    assert hands.image[RIGHT, 0, 0] == np.float32(0.7)
    assert hands.image[LEFT, 0, 0] == np.float32(0.3)


def test_single_hand_keeps_slot_when_label_flips():
    prev = assign_slots([_det("Right", 0.6)])
    flipped = assign_slots([_det("Left", 0.61)], previous=prev)
    assert flipped.present[RIGHT] and not flipped.present[LEFT]
    far = assign_slots([_det("Left", 0.2)], previous=prev)
    assert far.present[LEFT]
    assert not assign_slots([], previous=prev).any
    assert not empty_hands().any
