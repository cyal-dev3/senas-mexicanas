package mx.miratek.senas.trainer

import mx.miratek.senas.core.Features
import mx.miratek.senas.core.SignModel
import mx.miratek.senas.data.SignCatalog
import mx.miratek.senas.data.SignSpec
import mx.miratek.senas.trainer.data.Clip
import mx.miratek.senas.trainer.data.Npy
import mx.miratek.senas.trainer.data.Npz
import mx.miratek.senas.trainer.train.TrainConfig
import mx.miratek.senas.trainer.train.Trainer
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.util.Random
import kotlin.math.cos
import kotlin.math.sin

/**
 * Entrena con senas sinteticas (formas y movimientos distintos por sena, con
 * variaciones por persona) y revisa que el modelo aprenda y que el archivo que
 * exporta lo entienda la app de traduccion.
 */
class TrainerTest {
    private val signIds = listOf("hola", "gracias", "letra_a", "num_5", "nada")
    private val names = mapOf("hola" to "Hola", "gracias" to "Gracias", "letra_a" to "A", "num_5" to "5", "nada" to "Nada")
    private val catalog = SignCatalog(signIds.map { id ->
        SignSpec(
            id, names[id]!!, when {
                id.startsWith("letra") -> "abecedario"
                id.startsWith("num") -> "numeros"
                else -> "palabras"
            }, "", "mira",
        )
    })

    /** Una repeticion sintetica: mano derecha con una forma y un movimiento propios de la sena. */
    private fun clip(signIndex: Int, signer: Int, rng: Random): Clip {
        val n = 28
        val times = DoubleArray(n) { it * 2.0 / (n - 1) }
        val size = 0.09 + 0.02 * signer
        val image = ArrayList<FloatArray>(n)
        val world = ArrayList<FloatArray>(n)
        for (f in 0 until n) {
            val img = FloatArray(126) { Float.NaN }
            val wld = FloatArray(126) { Float.NaN }
            val phase = f.toDouble() / (n - 1)
            val nothing = signIndex == 4
            // Movimiento: cada sena recorre una direccion distinta; "nada" se queda quieta y a veces no hay mano
            val wx = 0.5 + 0.08 * signer + (if (nothing) 0.0 else 0.25 * phase * cos(signIndex * 1.3))
            val wy = 0.55 + (if (nothing) 0.0 else 0.2 * phase * sin(signIndex * 1.3))
            if (nothing && rng.nextDouble() < 0.4) {
                image += img; world += wld; continue
            }
            for (p in 0 until 21) {
                val finger = (p - 1) / 4
                val joint = if (p == 0) 0 else (p - 1) % 4 + 1
                // Dedos extendidos o doblados segun bits de la sena
                val extended = p == 0 || (signIndex shr (finger % 4)) and 1 == 1 || finger == 0
                val reach = joint * size * (if (extended) 0.55 else 0.22)
                val angle = -1.1 + 0.55 * finger + 0.15 * sin(signIndex + phase * 3)
                val x = wx + reach * cos(angle) + rng.nextGaussian() * 0.002
                val y = wy - reach * sin(angle) * 1.2 + rng.nextGaussian() * 0.002
                img[63 + p * 3] = x.toFloat(); img[63 + p * 3 + 1] = y.toFloat(); img[63 + p * 3 + 2] = (-0.02 * joint).toFloat()
                wld[63 + p * 3] = ((x - wx) * 0.9).toFloat(); wld[63 + p * 3 + 1] = ((y - wy) * 0.9).toFloat()
                wld[63 + p * 3 + 2] = (if (extended) 0.0 else -0.02 * joint).toFloat()
            }
            image += img; world += wld
        }
        return Clip(signIds[signIndex], "persona-$signer", "c${rng.nextInt(1 shl 20)}", 4.0 / 3, times, image, world)
    }

