package mx.miratek.senas.core

import org.json.JSONObject
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Base64
import kotlin.math.exp
import kotlin.math.max

/** Una sena que el modelo conoce (viene dentro del archivo del modelo). */
data class SignInfo(val id: String, val name: String, val category: String, val number: Int?) {
    val isLetter get() = category == CATEGORY_LETTERS
    val isNothing get() = id == NOTHING_ID

    companion object {
        const val NOTHING_ID = "nada"
        const val CATEGORY_WORDS = "palabras"
        const val CATEGORY_LETTERS = "abecedario"
        const val CATEGORY_NUMBERS = "numeros"
    }
}

/** Resumen del examen que se hizo al entrenar en la PC. */
data class ModelReport(
    val accuracy: Double,
    val evalMode: String,
    val signers: Int,
    val clips: Int,
    val trainedAt: String,
    val perCategory: Map<String, Double>,
)

class ModelFormatException(message: String) : Exception(message)

/**
 * El modelo entrenado en la PC (archivo modelo_android.json).
 * Hace lo mismo que TrainedModel.predict_proba en Python.
 */
class SignModel private constructor(
    override val signs: List<SignInfo>,
    override val windowS: Double,
    private val temperature: Double,
    private val mean: FloatArray,
    private val std: FloatArray,
    private val weights: List<FloatArray>,   // [entrada * salida], fila por fila
    private val biases: List<FloatArray>,
    private val sizes: List<Pair<Int, Int>>,
    val report: ModelReport?,
    val exported: String,
) : SignClassifier {
    val classes: List<String> = signs.map { it.id }

    override fun predictProba(features: FloatArray): DoubleArray {
        var x = FloatArray(features.size) { i -> (features[i] - mean[i]) / std[i] }
        for (layer in weights.indices) {
            val (nIn, nOut) = sizes[layer]
            val w = weights[layer]
            val out = biases[layer].copyOf()
            for (i in 0 until nIn) {
                val xi = x[i]
                if (xi == 0f) continue
                val row = i * nOut
                for (j in 0 until nOut) out[j] += xi * w[row + j]
            }
            if (layer < weights.size - 1) for (j in out.indices) out[j] = max(out[j], 0f)
            x = out
        }
        // Softmax con temperatura (probabilidades que suman 1)
        val z = DoubleArray(x.size) { x[it] / temperature }
        val top = z.maxOrNull() ?: 0.0
        val e = DoubleArray(z.size) { exp(z[it] - top) }
        val sum = e.sum()
        return DoubleArray(e.size) { e[it] / sum }
    }

    companion object {
        private fun floats(b64: String): FloatArray {
            val bytes = Base64.getDecoder().decode(b64)
            val buf = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer()
            return FloatArray(buf.remaining()).also { buf.get(it) }
        }

        fun fromJson(text: String): SignModel {
            val root = try {
                JSONObject(text)
            } catch (e: Exception) {
                throw ModelFormatException("El archivo no es un modelo de Mira&Tek.")
            }
            if (!root.has("layers") || !root.has("signs")) {
                throw ModelFormatException("El archivo no es un modelo de Mira&Tek.")
            }
            if (root.optInt("feature_version") != Features.FEATURE_VERSION ||
                root.optInt("feature_size") != Features.FEATURE_SIZE
            ) {
                throw ModelFormatException("Este modelo es de otra versión. Actualiza la app o vuelve a exportarlo.")
            }
            val signsJson = root.getJSONArray("signs")
            val signs = (0 until signsJson.length()).map { i ->
                val s = signsJson.getJSONObject(i)
                SignInfo(
                    id = s.getString("id"),
                    name = s.getString("name"),
                    category = s.optString("category", SignInfo.CATEGORY_WORDS),
                    number = if (s.isNull("number")) null else s.getInt("number"),
                )
            }
            val layersJson = root.getJSONArray("layers")
            val weights = ArrayList<FloatArray>()
            val biases = ArrayList<FloatArray>()
            val sizes = ArrayList<Pair<Int, Int>>()
            for (i in 0 until layersJson.length()) {
                val l = layersJson.getJSONObject(i)
                val nIn = l.getInt("in")
                val nOut = l.getInt("out")
                val w = floats(l.getString("w"))
                val b = floats(l.getString("b"))
                if (w.size != nIn * nOut || b.size != nOut) throw ModelFormatException("El modelo está dañado.")
                weights += w
                biases += b
                sizes += nIn to nOut
            }
            val mean = floats(root.getString("mean"))
            val std = floats(root.getString("std"))
            if (mean.size != Features.FEATURE_SIZE || sizes.first().first != Features.FEATURE_SIZE ||
                sizes.last().second != signs.size
            ) {
                throw ModelFormatException("El modelo está dañado.")
            }
            val report = root.optJSONObject("report")?.let { r ->
                val cats = r.optJSONObject("per_category")
                ModelReport(
                    accuracy = r.optDouble("accuracy", 0.0),
                    evalMode = r.optString("eval_mode"),
                    signers = r.optInt("n_signers"),
                    clips = r.optInt("n_clips"),
                    trainedAt = r.optString("trained_at"),
                    perCategory = cats?.keys()?.asSequence()?.associateWith { cats.getDouble(it) } ?: emptyMap(),
                )
            }
            return SignModel(
                signs, root.optDouble("window_s", 2.0), root.optDouble("temperature", 1.0),
                mean, std, weights, biases, sizes, report, root.optString("exported"),
            )
        }
    }
}
