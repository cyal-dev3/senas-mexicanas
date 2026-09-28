"""
Red neuronal MLP (Perceptron Multicapa) escrita solo con NumPy.

Es la misma idea que el modelo original en PyTorch:
    entrada (728 numeros) -> 256 neuronas -> 128 neuronas -> una salida por sena

La escribimos con NumPy para que la app sea ligera: PyTorch pesa cientos de
megas y el .exe tardaria mucho en abrir. Para una red de este tamano, NumPy
entrena en segundos.

Piezas:
  - ReLU: si un numero es negativo lo vuelve 0.
  - Dropout: apaga neuronas al azar al entrenar (evita memorizar).
  - Softmax: convierte las salidas en probabilidades que suman 1.
  - AdamW: el algoritmo que ajusta los pesos poco a poco.
"""

import numpy as np


class MLP:
    def __init__(self, n_in, n_out, hidden=(256, 128), dropout=(0.3, 0.2), seed=0):
        rng = np.random.default_rng(seed)
        sizes = [n_in, *hidden, n_out]
        self.dropout = tuple(dropout)
        self.weights = []
        self.biases = []
        for a, b in zip(sizes[:-1], sizes[1:]):
            # Inicializacion "He": buena para capas con ReLU
            self.weights.append((rng.standard_normal((a, b)) * np.sqrt(2.0 / a)).astype(np.float32))
            self.biases.append(np.zeros(b, np.float32))

    @property
    def params(self):
        return self.weights + self.biases

    def forward(self, x, train=False, rng=None):
        """Pasa los datos por la red. Devuelve (logits, cache para backward)."""
        acts = [x]
        masks = []
        h = x
        last = len(self.weights) - 1
        for i, (w, b) in enumerate(zip(self.weights, self.biases)):
            h = h @ w + b
            if i < last:
                h = np.maximum(h, 0.0)
                p = self.dropout[i] if i < len(self.dropout) else 0.0
                if train and p > 0:
                    mask = (rng.random(h.shape) >= p).astype(h.dtype) / (1.0 - p)
                    h = h * mask
                    masks.append(mask)
                else:
                    masks.append(None)
                acts.append(h)
        return h, (acts, masks)

    def backward(self, cache, dlogits):
        """Calcula como cambiar cada peso para equivocarse menos (gradientes)."""
        acts, masks = cache
        grads_w = [None] * len(self.weights)
        grads_b = [None] * len(self.biases)
        d = dlogits
        for i in range(len(self.weights) - 1, -1, -1):
            grads_w[i] = acts[i].T @ d
            grads_b[i] = d.sum(axis=0)
            if i > 0:
                d = d @ self.weights[i].T
                if masks[i - 1] is not None:
                    d = d * masks[i - 1]
                d = d * (acts[i] > 0)
        return grads_w + grads_b

    def logits(self, x, batch=4096):
        out = [self.forward(x[i:i + batch])[0] for i in range(0, len(x), batch)]
        return np.concatenate(out) if out else np.zeros((0, self.biases[-1].shape[0]), np.float32)

    def copy_params(self):
        return [p.copy() for p in self.params]

    def set_params(self, params):
        n = len(self.weights)
        self.weights = [p.copy() for p in params[:n]]
        self.biases = [p.copy() for p in params[n:]]


class AdamW:
    """Optimizador Adam con 'weight decay' (mantiene los pesos pequenos)."""

    def __init__(self, params, lr=1e-3, betas=(0.9, 0.999), eps=1e-8, weight_decay=1e-4, n_decay=None):
        self.lr = lr
        self.b1, self.b2 = betas
        self.eps = eps
        self.wd = weight_decay
        self.n_decay = len(params) if n_decay is None else n_decay  # solo pesos, no biases
        self.m = [np.zeros_like(p) for p in params]
        self.v = [np.zeros_like(p) for p in params]
        self.t = 0

    def step(self, params, grads):
        self.t += 1
        b1t = 1 - self.b1 ** self.t
        b2t = 1 - self.b2 ** self.t
        for i, (p, g) in enumerate(zip(params, grads)):
            self.m[i] = self.b1 * self.m[i] + (1 - self.b1) * g
            self.v[i] = self.b2 * self.v[i] + (1 - self.b2) * (g * g)
            update = (self.m[i] / b1t) / (np.sqrt(self.v[i] / b2t) + self.eps)
            if i < self.n_decay:
                update = update + self.wd * p
            p -= (self.lr * update).astype(p.dtype)


