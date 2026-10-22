package mx.miratek.senas.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/** Animacion de una sena: posiciones de las manos cuadro por cuadro (vista de espejo). */
class LearnClip(
    val fps: Int,
    val aspect: Float,
    val cover: Int,
    val signer: String,
    val frames: List<Array<FloatArray?>>,   // [cuadro][mano 0/1] -> 42 numeros (x, y) o null
)

/** Una sena en la seccion "Aprender". */
data class LearnSign(
    val id: String,
    val name: String,
    val category: String,
    val text: String,
    val alt: String?,
    val source: String,        // keysita, sep, mira o pendiente
    val sourceLabel: String,
    val clip: LearnClip?,
) {
    val pending get() = source == "pendiente"
}

/**
 * Lee assets/senas_info.json (como se hace cada sena) y assets/learn_clips.json
 * (animaciones grabadas). Todo viene dentro de la APK: funciona sin internet.
 */
class LearnRepository(private val context: Context) {

    fun load(): List<LearnSign> {
        val info = readAsset(INFO) ?: return emptyList()
        return parse(info, readAsset(CLIPS))
    }

    private fun readAsset(name: String): String? =
        runCatching { context.assets.open(name).bufferedReader().use { it.readText() } }.getOrNull()

    companion object {
        const val INFO = "senas_info.json"
        const val CLIPS = "learn_clips.json"

        /** Une las instrucciones con sus animaciones (tambien lo usan las pruebas). */
        fun parse(info: String, clipsJson: String?): List<LearnSign> {
            val clips = clipsJson?.let { parseClips(it) } ?: emptyMap()
            val root = JSONObject(info)
            val sources = root.optJSONObject("sources")
            val signs = root.getJSONObject("signs")
            return signs.keys().asSequence().map { id ->
                val s = signs.getJSONObject(id)
                val source = s.optString("source", "pendiente")
                LearnSign(
                    id = id,
                    name = s.getString("name"),
                    category = s.getString("category"),
                    text = s.optString("text"),
                    alt = s.optString("alt").takeIf { it.isNotBlank() },
                    source = source,
                    sourceLabel = sources?.optString(source).orEmpty(),
                    clip = clips[id],
                )
            }.toList()
        }

        private fun parseClips(text: String): Map<String, LearnClip> {
            val root = JSONObject(text)
            val fps = root.optInt("fps", 15)
            val signs = root.getJSONObject("signs")
            val out = HashMap<String, LearnClip>()
            for (id in signs.keys()) {
                val s = signs.getJSONObject(id)
                val framesJson = s.getJSONArray("frames")
                val frames = (0 until framesJson.length()).map { i ->
                    val frame = framesJson.getJSONArray(i)
                    Array(2) { slot -> if (frame.isNull(slot)) null else points(frame.getJSONArray(slot)) }
                }
                out[id] = LearnClip(fps, s.optDouble("aspect", 4.0 / 3).toFloat(), s.optInt("cover"),
                    s.optString("signer"), frames)
            }
            return out
        }

        private fun points(array: JSONArray): FloatArray {
            val out = FloatArray(42)
            for (p in 0 until minOf(21, array.length())) {
                val xy = array.getJSONArray(p)
                out[p * 2] = xy.getDouble(0).toFloat()
                out[p * 2 + 1] = xy.getDouble(1).toFloat()
            }
            return out
        }
    }
}
