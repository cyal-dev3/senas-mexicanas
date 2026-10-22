package mx.miratek.senas.trainer.data

import org.json.JSONObject
import java.io.BufferedOutputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.io.InputStream
import java.text.Normalizer
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream

/**
 * Paquetes para compartir: UN archivo .zip con grabaciones y/o modelo.
 * Mismo formato que miratek/package.py, asi la PC y el celular se entienden.
 *
 *   1. Cada persona graba y presiona "Crear archivo para enviar".
 *   2. Lo manda (WhatsApp, correo, Drive) a quien coordina.
 *   3. Quien coordina lo abre con esta app: las grabaciones se juntan con las suyas.
 */
object Packages {
    const val FORMAT = 1
    const val MANIFEST = "manifest.json"
    const val MODEL_MEMBER = "modelo/modelo.npz"
    const val ANDROID_MEMBER = "modelo/modelo_android.json"
    private val CLIP_RE = Regex("^clips/([a-z0-9_-]{1,64})/([a-z0-9_-]{1,64})/([a-z0-9_-]{1,64})\\.npz$")
    const val MAX_UNCOMPRESSED = 2L * 1024 * 1024 * 1024  // proteccion contra archivos maliciosos
    const val MAX_CLIP_BYTES = 32L * 1024 * 1024
    const val MAX_MODEL_BYTES = 50L * 1024 * 1024

    class PackageException(message: String) : Exception(message)

    class ImportResult {
        var added = 0
        var skipped = 0   // ya las teniamos
        var invalid = 0   // no se pudieron leer (danadas o de otro formato)
        val signers = HashMap<String, Int>()
        var author = ""
        var modelNpz: File? = null
        var modelJson: File? = null
        var clips = 0
    }

    fun slugify(text: String, fallback: String = "persona"): String {
        val ascii = Normalizer.normalize(text, Normalizer.Form.NFKD).replace(Regex("[^\\p{ASCII}]"), "")
        val slug = ascii.lowercase().replace(Regex("[^a-z0-9]+"), "-").trim('-')
        return slug.take(24).ifEmpty { fallback }
    }

    fun fileName(authorName: String, kind: String): String =
        "MiraTek_${slugify(authorName)}_${kind}_${SimpleDateFormat("yyyy-MM-dd_HHmm", Locale.US).format(Date())}.zip"

    /** Crea el .zip y regresa su ruta. */
    fun export(
        store: ClipStore, destDir: File, authorName: String,
        modelNpz: File? = null, modelJson: File? = null, includeClips: Boolean = true,
    ): File {
        destDir.mkdirs()
        val refs = if (includeClips) store.listClips() else emptyList()
        val hasNpz = modelNpz?.exists() == true
        val hasJson = modelJson?.exists() == true
        if (refs.isEmpty() && !hasNpz && !hasJson) {
            throw PackageException("Todavía no hay grabaciones ni modelo para enviar.")
        }
        val kind = if (refs.isNotEmpty()) "grabaciones" else "modelo"
        val names = store.signerNames()
        val signers = JSONObject()
        for (id in refs.map { it.signerId }.toSortedSet()) signers.put(id, names[id] ?: id)
        val manifest = JSONObject()
            .put("format", FORMAT)
            .put("app_version", ClipStore.APP_VERSION)
            .put("created", ClipStore.isoNow())
            .put("author", authorName)
            .put("signers", signers)
            .put("clips", refs.size)
            .put("has_model", hasNpz || hasJson)
        val path = File(destDir, fileName(authorName, kind))
        val tmp = File(destDir, path.name + ".tmp")
        ZipOutputStream(BufferedOutputStream(FileOutputStream(tmp))).use { zip ->
            zip.setLevel(1)  // los .npz ya vienen comprimidos
            for (ref in refs) {
                zip.putNextEntry(ZipEntry("clips/${ref.signerId}/${ref.signId}/${ref.clipId}.npz"))
                ref.file.inputStream().use { it.copyTo(zip) }
                zip.closeEntry()
            }
            if (hasNpz) {
                zip.putNextEntry(ZipEntry(MODEL_MEMBER))
                modelNpz!!.inputStream().use { it.copyTo(zip) }
                zip.closeEntry()
            }
            if (hasJson) {
                zip.putNextEntry(ZipEntry(ANDROID_MEMBER))
                modelJson!!.inputStream().use { it.copyTo(zip) }
                zip.closeEntry()
            }
            zip.putNextEntry(ZipEntry(MANIFEST))
            zip.write(manifest.toString(2).toByteArray(Charsets.UTF_8))
            zip.closeEntry()
        }
        if (!tmp.renameTo(path)) {
            path.delete()
            if (!tmp.renameTo(path)) throw PackageException("No pude guardar el archivo.")
        }
        return path
    }