    @Test
    fun learnsSyntheticSignsAndExportsForTheTranslator() {
        val rng = Random(7)
        val clips = ArrayList<Clip>()
        for (signer in 0 until 3) for (sign in signIds.indices) repeat(6) { clips += clip(sign, signer, rng) }
        val messages = ArrayList<String>()
        val cfg = TrainConfig(augCopies = 2, evalAugCopies = 1, maxEpochs = 25, evalMaxEpochs = 12, hidden = intArrayOf(48, 24),
            maxSignerFolds = 2)
        val model = Trainer.train(clips, catalog, cfg, progress = { _, m -> if (messages.lastOrNull() != m) messages += m })
        val report = model.report!!
        assertEquals("personas", report.evalMode)
        assertEquals(signIds.sorted(), report.classes)
        assertTrue("aciertos ${report.accuracy}", report.accuracy >= 0.8)
        assertEquals(2, report.perSigner.size)
        assertTrue(report.perCategory.containsKey("palabras"))
        assertTrue(messages.any { it.contains("Examen con personas nuevas") })
        assertTrue(messages.last().contains("Listo"))

        // El archivo para el celular lo lee SignModel y predice lo mismo
        val json = model.toAndroidJson(catalog, "prueba")
        val android = SignModel.fromJson(json)
        assertEquals(model.classes, android.classes)
        assertEquals(5, android.signs.first { it.id == "num_5" }.number)
        assertEquals("abecedario", android.signs.first { it.id == "letra_a" }.category)
        val sample = clips[3]
        val feats = Features.windowFeatures(sample.times, sample.image, sample.world, sample.aspect, 2.0)
        val mine = model.predictProba(feats)
        val theirs = android.predictProba(feats)
        for (i in mine.indices) assertEquals(mine[i], theirs[i], 1e-4)
        assertEquals(report.accuracy, android.report!!.accuracy, 1e-9)

        // Y el .npz para la PC trae las mismas piezas que TrainedModel.save
        val npz = Npz.read(model.toNpz("prueba"))
        assertEquals(setOf("mean", "std", "meta", "w0", "b0", "w1", "b1", "w2", "b2"), npz.keys)
        val w0 = npz["w0"] as Npy.Floats
        assertEquals(Features.FEATURE_SIZE, w0.shape[0])
        assertEquals(48, w0.shape[1])
        val meta = JSONObject((npz["meta"] as Npy.Text).value)
        assertEquals(1, meta.getInt("feature_version"))
        assertEquals(5, meta.getJSONArray("classes").length())
        assertEquals("personas", meta.getJSONObject("report").getString("eval_mode"))

        // Lo dejamos en build/ para revisarlo con NumPy desde la PC
        val out = File("build/npz-out").apply { mkdirs() }
        File(out, "modelo_kotlin.npz").writeBytes(model.toNpz("prueba"))
        File(out, "modelo_kotlin.json").writeText(json)
        Npz.write(File(out, "clip_kotlin.npz").outputStream(), linkedMapOf(
            "image" to Npy.Floats(intArrayOf(sample.frames, 2, 21, 3), FloatArray(sample.frames * 126) { sample.image[it / 126][it % 126] }),
            "world" to Npy.Floats(intArrayOf(sample.frames, 2, 21, 3), FloatArray(sample.frames * 126) { sample.world[it / 126][it % 126] }),
            "t" to Npy.Floats(intArrayOf(sample.frames), FloatArray(sample.frames) { sample.times[it].toFloat() }),
            "meta" to Npy.Text("{\"format\": 1, \"aspect\": 1.3333, \"sign_id\": \"${sample.signId}\"}"),
        ))
    }

    @Test
    fun needsAtLeastTwoSigns() {
        val rng = Random(1)
        val clips = List(5) { clip(0, 0, rng) }
        try {
            Trainer.train(clips, catalog, TrainConfig(maxEpochs = 1))
            throw AssertionError("debio fallar")
        } catch (e: Trainer.TrainingException) {
            assertTrue(e.message!!.contains("suficientes"))
        }
    }
}
