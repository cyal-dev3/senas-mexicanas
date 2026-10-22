package mx.miratek.senas.data

import android.content.Context
import android.net.Uri
import mx.miratek.senas.core.ModelFormatException
import mx.miratek.senas.core.SignModel
import java.io.BufferedInputStream
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.InputStream
import java.util.zip.ZipInputStream

/**
 * Donde vive el modelo:
 *  1. El que la persona cargo desde un archivo (se guarda dentro de la app).
 *  2. Si no hay, el que viene incluido en la APK (assets/modelo_android.json).
 */
class ModelRepository(private val context: Context) {
    private val userFile = File(context.filesDir, "modelo.json")

    val hasUserModel get() = userFile.exists()

    val hasBundledModel: Boolean
        get() = runCatching { context.assets.open(BUNDLED).close(); true }.getOrDefault(false)

    /** true si el ultimo modelo cargado es el de la persona (si su archivo falla, se usa el incluido). */
    @Volatile var usingUserModel = false
        private set

    fun load(): SignModel? {
        if (userFile.exists()) {
            runCatching { SignModel.fromJson(userFile.readText()) }.getOrNull()?.let {
                usingUserModel = true
                return it
            }
        }
        usingUserModel = false
        return runCatching {
            context.assets.open(BUNDLED).bufferedReader().use { SignModel.fromJson(it.readText()) }
        }.getOrNull()
    }

    /** Carga un modelo desde un archivo .json (o un .zip de la app de PC). */
    fun import(uri: Uri): SignModel {
        val text = context.contentResolver.openInputStream(uri)?.use { raw ->
            val input = BufferedInputStream(raw)
            input.mark(4)
            val isZip = input.read() == 'P'.code && input.read() == 'K'.code
            input.reset()
            if (isZip) fromZip(input) else readLimited(input)
        } ?: throw ModelFormatException("No pude abrir el archivo.")
        val model = SignModel.fromJson(text)  // valida antes de guardar
        val tmp = File(context.filesDir, "modelo.json.tmp")
        tmp.writeText(text)
        if (!tmp.renameTo(userFile)) {
            userFile.delete()
            tmp.renameTo(userFile)
        }
        usingUserModel = true
        return model
    }

    fun useBundled() {
        userFile.delete()
    }

    /** Lee texto sin pasar de MAX_MODEL_BYTES (un modelo pesa 1-2 MB). */
    private fun readLimited(input: InputStream): String {
        val out = ByteArrayOutputStream()
        val buffer = ByteArray(64 * 1024)
        var total = 0L
        while (true) {
            val n = input.read(buffer)
            if (n < 0) break
            total += n
            if (total > MAX_MODEL_BYTES) throw ModelFormatException("Este archivo no parece un modelo de Mira&Tek.")
            out.write(buffer, 0, n)
        }
        return out.toString(Charsets.UTF_8.name())
    }

    private fun fromZip(input: InputStream): String {
        ZipInputStream(input).use { zip ->
            while (true) {
                val entry = zip.nextEntry ?: break
                if (entry.name == ZIP_MEMBER || entry.name.endsWith("modelo_android.json")) {
                    return readLimited(zip)
                }
            }
        }
        throw ModelFormatException("Este archivo no trae un modelo para el celular. En la PC usa «Crear archivo para el celular».")
    }

    companion object {
        const val BUNDLED = "modelo_android.json"
        const val ZIP_MEMBER = "modelo/modelo_android.json"
        const val MAX_MODEL_BYTES = 50L * 1024 * 1024
    }
}
