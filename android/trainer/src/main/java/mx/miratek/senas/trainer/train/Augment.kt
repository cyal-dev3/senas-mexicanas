package mx.miratek.senas.trainer.train

import mx.miratek.senas.trainer.data.Clip
import java.util.Random
import kotlin.math.cos
import kotlin.math.sin

/** Un clip con variaciones: image/world/tiempos nuevos y donde termina la ventana. */
class Augmented(val image: List<FloatArray>, val world: List<FloatArray>, val times: DoubleArray, val tEnd: Double)

/**
 * Data augmentation, copia de miratek/augment.py: variaciones realistas de cada
 * clip para que el modelo aprenda mejor con pocos datos. Simulamos cosas que de
 * verdad pasan frente a una camara: mas cerca o lejos, mas a un lado, camara un
 * poco chueca, sena mas rapida o lenta, ventana corrida, frames sin mano y la
 * cola de la sena anterior al inicio de la ventana (como pasa en vivo).
 */
object Augment {
    private const val FRAME = 126

    private fun Random.uniform(lo: Double, hi: Double) = lo + (hi - lo) * nextDouble()

    /** Variacion geometrica y de velocidad de un clip (sin decidir todavia la ventana). */
    fun geometric(image: List<FloatArray>, world: List<FloatArray>, times: DoubleArray, aspect: Double, rng: Random): Augmented {
        val n = times.size
        // Velocidad: la misma sena, un poco mas rapida o lenta
        val speed = rng.uniform(0.85, 1.18)
        val t0 = times[0]
        val tNew = DoubleArray(n) { (times[it] - t0) / speed }

        // Centro de giro: promedio de la muneca (en coordenadas cuadradas)
        var sx = 0.0
        var sy = 0.0
        var count = 0
        for (f in 0 until n) for (s in 0..1) {
            val x = image[f][s * 63]
            val y = image[f][s * 63 + 1]
            if (!x.isNaN() && !y.isNaN()) {
                sx += x * aspect; sy += y; count++
            }
        }
        val cx = if (count > 0) sx / count else aspect / 2
        val cy = if (count > 0) sy / count else 0.5

        // Camara: escala, giro (~8 grados) y traslacion
        val theta = rng.uniform(-0.14, 0.14)
        val scale = rng.uniform(0.82, 1.18)
        val dx = rng.uniform(-0.09, 0.09)
        val dy = rng.uniform(-0.09, 0.09)
        val c = cos(theta)
        val s = sin(theta)
        val img = List(n) { FloatArray(FRAME) }
        val wld = List(n) { FloatArray(FRAME) }
        for (f in 0 until n) {
            val src = image[f]
            val srw = world[f]
            val di = img[f]
            val dw = wld[f]
            for (p in 0 until 42) {
                val o = p * 3
                val x = src[o] * aspect
                val y = src[o + 1]
                val xc = x - cx
                val yc = y - cy
                // Temblor pequeno (como el ruido normal de MediaPipe); NaN se queda NaN
                di[o] = (((c * xc - s * yc) * scale + cx + dx) / aspect + rng.nextGaussian() * 0.002).toFloat()
                di[o + 1] = ((s * xc + c * yc) * scale + cy + dy + rng.nextGaussian() * 0.002).toFloat()
                di[o + 2] = (src[o + 2] * scale).toFloat()
                val wx = srw[o]
                val wy = srw[o + 1]
                dw[o] = (c * wx - s * wy + rng.nextGaussian() * 0.0015).toFloat()
                dw[o + 1] = (s * wx + c * wy + rng.nextGaussian() * 0.0015).toFloat()
                dw[o + 2] = (srw[o + 2] + rng.nextGaussian() * 0.0015).toFloat()
            }
            // Perdidas de deteccion en algunos frames
            for (hand in 0..1) if (rng.nextDouble() < 0.05) {
                for (k in hand * 63 until hand * 63 + 63) {
                    di[k] = Float.NaN; dw[k] = Float.NaN
                }
            }
        }
        return Augmented(img, wld, tNew, tNew[n - 1])
    }

    /**
     * Fija donde termina la ventana y rellena los bordes repitiendo el primer/ultimo
     * frame TAL CUAL (si ahi no habia mano, sigue sin haberla: no se inventan manos).
     */
    fun window(a: Augmented, tEnd: Double, windowS: Double): Augmented {
        val image = ArrayList(a.image)
        val world = ArrayList(a.world)
        val times = a.times.toMutableList()
        val start = tEnd - windowS
        if (start < times.first()) {
            image.add(0, image.first().copyOf()); world.add(0, world.first().copyOf()); times.add(0, start)
        }
        if (tEnd > times.last()) {
            image.add(image.last().copyOf()); world.add(world.last().copyOf()); times.add(tEnd)
        }
        return Augmented(image, world, times.toDoubleArray(), tEnd)
    }

    /** Copia normal: variacion geometrica + ventana un poco corrida. */
    fun clip(clip: Clip, rng: Random, windowS: Double): Augmented {
        val g = geometric(clip.image, clip.world, clip.times, clip.aspect, rng)
        return window(g, g.times.last() + rng.uniform(-0.4, 0.3), windowS)
    }

    /**
     * Transicion: la ventana empieza con la cola de OTRA sena (o de "nada") y
     * termina antes de que acabe la sena buscada. Asi el modelo aprende a
     * reconocerla en cuanto lleva ~1.2-1.7 s en pantalla, sin esperar a que
     * salga por completo la sena anterior.
     */
    fun transition(clip: Clip, prefix: Clip, rng: Random, windowS: Double): Augmented {
        val g = geometric(clip.image, clip.world, clip.times, clip.aspect, rng)
        val gap = rng.uniform(0.05, 0.25)
        val shift = rng.uniform(0.3, 0.8)
        val pEnd = prefix.times.last()
        val offset = g.times.first() - gap - pEnd
        val times = DoubleArray(prefix.frames + g.times.size)
        for (i in 0 until prefix.frames) times[i] = prefix.times[i] + offset
        for (i in g.times.indices) times[prefix.frames + i] = g.times[i]
        val image = prefix.image + g.image
        val world = prefix.world + g.world
        return window(Augmented(image, world, times, g.times.last()), g.times.last() - shift, windowS)
    }
}
