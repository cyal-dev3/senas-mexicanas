package mx.miratek.senas.core

import kotlin.math.hypot

/**
 * Decide que mano va en la posicion izquierda y cual en la derecha.
 * Copia de assign_slots en miratek/hands.py (arregla confusiones de MediaPipe).
 */
class Detection(val label: String, val image: FloatArray, val world: FloatArray)  // 63 numeros cada uno

class FrameHands(val image: FloatArray, val world: FloatArray) {  // 126 numeros cada uno
    fun present(slot: Int) = !image[slot * 63].isNaN()
    val any get() = present(0) || present(1)

    companion object {
        fun empty() = FrameHands(FloatArray(126) { Float.NaN }, FloatArray(126) { Float.NaN })
    }
}

object HandSlots {
    private const val CONTINUITY_DISTANCE = 0.10

    fun assign(detections: List<Detection>, previous: FrameHands?): FrameHands {
        val hands = FrameHands.empty()
        if (detections.isEmpty()) return hands
        val slots: List<Pair<Int, Detection>> = if (detections.size >= 2) {
            val a = detections[0]
            val b = detections[1]
            if (a.label == b.label) {
                // Misma etiqueta. Si en el frame anterior habia dos manos, cada una se queda
                // en la posicion de la mas cercana. Si no, decidimos por la posicion
                // horizontal con la convencion que de verdad da MediaPipe en nuestras
                // imagenes (ya en espejo): "Right" cae en la mano MAS A LA IZQUIERDA.
                if (previous != null && previous.present(0) && previous.present(1)) {
                    val straight = dist(previous, 0, a) + dist(previous, 1, b)
                    val swapped = dist(previous, 0, b) + dist(previous, 1, a)
                    if (straight <= swapped) listOf(Features.LEFT to a, Features.RIGHT to b)
                    else listOf(Features.LEFT to b, Features.RIGHT to a)
                } else {
                    val (leftmost, rightmost) = if (a.image[0] <= b.image[0]) a to b else b to a
                    listOf(Features.RIGHT to leftmost, Features.LEFT to rightmost)
                }
            } else {
                listOf(a, b).map { (if (it.label == "Right") Features.RIGHT else Features.LEFT) to it }
            }
        } else {
            val det = detections[0]
            var slot = if (det.label == "Right") Features.RIGHT else Features.LEFT
            if (previous != null) {
                val other = 1 - slot
                if (previous.present(other) && !previous.present(slot)) {
                    val d = hypot(
                        (previous.image[other * 63] - det.image[0]).toDouble(),
                        (previous.image[other * 63 + 1] - det.image[1]).toDouble(),
                    )
                    if (d < CONTINUITY_DISTANCE) slot = other
                }
            }
            listOf(slot to det)
        }
        for ((slot, det) in slots) {
            det.image.copyInto(hands.image, slot * 63)
            det.world.copyInto(hands.world, slot * 63)
        }
        return hands
    }

    /** Distancia entre la muneca del frame anterior (en ese slot) y la de una deteccion. */
    private fun dist(previous: FrameHands, slot: Int, det: Detection): Double = hypot(
        (previous.image[slot * 63] - det.image[0]).toDouble(),
        (previous.image[slot * 63 + 1] - det.image[1]).toDouble(),
    )
}
