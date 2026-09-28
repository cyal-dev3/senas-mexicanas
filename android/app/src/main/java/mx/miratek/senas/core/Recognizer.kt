package mx.miratek.senas.core

/**
 * Reconocimiento en vivo estable: copia de miratek/recognizer.py.
 *
 * Junta los ultimos ~2 s, predice cada 2 frames, suaviza las probabilidades y
 * solo "confirma" una sena si gana varias veces seguidas con buena confianza.
 */
data class Prediction(
    val sign: SignInfo?,
    val confidence: Double,
    val top: List<Pair<SignInfo, Double>>,
    val handsVisible: Boolean,
)

data class SignEvent(val sign: SignInfo, val confidence: Double, val t: Double)

enum class Sensitivity(val threshold: Double, val minHits: Int, val label: String) {
    LOW(0.75, 4, "Baja"), MEDIUM(0.6, 3, "Media"), HIGH(0.45, 2, "Alta"),
}

/** Lo que el reconocedor necesita de un modelo (en las pruebas se usa uno falso). */
interface SignClassifier {
    val signs: List<SignInfo>
    val windowS: Double
    fun predictProba(features: FloatArray): DoubleArray
}

class LiveRecognizer(
    val model: SignClassifier,
    var aspect: Double = 0.75,
    private val hop: Int = 2,
    private val smoothing: Double = 0.5,
    sensitivity: Sensitivity = Sensitivity.MEDIUM,
    private val cooldownS: Double = 0.8,
) {
    private class Frame(val t: Double, val image: FloatArray, val world: FloatArray)

    private var threshold = sensitivity.threshold
    private var minHits = sensitivity.minHits
    private val nothingIndex = model.signs.indexOfFirst { it.isNothing }.takeIf { it >= 0 }
    private var mask: BooleanArray? = null

    private val frames = ArrayDeque<Frame>()
    private var count = 0
    private var probs: DoubleArray? = null
    private var candidate = -1
    private var hits = 0
    private var armedBlock = -1
    private var lastEmitT = -1e9
    private var lastHandT = -1e9

    val currentThreshold get() = threshold

    fun setSensitivity(s: Sensitivity) {
        threshold = s.threshold
        minHits = s.minHits
    }

    /** Solo compiten estas categorias (ej: letras al deletrear). "Nada" siempre compite. */
    fun setAllowedCategory(category: String?) {
        mask = if (category == null) null else BooleanArray(model.signs.size) { i ->
            val s = model.signs[i]
            s.isNothing || s.category == category
        }
        probs = null
        candidate = -1; hits = 0; armedBlock = -1
    }

    fun reset() {
        frames.clear()
        count = 0
        probs = null
        candidate = -1; hits = 0; armedBlock = -1
        lastEmitT = -1e9
        lastHandT = -1e9
    }

    fun push(t: Double, image: FloatArray, world: FloatArray, anyHands: Boolean): Pair<Prediction?, SignEvent?> {
        val horizon = model.windowS + 0.3
        frames.addLast(Frame(t, image, world))
        while (frames.isNotEmpty() && t - frames.first().t > horizon) frames.removeFirst()
        if (anyHands) lastHandT = t
        count++
        if (count % hop != 0) return null to null

        if (t - lastHandT > 0.5) {
            probs = null
            candidate = -1; hits = 0; armedBlock = -1
            return Prediction(null, 0.0, emptyList(), false) to null
        }
        val span = frames.last().t - frames.first().t
        if (span < 0.5 * model.windowS) return null to null

        val times = DoubleArray(frames.size) { frames[it].t }
        val feats = Features.windowFeatures(
            times, frames.map { it.image }, frames.map { it.world }, aspect, model.windowS, t,
        )
        var p = model.predictProba(feats)
        mask?.let { m ->
            if (m.any { it }) {
                val masked = DoubleArray(p.size) { if (m[it]) p[it] else 0.0 }
                val sum = masked.sum().coerceAtLeast(1e-9)
                p = DoubleArray(p.size) { masked[it] / sum }
            }
        }
        val prev = probs
        val smoothed = if (prev == null) p else DoubleArray(p.size) { smoothing * prev[it] + (1 - smoothing) * p[it] }
        probs = smoothed

        val order = smoothed.indices.sortedByDescending { smoothed[it] }
        val best = order.first()
        val conf = smoothed[best]
        val top = order.take(3).map { model.signs[it] to smoothed[it] }
        val prediction = Prediction(model.signs[best], conf, top, true)
        return prediction to updateEvents(best, conf, t)
    }

    private fun updateEvents(best: Int, conf: Double, t: Double): SignEvent? {
        val isSign = best != nothingIndex && conf >= threshold
        if (!isSign) {
            candidate = -1; hits = 0
            if (best == nothingIndex || conf < 0.7 * threshold) armedBlock = -1
            return null
        }
        if (best == candidate) {
            hits++
        } else {
            candidate = best; hits = 1
            if (armedBlock != -1 && best != armedBlock) armedBlock = -1
        }
        if (hits >= minHits && best != armedBlock && t - lastEmitT >= cooldownS) {
            armedBlock = best
            lastEmitT = t
            return SignEvent(model.signs[best], conf, t)
        }
        return null
    }
}
