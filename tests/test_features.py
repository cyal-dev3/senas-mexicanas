import numpy as np

from miratek import synthetic
from miratek.augment import augment_clip
from miratek.features import FEATURE_SIZE, window_features


def _clip(seed=0, left_handed=False):
    rng = np.random.default_rng(seed)
    sign = synthetic.random_sign(rng, 1)
    signer = synthetic.SynthSigner(left_handed=left_handed, seed=seed, curl_noise=0.0)
    return synthetic.generate_clip(sign, signer, np.random.default_rng(seed))


def test_size_and_finite():
    image, world, t = _clip()
    f = window_features(image, world, t, 4 / 3, 2.0)
    assert f.shape == (FEATURE_SIZE,)
    assert np.isfinite(f).all()


def test_no_hands_is_all_zeros():
    image, world, t = _clip()
    nan = np.full_like(image, np.nan)
    assert not window_features(nan, nan, t, 4 / 3, 2.0).any()
    assert not window_features(nan[:0], nan[:0], t[:0], 4 / 3, 2.0).any()


def test_invariant_to_position_in_frame():
    """Moverse en la imagen no debe cambiar forma ni movimiento."""
    image, world, t = _clip()
    moved = image.copy()
    moved[..., 0] += 0.1
    moved[..., 1] -= 0.05
    a = window_features(image, world, t, 4 / 3, 2.0)
    b = window_features(moved, world, t, 4 / 3, 2.0)
    shape_and_motion = slice(0, 480 + 120 + 64 + 32)
    assert np.allclose(a[shape_and_motion], b[shape_and_motion], atol=1e-4)


def test_invariant_to_frame_rate():
    """La misma sena grabada a 30 o a 15 fps debe dar casi lo mismo."""
    image, world, t = _clip()
    a = window_features(image, world, t, 4 / 3, 2.0)
    b = window_features(image[::2], world[::2], t[::2], 4 / 3, 2.0, t_end=t[-1])
    assert np.corrcoef(a, b)[0, 1] > 0.97


def test_left_handed_is_mirrored_to_right():
    """Una persona zurda debe verse igual que una diestra."""
    right = window_features(*_clip(3, False), 4 / 3, 2.0)
    left = window_features(*_clip(3, True), 4 / 3, 2.0)
    assert np.corrcoef(right, left)[0, 1] > 0.95


def test_augmentation_keeps_shapes():
    image, world, t = _clip()
    rng = np.random.default_rng(1)
    a_img, a_wld, a_t, t_end = augment_clip(image, world, t, 4 / 3, rng)
    assert a_img.shape == image.shape and a_wld.shape == world.shape and a_t.shape == t.shape
    f = window_features(a_img, a_wld, a_t, 4 / 3, 2.0, t_end=t_end, hold_edges=True)
    assert f.shape == (FEATURE_SIZE,) and np.isfinite(f).all()
