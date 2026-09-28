package mx.miratek.senas.core

import kotlin.math.abs
import kotlin.math.ln
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sqrt

/**
 * De frames a numeros: copia EXACTA de miratek/features.py.
 *
 * Una ventana de ~2 segundos de manos se convierte en un vector de 728 numeros.
 * Si cambian algo aqui, cambienlo tambien en Python (y al reves): las pruebas
 * de paridad (FeaturesParityTest) comparan ambos resultados.
 *
 * Formato de cada frame: 126 numeros = 2 manos x 21 puntos x (x, y, z).
 * Indice = mano * 63 + punto * 3 + coordenada. NaN si la mano no aparece.
 */
object Features {
    const val FEATURE_VERSION = 1
    const val N_STEPS = 16
    const val N_SEGMENTS = 4
    const val MAX_GAP = 0.25
    const val FEATURE_SIZE = 2 * N_SEGMENTS * 60 + 2 * 60 + N_STEPS * 4 + N_STEPS * 2 +
        2 * N_SEGMENTS * 2 + N_SEGMENTS * 2 + 2 * N_SEGMENTS
    private const val DEFAULT_PALM = 0.12
    private val PALM = intArrayOf(5, 9, 13, 17)
    const val LEFT = 0
    const val RIGHT = 1

    /** Ventana remuestreada: [paso][mano][punto][coord]. */
    class Resampled(
        val img: Array<Array<Array<DoubleArray>>>,
        val wld: Array<Array<Array<DoubleArray>>>,
        val present: Array<BooleanArray>,
    )

    fun windowFeatures(
        times: DoubleArray,
        image: List<FloatArray>,
        world: List<FloatArray>,
        aspect: Double,
        windowS: Double,
        tEnd: Double = times.last(),
        holdEdges: Boolean = false,
    ): FloatArray {
        if (times.isEmpty()) return FloatArray(FEATURE_SIZE)
        return fromResampled(resample(times, image, world, windowS, tEnd, holdEdges), aspect)
    }

    // ------------------------------------------------------------------
    // Remuestreo en el tiempo (como _resample_slot en Python)
    // ------------------------------------------------------------------

    fun resample(
        times: DoubleArray, image: List<FloatArray>, world: List<FloatArray>,
        windowS: Double, tEnd: Double, holdEdges: Boolean,
    ): Resampled {
        // Igual que np.linspace: inicio + i * paso, y el ultimo exactamente tEnd
        val start = tEnd - windowS
        val step = (tEnd - start) / (N_STEPS - 1)
        val grid = DoubleArray(N_STEPS) { i -> if (i == N_STEPS - 1) tEnd else start + i * step }
        val img = Array(N_STEPS) { Array(2) { Array(21) { DoubleArray(3) { Double.NaN } } } }
        val wld = Array(N_STEPS) { Array(2) { Array(21) { DoubleArray(3) { Double.NaN } } } }
        val present = Array(N_STEPS) { BooleanArray(2) }
        val n = times.size
        for (slot in 0..1) {
            val base = slot * 63
            val idx = (0 until n).filter { k ->
                !image[k][base].isNaN() && !world[k][base].isNaN()
            }
            if (idx.isEmpty()) continue
            val tp = DoubleArray(idx.size) { times[idx[it]] }
            for (g in 0 until N_STEPS) {
                val t = grid[g]
                val j = searchLeft(tp, t)
                val jn = min(j, tp.size - 1)
                val jp = max(j - 1, 0)
                val hasNext = j < tp.size
                val hasPrev = j > 0
                val dn = if (hasNext) tp[jn] - t else Double.POSITIVE_INFINITY
                val dp = if (hasPrev) t - tp[jp] else Double.POSITIVE_INFINITY
                var useN = dn <= MAX_GAP
                var useP = dp <= MAX_GAP
                if (holdEdges) {
                    useN = useN || !hasPrev
                    useP = useP || !hasNext
                }
                if (!useN && !useP) continue
                present[g][slot] = true
                val kn = idx[jn]
                val kp = idx[jp]
                for (p in 0 until 21) for (c in 0 until 3) {
                    val o = base + p * 3 + c
                    img[g][slot][p][c] = mix(image[kp][o], image[kn][o], useP, useN, dp, dn)
                    wld[g][slot][p][c] = mix(world[kp][o], world[kn][o], useP, useN, dp, dn)
                }
            }
        }
        return Resampled(img, wld, present)
    }

