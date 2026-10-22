package mx.miratek.senas.trainer.data

import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID

/** Referencia a un clip en disco (sin cargarlo). */
class ClipRef(val file: File, val signerId: String, val signId: String, val clipId: String)

/**
 * Una repeticion de una sena: solo posiciones de las manos, nunca video.
 * Cada frame trae 126 numeros (2 manos x 21 puntos x 3), NaN si la mano no aparece.
 */
class Clip(
    val signId: String,
    val signerId: String,
    val clipId: String,
    val aspect: Double,
    val times: DoubleArray,
    val image: List<FloatArray>,
    val world: List<FloatArray>,
    val mirror: Boolean? = null,   // true: persona zurda (se refleja), null: no se sabe
) {
    val frames get() = times.size
}

/**
 * Almacen de grabaciones, copia de miratek/dataset.py:
 *
 *     clips/<persona>/<sena>/<id_del_clip>.npz
 *
 * Un archivo por clip: borrar uno malo es borrar un archivo, y juntar las
 * grabaciones de varias personas es copiar archivos sin choques.
 */
class ClipStore(val root: File) {
    val clipsDir = File(root, "clips").apply { mkdirs() }
    private val namesFile = File(root, "personas.json")

    fun saveClip(
        signId: String, signerId: String, times: DoubleArray,
        image: List<FloatArray>, world: List<FloatArray>, aspect: Double, mirror: Boolean? = null,
    ): ClipRef {
        require(isSafeId(signId) && isSafeId(signerId)) { "id inválido: $signId / $signerId" }
        require(times.size == image.size && times.size == world.size && times.isNotEmpty()) { "frames incompletos" }
        val clipId = newClipId()
        val folder = File(clipsDir, "$signerId/$signId").apply { mkdirs() }
        val n = times.size
        val meta = JSONObject()
            .put("format", CLIP_FORMAT)
            .put("app_version", APP_VERSION)
            .put("sign_id", signId)
            .put("signer_id", signerId)
            .put("clip_id", clipId)
            .put("aspect", aspect)
            .put("created", isoNow())
        if (mirror != null) meta.put("zurdo", mirror)  // con que mano hace las senas (ver Features.mirror)
        val t0 = times[0]
        val arrays = linkedMapOf<String, Npy>(
            "image" to Npy.Floats(intArrayOf(n, 2, 21, 3), flatten(image)),
            "world" to Npy.Floats(intArrayOf(n, 2, 21, 3), flatten(world)),
            "t" to Npy.Floats(intArrayOf(n), FloatArray(n) { (times[it] - t0).toFloat() }),
            "meta" to Npy.Text(meta.toString()),
        )
        val tmp = File(folder, "$clipId.tmp.npz")
        tmp.outputStream().use { Npz.write(it, arrays) }
        val target = File(folder, "$clipId.npz")
        if (!tmp.renameTo(target)) {
            tmp.delete()
            throw IOException("No pude guardar la grabación")
        }
        return ClipRef(target, signerId, signId, clipId)
    }

    fun load(ref: ClipRef): Clip = parse(ref.file.readBytes(), ref.signerId, ref.signId, ref.clipId)

    fun listClips(signerId: String? = null): List<ClipRef> {
        val signerDirs = if (signerId != null) listOf(File(clipsDir, signerId)) else clipsDir.listFiles().orEmpty().toList()
        val out = ArrayList<ClipRef>()
        for (sdir in signerDirs.sortedBy { it.name }) {
            if (!sdir.isDirectory) continue
            for (gdir in sdir.listFiles().orEmpty().sortedBy { it.name }) {
                if (!gdir.isDirectory) continue
                for (f in gdir.listFiles().orEmpty().sortedBy { it.name }) {
                    if (f.name.endsWith(".npz") && !f.name.endsWith(".tmp.npz")) {
                        out += ClipRef(f, sdir.name, gdir.name, f.name.removeSuffix(".npz"))
                    }
                }
            }
        }
        return out
    }

    /** {sena: numero de clips} de una persona o de todas. */
    fun counts(signerId: String? = null): Map<String, Int> {
        val out = HashMap<String, Int>()
        for (ref in listClips(signerId)) out[ref.signId] = (out[ref.signId] ?: 0) + 1
        return out
    }

    fun countsBySigner(): Map<String, Map<String, Int>> {
        val out = HashMap<String, HashMap<String, Int>>()
        for (ref in listClips()) {
            val per = out.getOrPut(ref.signerId) { HashMap() }
            per[ref.signId] = (per[ref.signId] ?: 0) + 1
        }
        return out
    }

