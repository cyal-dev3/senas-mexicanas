package mx.miratek.senas.trainer.train

import java.util.Random
import java.util.concurrent.Callable
import java.util.concurrent.ExecutionException
import java.util.concurrent.Executors
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sqrt

class TrainingCancelled : Exception("Entrenamiento cancelado")

/** Reparte un ciclo entre los nucleos del telefono (las multiplicaciones de matrices son lo lento). */
object Par {
    val threads: Int = Runtime.getRuntime().availableProcessors().coerceIn(1, 8)
    private val pool = Executors.newFixedThreadPool(threads) { r -> Thread(r, "miratek-train").apply { isDaemon = true } }

    fun forRange(n: Int, body: (from: Int, to: Int) -> Unit) {
        if (n < 32 || threads == 1) {
            if (n > 0) body(0, n)
            return
        }
        val chunks = min(threads, n)
        val size = (n + chunks - 1) / chunks
        val tasks = (0 until chunks).map { k ->
            Callable { body(k * size, min(n, (k + 1) * size)) }
        }
        try {
            for (f in pool.invokeAll(tasks)) f.get()
        } catch (e: ExecutionException) {
            throw e.cause ?: e
        }
    }
}

/**
 * Red neuronal MLP escrita a mano, copia de miratek/mlp.py:
 *     entrada (728 numeros) -> 256 neuronas -> 128 neuronas -> una salida por sena
 * Los pesos van en arreglos planos [entrada * salida], fila por fila (igual que
 * los lee SignModel en la app de traduccion).
 */
class Mlp(val nIn: Int, val nOut: Int, val hidden: IntArray, val dropout: FloatArray, seed: Long) {
    val sizes: IntArray = intArrayOf(nIn, *hidden, nOut)
    val layers: Int = sizes.size - 1
    var weights: Array<FloatArray> = Array(layers) { l -> FloatArray(sizes[l] * sizes[l + 1]) }
    var biases: Array<FloatArray> = Array(layers) { l -> FloatArray(sizes[l + 1]) }

    init {
        val rng = Random(seed)
        for (l in 0 until layers) {
            val sd = sqrt(2.0 / sizes[l])  // inicializacion "He": buena para capas con ReLU
            val w = weights[l]
            for (i in w.indices) w[i] = (rng.nextGaussian() * sd).toFloat()
        }
    }

    /** Lo que backward necesita: la entrada de cada capa y las mascaras de dropout. */
    class Cache(val acts: Array<FloatArray>, val masks: Array<FloatArray?>, val n: Int)

    class Grads(val weights: Array<FloatArray>, val biases: Array<FloatArray>) {
        val all: List<FloatArray> get() = weights.toList() + biases.toList()
    }

    val params: List<FloatArray> get() = weights.toList() + biases.toList()

    /** y = x W + b para n filas (paralelo por filas). */
    private fun linear(x: FloatArray, n: Int, nI: Int, nO: Int, w: FloatArray, b: FloatArray): FloatArray {
        val out = FloatArray(n * nO)
        Par.forRange(n) { from, to ->
            for (r in from until to) {
                val o = r * nO
                System.arraycopy(b, 0, out, o, nO)
                val xr = r * nI
                for (i in 0 until nI) {
                    val xi = x[xr + i]
                    if (xi == 0f) continue  // tras ReLU muchas entradas son 0
                    val row = i * nO
                    for (j in 0 until nO) out[o + j] += xi * w[row + j]
                }
            }
        }
        return out
    }

    fun forward(x: FloatArray, n: Int, train: Boolean, rng: Random?): Pair<FloatArray, Cache> {
        val acts = arrayOfNulls<FloatArray>(layers)
        val masks = arrayOfNulls<FloatArray>(max(layers - 1, 0))
        var h = x
        for (l in 0 until layers) {
            acts[l] = h
            val out = linear(h, n, sizes[l], sizes[l + 1], weights[l], biases[l])
            if (l < layers - 1) {
                val p = if (l < dropout.size) dropout[l] else 0f
                if (train && p > 0f && rng != null) {
                    val keep = 1f / (1f - p)
                    val mask = FloatArray(out.size)
                    for (i in mask.indices) mask[i] = if (rng.nextFloat() >= p) keep else 0f
                    for (i in out.indices) out[i] = max(out[i], 0f) * mask[i]
                    masks[l] = mask
                } else {
                    for (i in out.indices) out[i] = max(out[i], 0f)
                }
            }
            h = out
        }
        @Suppress("UNCHECKED_CAST")
        return h to Cache(acts as Array<FloatArray>, masks, n)
    }