    private fun mix(prev: Float, next: Float, useP: Boolean, useN: Boolean, dp: Double, dn: Double): Double =
        when {
            useP && useN -> {
                val w = dp / (dp + dn)
                prev.toDouble() * (1 - w) + next.toDouble() * w
            }
            useN -> next.toDouble()
            else -> prev.toDouble()
        }

    /** Primer indice con tp[i] >= t (como np.searchsorted side="left"). */
    private fun searchLeft(tp: DoubleArray, t: Double): Int {
        var lo = 0
        var hi = tp.size
        while (lo < hi) {
            val mid = (lo + hi) ushr 1
            if (tp[mid] < t) lo = mid + 1 else hi = mid
        }
        return lo
    }

    // ------------------------------------------------------------------
    // Ayudantes estadisticos que ignoran NaN
    // ------------------------------------------------------------------

    private fun nanMean(values: DoubleArray): Double {
        var sum = 0.0
        var count = 0
        for (v in values) if (!v.isNaN()) { sum += v; count++ }
        return if (count == 0) Double.NaN else sum / count
    }

    private fun nanMedian(values: DoubleArray): Double {
        val valid = values.filter { !it.isNaN() }.sorted()
        if (valid.isEmpty()) return Double.NaN
        val n = valid.size
        return (valid[(n - 1) / 2] + valid[n / 2]) / 2.0
    }

    private fun dist(a: DoubleArray, b: DoubleArray, dims: Int): Double {
        var s = 0.0
        for (c in 0 until dims) { val d = a[c] - b[c]; s += d * d }
        return sqrt(s)
    }

    private fun palmSize(points: Array<DoubleArray>, dims: Int): Double {
        var s = 0.0
        for (p in PALM) s += dist(points[p], points[0], dims)
        return s / PALM.size
    }

    /** Promedio (ignorando NaN) de cada etapa de 4 pasos. */
    private fun segmentMean(values: (step: Int) -> Double): DoubleArray {
        val per = N_STEPS / N_SEGMENTS
        return DoubleArray(N_SEGMENTS) { s -> nanMean(DoubleArray(per) { k -> values(s * per + k) }) }
    }

    // ------------------------------------------------------------------
    // El vector final (como features_from_resampled en Python)
    // ------------------------------------------------------------------