    fun delete(ref: ClipRef) {
        ref.file.delete()
    }

    fun deleteSigner(signerId: String) {
        if (isSafeId(signerId)) File(clipsDir, signerId).deleteRecursively()
        val names = signerNames().toMutableMap()
        if (names.remove(signerId) != null) writeNames(names)
    }

    /** Ultimo clip de una sena y persona (para "deshacer"). */
    fun lastClip(signerId: String, signId: String): ClipRef? =
        listClips(signerId).filter { it.signId == signId }.maxByOrNull { it.clipId }

    // ---------------- Nombres de las personas ----------------

    fun signerNames(): Map<String, String> {
        if (!namesFile.exists()) return emptyMap()
        return runCatching {
            val json = JSONObject(namesFile.readText())
            json.keys().asSequence().filter { isSafeId(it) }.associateWith { json.optString(it) }
        }.getOrDefault(emptyMap())
    }

    fun setSignerName(signerId: String, name: String) {
        val names = signerNames().toMutableMap()
        if (names[signerId] != name) {
            names[signerId] = name
            writeNames(names)
        }
    }

    private fun writeNames(names: Map<String, String>) {
        val tmp = File(root, "personas.tmp")
        tmp.writeText(JSONObject(names).toString(2))
        if (!tmp.renameTo(namesFile)) {
            namesFile.delete()
            tmp.renameTo(namesFile)
        }
    }

    companion object {
        const val CLIP_FORMAT = 1
        const val MIN_FRAMES = 8          // igual que al grabar en la PC
        const val FRAME_SIZE = 126
        var APP_VERSION = "android"
        private val SAFE = Regex("^[a-z0-9_-]{1,64}$")

        fun isSafeId(text: String) = SAFE.matches(text)

        /** Empieza con la hora en milisegundos: ordenar por nombre = ordenar por fecha. */
        fun newClipId(): String =
            "%013x-%s".format(System.currentTimeMillis(), UUID.randomUUID().toString().replace("-", "").take(6))

        fun isoNow(): String = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).format(Date())

        private fun flatten(frames: List<FloatArray>): FloatArray {
            val out = FloatArray(frames.size * FRAME_SIZE)
            for ((i, f) in frames.withIndex()) System.arraycopy(f, 0, out, i * FRAME_SIZE, FRAME_SIZE)
            return out
        }

        /** Lee un clip y revisa que tenga la forma correcta (como _valid_clip en la PC). */
        fun parse(bytes: ByteArray, signerId: String, signId: String, clipId: String): Clip {
            val arrays = Npz.read(bytes)
            val image = arrays["image"] as? Npy.Floats ?: throw NpzFormatException("Falta 'image'")
            val world = arrays["world"] as? Npy.Floats ?: throw NpzFormatException("Falta 'world'")
            val t = arrays["t"] as? Npy.Floats ?: throw NpzFormatException("Falta 't'")
            val metaText = (arrays["meta"] as? Npy.Text)?.value ?: throw NpzFormatException("Falta 'meta'")
            val meta = try { JSONObject(metaText) } catch (e: Exception) { throw NpzFormatException("meta dañado") }
            val n = image.shape.getOrNull(0) ?: 0
            if (image.shape.size != 4 || image.shape[1] != 2 || image.shape[2] != 21 || image.shape[3] != 3 ||
                n < MIN_FRAMES || !world.shape.contentEquals(image.shape) || t.shape.size != 1 || t.shape[0] != n
            ) throw NpzFormatException("Forma del clip incorrecta")
            val times = DoubleArray(n) { t.data[it].toDouble() }
            for (i in 0 until n) {
                if (!times[i].isFinite() || (i > 0 && times[i] < times[i - 1])) throw NpzFormatException("Tiempos dañados")
            }
            return Clip(
                signId, signerId, clipId, meta.optDouble("aspect", 4.0 / 3), times,
                List(n) { image.data.copyOfRange(it * FRAME_SIZE, (it + 1) * FRAME_SIZE) },
                List(n) { world.data.copyOfRange(it * FRAME_SIZE, (it + 1) * FRAME_SIZE) },
                mirror = if (meta.opt("zurdo") is Boolean) meta.getBoolean("zurdo") else null,
            )
        }

        fun isValid(bytes: ByteArray): Boolean = runCatching { parse(bytes, "x", "x", "x"); true }.getOrDefault(false)
    }
}