    /** Gradientes de pesos y sesgos a partir del gradiente de los logits. */
    fun backward(c: Cache, dLogits: FloatArray): Grads {
        val gW = Array(layers) { FloatArray(weights[it].size) }
        val gB = Array(layers) { FloatArray(biases[it].size) }
        var d = dLogits
        val n = c.n
        for (l in layers - 1 downTo 0) {
            val nI = sizes[l]
            val nO = sizes[l + 1]
            val a = c.acts[l]
            val gw = gW[l]
            // gW = a^T d  (paralelo por filas de entrada: cada hilo escribe filas distintas)
            Par.forRange(nI) { from, to ->
                for (i in from until to) {
                    val row = i * nO
                    for (r in 0 until n) {
                        val ai = a[r * nI + i]
                        if (ai == 0f) continue
                        val dr = r * nO
                        for (j in 0 until nO) gw[row + j] += ai * d[dr + j]
                    }
                }
            }
            val gb = gB[l]
            for (r in 0 until n) {
                val dr = r * nO
                for (j in 0 until nO) gb[j] += d[dr + j]
            }
            if (l > 0) {
                // d_prev = (d W^T) * mascara * (a > 0)
                val w = weights[l]
                val mask = c.masks[l - 1]
                val dPrev = FloatArray(n * nI)
                Par.forRange(n) { from, to ->
                    for (r in from until to) {
                        val dr = r * nO
                        val pr = r * nI
                        for (i in 0 until nI) {
                            if (a[pr + i] <= 0f) continue  // ReLU apagada o dropout
                            var s = 0f
                            val row = i * nO
                            for (j in 0 until nO) s += d[dr + j] * w[row + j]
                            dPrev[pr + i] = if (mask != null) s * mask[pr + i] else s
                        }
                    }
                }
                d = dPrev
            }
        }
        return Grads(gW, gB)
    }

    fun logits(x: FloatArray, n: Int): FloatArray = if (n == 0) FloatArray(0) else forward(x, n, false, null).first

    fun copyParams(): List<FloatArray> = params.map { it.copyOf() }

    fun setParams(p: List<FloatArray>) {
        weights = Array(layers) { p[it].copyOf() }
        biases = Array(layers) { p[layers + it].copyOf() }
    }
}

/** Optimizador Adam con 'weight decay' (solo en los pesos, no en los sesgos). */
class AdamW(
    params: List<FloatArray>,
    var lr: Double,
    private val weightDecay: Double,
    private val nDecay: Int,
    private val b1: Double = 0.9,
    private val b2: Double = 0.999,
    private val eps: Double = 1e-8,
) {
    private val m = params.map { FloatArray(it.size) }
    private val v = params.map { FloatArray(it.size) }
    private var t = 0

    fun step(params: List<FloatArray>, grads: List<FloatArray>) {
        t++
        val b1t = 1 - b1.pow(t)
        val b2t = 1 - b2.pow(t)
        for ((i, p) in params.withIndex()) {
            val g = grads[i]
            val mi = m[i]
            val vi = v[i]
            val decay = i < nDecay
            Par.forRange(p.size) { from, to ->
                for (k in from until to) {
                    val gk = g[k].toDouble()
                    val mk = b1 * mi[k] + (1 - b1) * gk
                    val vk = b2 * vi[k] + (1 - b2) * gk * gk
                    mi[k] = mk.toFloat()
                    vi[k] = vk.toFloat()
                    var update = (mk / b1t) / (sqrt(vk / b2t) + eps)
                    if (decay) update += weightDecay * p[k]
                    p[k] = (p[k] - lr * update).toFloat()
                }
            }
        }
    }
}

class LossGrad(val loss: Double, val grad: FloatArray)

object Loss {
    /** Softmax de UNA fila de logits con temperatura (probabilidades que suman 1). */
    fun softmaxRow(logits: FloatArray, offset: Int, c: Int, temperature: Double = 1.0): DoubleArray {
        var top = Double.NEGATIVE_INFINITY
        for (j in 0 until c) top = max(top, logits[offset + j] / temperature)
        val e = DoubleArray(c) { exp(logits[offset + it] / temperature - top) }
        val sum = e.sum()
        return DoubleArray(c) { e[it] / sum }
    }

    /** Perdida (que tan mal le fue) y su gradiente respecto a los logits. */
    fun crossEntropy(
        logits: FloatArray, n: Int, c: Int, y: IntArray, smoothing: Double, classWeights: DoubleArray?,
    ): LossGrad {
        val grad = FloatArray(n * c)
        val rowWeight = DoubleArray(n)
        var wsum = 0.0
        var total = 0.0
        for (r in 0 until n) {
            val off = r * c
            val p = softmaxRow(logits, off, c)
            val w = classWeights?.get(y[r]) ?: 1.0
            rowWeight[r] = w
            wsum += w
            var loss = 0.0
            for (j in 0 until c) {
                val target = smoothing / c + (if (j == y[r]) 1.0 - smoothing else 0.0)
                loss -= target * ln(max(p[j], 1e-12))
                grad[off + j] = (p[j] - target).toFloat()
            }
            total += loss * w
        }
        if (wsum <= 0.0) wsum = 1.0
        for (r in 0 until n) {
            val scale = (rowWeight[r] / wsum).toFloat()
            val off = r * c
            for (j in 0 until c) grad[off + j] *= scale
        }
        return LossGrad(total / wsum, grad)
    }