def softmax(logits, temperature=1.0):
    z = logits / temperature
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def cross_entropy(logits, y, smoothing=0.0, class_weights=None):
    """Perdida (que tan mal le fue) y su gradiente respecto a los logits."""
    n, c = logits.shape
    probs = softmax(logits)
    target = np.full((n, c), smoothing / c, dtype=np.float64)
    target[np.arange(n), y] += 1.0 - smoothing
    w = np.ones(n) if class_weights is None else class_weights[y]
    logp = np.log(np.clip(probs, 1e-12, 1.0))
    loss = float((-(target * logp).sum(axis=1) * w).sum() / w.sum())
    grad = (probs - target) * (w / w.sum())[:, None]
    return loss, grad.astype(np.float32)


def fit_temperature(logits, y):
    """Busca la 'temperatura' que hace que las probabilidades sean honestas.

    Sin esto, una red suele decir "99% seguro" aunque se equivoque. Con la
    temperatura correcta, "80% seguro" significa que acierta ~80% de las veces.
    """
    if len(y) == 0:
        return 1.0

    def nll(temp):
        p = softmax(logits, temp)
        return -np.log(np.clip(p[np.arange(len(y)), y], 1e-12, 1.0)).mean()

    lo, hi = np.log(0.25), np.log(5.0)
    for _ in range(40):  # busqueda de la seccion dorada
        a = hi - (hi - lo) * 0.618
        b = lo + (hi - lo) * 0.618
        if nll(np.exp(a)) < nll(np.exp(b)):
            hi = b
        else:
            lo = a
    return float(np.exp((lo + hi) / 2))


class TrainingCancelled(Exception):
    pass


def train_mlp(x_train, y_train, x_val, y_val, n_classes, *, hidden=(256, 128), dropout=(0.3, 0.2),
              lr=1e-3, weight_decay=1e-4, batch_size=128, max_epochs=60, patience=10,
              smoothing=0.05, seed=0, on_epoch=None, should_cancel=None):
    """Entrena la red y regresa la version que mejor le fue en validacion."""
    rng = np.random.default_rng(seed)
    model = MLP(x_train.shape[1], n_classes, hidden, dropout, seed)
    opt = AdamW(model.params, lr=lr, weight_decay=weight_decay, n_decay=len(model.weights))

    counts = np.bincount(y_train, minlength=n_classes).astype(np.float64)
    class_weights = np.where(counts > 0, counts.sum() / np.maximum(counts, 1) / n_classes, 0.0)

    has_val = len(y_val) > 0
    best = (np.inf, model.copy_params(), 0)
    stale = 0
    plateau = 0
    for epoch in range(max_epochs):
        if should_cancel and should_cancel():
            raise TrainingCancelled()
        order = rng.permutation(len(x_train))
        for start in range(0, len(order), batch_size):
            idx = order[start:start + batch_size]
            if len(idx) < 2:
                continue
            logits, cache = model.forward(x_train[idx], train=True, rng=rng)
            _, grad = cross_entropy(logits, y_train[idx], smoothing, class_weights)
            opt.step(model.params, model.backward(cache, grad))

        if has_val:
            val_loss, _ = cross_entropy(model.logits(x_val), y_val)
        else:
            val_loss = float(max_epochs - epoch)  # sin validacion: quedarse con la ultima
        if val_loss < best[0] - 1e-4:
            best = (val_loss, model.copy_params(), epoch)
            stale = plateau = 0
        else:
            stale += 1
            plateau += 1
            if plateau >= 4:  # se estanco: aprender mas despacio
                opt.lr = max(opt.lr * 0.5, 1e-5)
                plateau = 0
        if on_epoch:
            on_epoch(epoch, max_epochs, val_loss)
        if has_val and stale >= patience:
            break

    model.set_params(best[1])
    return model
