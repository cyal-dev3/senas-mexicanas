package mx.miratek.senas.core

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Mismas pruebas que tests/test_recognizer.py, con un modelo falso. */
class RecognizerTest {
    private class Scripted : SignClassifier {
        override val signs = listOf(
            SignInfo("hola", "Hola", SignInfo.CATEGORY_WORDS, null),
            SignInfo("gracias", "Gracias", SignInfo.CATEGORY_WORDS, null),
            SignInfo("nada", "Nada", SignInfo.CATEGORY_WORDS, null),
        )
        override val windowS = 1.0
        var next = doubleArrayOf(0.0, 0.0, 1.0)
        override fun predictProba(features: FloatArray) = next
    }

    private val hands: FrameHands = FrameHands.empty().also { h ->
        val rnd = java.util.Random(0)
        for (i in 63 until 126) { h.image[i] = rnd.nextFloat(); h.world[i] = h.image[i] * 0.05f }
    }

    private fun run(rec: LiveRecognizer, model: Scripted, probs: DoubleArray, frames: Int, t0: Double,
                    frame: FrameHands = hands): Pair<List<String>, Double> {
        model.next = probs
        val events = ArrayList<String>()
        var t = t0
        repeat(frames) {
            t += 1.0 / 30
            val (_, event) = rec.push(t, frame.image, frame.world, frame.any)
            if (event != null) events += event.sign.id
        }
        return events to t
    }

    @Test
    fun emitsOncePerHeldSignAndRearmsAfterNothing() {
        val model = Scripted()
        val rec = LiveRecognizer(model, smoothing = 0.0, cooldownS = 0.2)
        var (_, t) = run(rec, model, doubleArrayOf(0.0, 0.0, 1.0), 30, 0.0)
        val (held, t2) = run(rec, model, doubleArrayOf(0.9, 0.05, 0.05), 60, t)
        assertEquals(listOf("hola"), held)
        t = run(rec, model, doubleArrayOf(0.05, 0.05, 0.9), 20, t2).second
        assertEquals(listOf("hola"), run(rec, model, doubleArrayOf(0.9, 0.05, 0.05), 20, t).first)
    }

    @Test
    fun lowConfidenceNeverEmits() {
        val model = Scripted()
        val rec = LiveRecognizer(model, smoothing = 0.0)
        assertTrue(run(rec, model, doubleArrayOf(0.4, 0.35, 0.25), 90, 0.0).first.isEmpty())
    }

    @Test
    fun noHandsResets() {
        val model = Scripted()
        val rec = LiveRecognizer(model, smoothing = 0.0)
        var last: Prediction? = null
        model.next = doubleArrayOf(0.9, 0.05, 0.05)
        var t = 0.0
        repeat(40) {
            t += 1.0 / 30
            val empty = FrameHands.empty()
            val (p, e) = rec.push(t, empty.image, empty.world, false)
            assertEquals(null, e)
            if (p != null) last = p
        }
        assertFalse(last!!.handsVisible)
    }

    @Test
    fun slotAssignmentFixesDuplicateLabels() {
        fun det(label: String, x: Float) = Detection(label, FloatArray(63) { if (it % 3 == 0) x else 0f }, FloatArray(63))
        val h = HandSlots.assign(listOf(det("Right", 0.7f), det("Right", 0.3f)), null)
        assertEquals(0.7f, h.image[63])
        assertEquals(0.3f, h.image[0])
        val prev = HandSlots.assign(listOf(det("Right", 0.6f)), null)
        val flipped = HandSlots.assign(listOf(det("Left", 0.61f)), prev)
        assertTrue(flipped.present(1) && !flipped.present(0))
    }
}
