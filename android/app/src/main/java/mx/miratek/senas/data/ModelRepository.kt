package mx.miratek.senas.data

import android.content.Context
import android.net.Uri
import mx.miratek.senas.core.ModelFormatException
import mx.miratek.senas.core.SignModel
import java.io.ByteArrayInputStream
import java.io.File
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

    fun load(): SignModel? {
        if (userFile.exists()) {
            runCatching { return SignModel.fromJson(userFile.readText()) }
        }
        return runCatching {
            context.assets.open(BUNDLED).bufferedReader().use { SignModel.fromJson(it.readText()) }
        }.getOrNull()
    }

    /** Carga un modelo desde un archivo .json (o un .zip de la app de PC). */
    fun import(uri: Uri): SignModel {
        val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
            ?: throw ModelFormatException("No pude abrir el archivo.")
        if (bytes.size > MAX_BYTES) throw ModelFormatException("El archivo es demasiado grande.")
        val text = if (bytes.size > 2 && bytes[0] == 'P'.code.toByte() && bytes[1] == 'K'.code.toByte()) {
            fromZip(bytes)
        } else {
            bytes.toString(Charsets.UTF_8)
        }
        val model = SignModel.fromJson(text)  // valida antes de guardar
        val tmp = File(context.filesDir, "modelo.json.tmp")
        tmp.writeText(text)
        if (!tmp.renameTo(userFile)) {
            userFile.delete()
            tmp.renameTo(userFile)
        }
        return model
    }

    fun useBundled() {
        userFile.delete()
    }

    private fun fromZip(bytes: ByteArray): String {
        ZipInputStream(ByteArrayInputStream(bytes)).use { zip ->
            while (true) {
                val entry = zip.nextEntry ?: break
                if (entry.name == ZIP_MEMBER || entry.name.endsWith("modelo_android.json")) {
                    return zip.readBytes().toString(Charsets.UTF_8)
                }
            }
        }
        throw ModelFormatException("Este archivo no trae un modelo para el celular. En la PC usa «Crear archivo para el celular».")
    }

    companion object {
        const val BUNDLED = "modelo_android.json"
        const val ZIP_MEMBER = "modelo/modelo_android.json"
        const val MAX_BYTES = 200L * 1024 * 1024
    }
}