    /**
     * Busca la 'temperatura' que hace honestas las probabilidades: con ella,
     * "80% seguro" significa que acierta ~80% de las veces.
     */
    fun fitTemperature(logits: FloatArray, n: Int, c: Int, y: IntArray): Double =
        fitTemperatureRows(List(n) { r -> logits.copyOfRange(r * c, (r + 1) * c) to y[r] })

    /** Igual, pero cada fila trae sus propios logits (pueden ser de modelos con distintas clases). */
    fun fitTemperatureRows(rows: List<Pair<FloatArray, Int>>): Double {
        if (rows.isEmpty()) return 1.0
        fun nll(temp: Double): Double {
            var s = 0.0
            for ((logits, y) in rows) {
                val p = softmaxRow(logits, 0, logits.size, temp)
                s -= ln(max(p[y], 1e-12))
            }
            return s / rows.size
        }
        var lo = ln(0.25)
        var hi = ln(5.0)
        repeat(40) {  // busqueda de la seccion dorada
            val a = hi - (hi - lo) * 0.618
            val b = lo + (hi - lo) * 0.618
            if (nll(exp(a)) < nll(exp(b))) hi = b else lo = a
        }
        return exp((lo + hi) / 2)
    }
}

/** Entrena la red y regresa la version que mejor le fue en validacion (copia de train_mlp). */
fun trainMlp(
    xTrain: FloatArray, yTrain: IntArray, nTrain: Int,
    xVal: FloatArray, yVal: IntArray, nVal: Int,
    nIn: Int, nClasses: Int, cfg: TrainConfig, maxEpochs: Int, seed: Long,
    onEpoch: (epoch: Int, total: Int, valLoss: Double) -> Unit = { _, _, _ -> },
    shouldCancel: () -> Boolean = { false },
): Mlp {
    val rng = Random(seed)
    val model = Mlp(nIn, nClasses, cfg.hidden, cfg.dropout, seed)
    val params = model.params
    val opt = AdamW(params, cfg.lr, cfg.weightDecay, model.weights.size)

    val counts = DoubleArray(nClasses)
    for (i in 0 until nTrain) counts[yTrain[i]]++
    val classWeights = DoubleArray(nClasses) { if (counts[it] > 0) nTrain / max(counts[it], 1.0) / nClasses else 0.0 }

    val hasVal = nVal > 0
    var bestLoss = Double.POSITIVE_INFINITY
    var best = model.copyParams()
    var stale = 0
    var plateau = 0
    val order = IntArray(nTrain) { it }
    val batch = cfg.batchSize
    val xb = FloatArray(batch * nIn)
    val yb = IntArray(batch)
    for (epoch in 0 until maxEpochs) {
        if (shouldCancel()) throw TrainingCancelled()
        for (i in nTrain - 1 downTo 1) {  // barajar
            val j = rng.nextInt(i + 1)
            val tmp = order[i]; order[i] = order[j]; order[j] = tmp
        }
        var start = 0
        while (start < nTrain) {
            val m = min(batch, nTrain - start)
            if (m < 2) break
            for (r in 0 until m) {
                val src = order[start + r]
                System.arraycopy(xTrain, src * nIn, xb, r * nIn, nIn)
                yb[r] = yTrain[src]
            }
            if (cfg.inputNoise > 0) {
                // Ruido en la entrada: regulariza contra manos distintas a las grabadas
                val sd = cfg.inputNoise.toFloat()
                for (i in 0 until m * nIn) xb[i] += (rng.nextGaussian() * sd).toFloat()
            }
            val (logits, cache) = model.forward(xb, m, true, rng)
            val lg = Loss.crossEntropy(logits, m, nClasses, yb, cfg.smoothing, classWeights)
            opt.step(params, model.backward(cache, lg.grad).all)
            start += batch
        }

        val valLoss = if (hasVal) {
            Loss.crossEntropy(model.logits(xVal, nVal), nVal, nClasses, yVal, 0.0, null).loss
        } else {
            (maxEpochs - epoch).toDouble()  // sin validacion: quedarse con la ultima
        }
        if (valLoss < bestLoss - 1e-4) {
            bestLoss = valLoss
            best = model.copyParams()
            stale = 0; plateau = 0
        } else {
            stale++; plateau++
            if (plateau >= 4) {  // se estanco: aprender mas despacio
                opt.lr = max(opt.lr * 0.5, 1e-5)
                plateau = 0
            }
        }
        onEpoch(epoch, maxEpochs, valLoss)
        if (hasVal && stale >= cfg.patience) break
    }
    model.setParams(best)
    return model
}