    fun readManifest(zipFile: File): JSONObject {
        try {
            ZipFile(zipFile).use { z ->
                val entry = z.getEntry(MANIFEST) ?: throw PackageException("Este archivo no es un paquete de Mira&Tek.")
                val text = z.getInputStream(entry).use { readLimited(it, 1L shl 20) }.toString(Charsets.UTF_8.name())
                return JSONObject(text)
            }
        } catch (e: PackageException) {
            throw e
        } catch (e: Exception) {
            throw PackageException("Este archivo no es un paquete de Mira&Tek.")
        }
    }

    /** Junta las grabaciones del paquete con las nuestras (sin duplicados). */
    fun import(store: ClipStore, zipFile: File, modelsDir: File): ImportResult {
        val result = ImportResult()
        val manifest = readManifest(zipFile)
        val version = manifest.opt("format")
        val formatNumber = (version as? Number)?.toInt() ?: (version as? String)?.toIntOrNull()
            ?: throw PackageException("Este archivo no es un paquete de Mira&Tek.")
        if (formatNumber > FORMAT) {
            throw PackageException("Este archivo es de una versión más nueva de la app. Actualiza la app.")
        }
        result.author = manifest.optString("author")
        result.clips = manifest.optInt("clips")
        try {
            copyMembers(store, zipFile, modelsDir, result)
        } catch (e: PackageException) {
            throw e
        } catch (e: Exception) {
            throw PackageException(
                "El archivo está dañado (quizá no terminó de descargarse). " +
                    "Se agregaron ${result.added} grabaciones antes del error."
            )
        }
        manifest.optJSONObject("signers")?.let { names ->
            val known = store.signerNames()
            for (id in names.keys()) {
                val name = names.opt(id) as? String ?: continue
                if (ClipStore.isSafeId(id) && id !in known) store.setSignerName(id, name.take(40))
            }
        }
        return result
    }

    private fun copyMembers(store: ClipStore, zipFile: File, modelsDir: File, result: ImportResult) {
        ZipFile(zipFile).use { z ->
            val entries = z.entries().toList()
            if (entries.sumOf { it.size.coerceAtLeast(0) } > MAX_UNCOMPRESSED) {
                throw PackageException("El archivo es demasiado grande.")
            }
            val stamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(Date())
            for (entry in entries) {
                val match = CLIP_RE.find(entry.name)
                if (match != null) {
                    val (signerId, signId, clipId) = match.destructured
                    val target = File(store.clipsDir, "$signerId/$signId/$clipId.npz")
                    if (target.exists()) {
                        result.skipped++
                        continue
                    }
                    if (entry.size > MAX_CLIP_BYTES) {
                        result.invalid++
                        continue
                    }
                    val bytes = z.getInputStream(entry).use { readLimited(it, MAX_CLIP_BYTES) }.toByteArray()
                    if (!ClipStore.isValid(bytes)) {
                        result.invalid++
                        continue
                    }
                    target.parentFile!!.mkdirs()
                    val tmp = File(target.parentFile, "$clipId.tmp.npz")
                    tmp.writeBytes(bytes)
                    if (!tmp.renameTo(target)) {
                        tmp.delete()
                        continue
                    }
                    result.added++
                    result.signers[signerId] = (result.signers[signerId] ?: 0) + 1
                } else if (entry.name == MODEL_MEMBER || entry.name == ANDROID_MEMBER) {
                    modelsDir.mkdirs()
                    val ext = if (entry.name == MODEL_MEMBER) "npz" else "json"
                    val target = File(modelsDir, "recibido_$stamp.$ext")
                    val bytes = z.getInputStream(entry).use { readLimited(it, MAX_MODEL_BYTES) }.toByteArray()
                    target.writeBytes(bytes)
                    if (ext == "npz") result.modelNpz = target else result.modelJson = target
                }
                // Cualquier otro archivo se ignora (no extraemos nada inesperado)
            }
        }
    }

    private fun readLimited(input: InputStream, limit: Long): ByteArrayOutputStream {
        val out = ByteArrayOutputStream()
        val buffer = ByteArray(64 * 1024)
        var total = 0L
        while (true) {
            val n = input.read(buffer)
            if (n < 0) break
            total += n
            if (total > limit) throw PackageException("El archivo es demasiado grande.")
            out.write(buffer, 0, n)
        }
        return out
    }
}
