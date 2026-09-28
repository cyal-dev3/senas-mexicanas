import numpy as np

from miratek.mlp import MLP, cross_entropy, fit_temperature, softmax, train_mlp


def test_gradients_match_numeric():
    """El backward calcula bien los gradientes (comparado con diferencias finitas)."""
    rng = np.random.default_rng(0)
    net = MLP(6, 3, hidden=(5, 4), dropout=(0.0, 0.0), seed=1)
    net.weights = [w.astype(np.float64) for w in net.weights]
    net.biases = [b.astype(np.float64) + 0.1 for b in net.biases]
    x = rng.standard_normal((7, 6))
    y = rng.integers(0, 3, 7)

    def loss_fn():
        return cross_entropy(net.forward(x)[0], y, smoothing=0.1)[0]

    logits, cache = net.forward(x)
    _, dlogits = cross_entropy(logits, y, smoothing=0.1)
    grads = net.backward(cache, dlogits.astype(np.float64))
    eps = 1e-6
    for param, grad in zip(net.params, grads):
        flat = param.reshape(-1)
        for i in range(0, flat.size, max(1, flat.size // 7)):
            old = flat[i]
            flat[i] = old + eps
            up = loss_fn()
            flat[i] = old - eps
            down = loss_fn()
            flat[i] = old
            assert abs((up - down) / (2 * eps) - grad.reshape(-1)[i]) < 1e-4


def test_learns_separable_classes():
    rng = np.random.default_rng(0)
    centers = rng.standard_normal((4, 20)) * 3
    y = rng.integers(0, 4, 800)
    x = (centers[y] + rng.standard_normal((800, 20))).astype(np.float32)
    net = train_mlp(x[:600], y[:600], x[600:700], y[600:700], 4, max_epochs=30, seed=0)
    acc = (net.logits(x[700:]).argmax(1) == y[700:]).mean()
    assert acc > 0.95


def test_temperature_calibrates_overconfidence():
    rng = np.random.default_rng(0)
    honest = rng.standard_normal((4000, 3)) * 1.5
    probs = softmax(honest)
    y = np.array([rng.choice(3, p=p) for p in probs])  # etiquetas que siguen esas probabilidades
    temp = fit_temperature(honest * 4, y)  # red 4 veces demasiado segura de si misma
    assert 3.2 < temp < 4.8
    assert np.allclose(softmax(honest, temp).sum(1), 1.0)