    fun fromResampled(r: Resampled, aspect: Double): FloatArray {
        // Coordenadas "cuadradas": x multiplicada por el aspecto de la imagen
        var xy = Array(N_STEPS) { g -> Array(2) { s -> Array(21) { p ->
            doubleArrayOf(r.img[g][s][p][0] * aspect, r.img[g][s][p][1])
        } } }
        var wld = r.wld
        var present = r.present
        var palmPx = Array(N_STEPS) { g -> DoubleArray(2) { s -> palmSize(xy[g][s], 2) } }

        // --- Mano dominante: la que aparece y se mueve mas va a la derecha ---
        val medians = DoubleArray(2) { s -> nanMedian(DoubleArray(N_STEPS) { g -> palmPx[g][s] }) }
        var scale = nanMean(medians)
        if (scale.isNaN() || scale <= 1e-6) scale = DEFAULT_PALM
        val energy = DoubleArray(2) { s ->
            var path = 0.0
            for (g in 1 until N_STEPS) {
                val d = dist(xy[g][s][0], xy[g - 1][s][0], 2)
                if (!d.isNaN()) path += d
            }
            val count = (0 until N_STEPS).count { present[it][s] }
            count * (1.0 + path / scale)
        }
        if (energy[LEFT] > 1.2 * energy[RIGHT] + 1e-6) {
            val oldXy = xy
            xy = Array(N_STEPS) { g -> Array(2) { s -> Array(21) { p ->
                val q = oldXy[g][1 - s][p]
                doubleArrayOf(aspect - q[0], q[1])
            } } }
            val oldW = wld
            wld = Array(N_STEPS) { g -> Array(2) { s -> Array(21) { p ->
                val q = oldW[g][1 - s][p]
                doubleArrayOf(-q[0], q[1], q[2])
            } } }
            val oldP = present
            present = Array(N_STEPS) { g -> booleanArrayOf(oldP[g][1], oldP[g][0]) }
            val oldPalm = palmPx
            palmPx = Array(N_STEPS) { g -> doubleArrayOf(oldPalm[g][1], oldPalm[g][0]) }
        }

        val out = ArrayList<Double>(FEATURE_SIZE)

        // --- Forma de la mano (3D, relativa a la muneca, en "palmas") ---
        val palmW = DoubleArray(2) { s ->
            val m = nanMedian(DoubleArray(N_STEPS) { g -> palmSize(wld[g][s], 3) })
            if (!m.isNaN() && m > 1e-6) m else 1.0
        }
        val shape = Array(N_STEPS) { g -> Array(2) { s -> DoubleArray(60) { k ->
            val p = k / 3 + 1
            val c = k % 3
            (wld[g][s][p][c] - wld[g][s][0][c]) / palmW[s]
        } } }
        for (s in 0..1) for (seg in 0 until N_SEGMENTS) {
            val per = N_STEPS / N_SEGMENTS
            for (k in 0 until 60) out.add(nanMean(DoubleArray(per) { i -> shape[seg * per + i][s][k] }))
        }
        for (s in 0..1) for (k in 0 until 60) {
            out.add(nanMean(DoubleArray(N_STEPS - 1) { g -> abs(shape[g + 1][s][k] - shape[g][s][k]) }))
        }

        // --- Movimiento de la muneca ---
        val wristMean = Array(2) { s -> DoubleArray(2) { c -> nanMean(DoubleArray(N_STEPS) { g -> xy[g][s][0][c] }) } }
        for (g in 0 until N_STEPS) for (s in 0..1) for (c in 0..1) {
            out.add((xy[g][s][0][c] - wristMean[s][c]) / scale)
        }
        val palmMed = DoubleArray(2) { s -> nanMedian(DoubleArray(N_STEPS) { g -> palmPx[g][s] }) }
        for (g in 0 until N_STEPS) for (s in 0..1) out.add(ln(palmPx[g][s] / palmMed[s]))
        val center = doubleArrayOf(aspect / 2.0, 0.5)
        for (s in 0..1) {
            val segs = Array(2) { c -> segmentMean { g -> (xy[g][s][0][c] - center[c]) / scale } }
            for (seg in 0 until N_SEGMENTS) for (c in 0..1) out.add(segs[c][seg])
        }
        val inter = Array(2) { c ->
            segmentMean { g -> (xy[g][RIGHT][0][c] - xy[g][LEFT][0][c]) / scale }
        }
        for (seg in 0 until N_SEGMENTS) for (c in 0..1) out.add(inter[c][seg])
        for (s in 0..1) {
            val seg = segmentMean { g -> if (present[g][s]) 1.0 else 0.0 }
            for (v in seg) out.add(v)
        }

        check(out.size == FEATURE_SIZE) { "tamano ${out.size}" }
        return FloatArray(FEATURE_SIZE) { i ->
            val v = out[i]
            if (v.isNaN() || v.isInfinite()) 0f else v.coerceIn(-10.0, 10.0).toFloat()
        }
    }
}
