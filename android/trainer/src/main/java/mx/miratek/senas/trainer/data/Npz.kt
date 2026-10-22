package mx.miratek.senas.trainer.data

import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

/** Un arreglo guardado en formato .npy: numeros float32 con su forma, o un texto. */
sealed class Npy {
    class Floats(val shape: IntArray, val data: FloatArray) : Npy()
    class Text(val value: String) : Npy()
}

class NpzFormatException(message: String) : IOException(message)

/**
 * Lee y escribe archivos .npz de NumPy (un .zip con un .npy por arreglo).
 * Asi las grabaciones y los modelos del celular son EXACTAMENTE los mismos
 * archivos que usa la app de PC: se pueden mezclar sin convertir nada.
 */
object Npz {
    private val MAGIC = byteArrayOf(
        0x93.toByte(), 'N'.code.toByte(), 'U'.code.toByte(), 'M'.code.toByte(), 'P'.code.toByte(), 'Y'.code.toByte(),
    )
    const val DEFAULT_LIMIT = 64L * 1024 * 1024  // un clip pesa ~100 KB; un modelo ~1 MB

    fun read(bytes: ByteArray, limit: Long = DEFAULT_LIMIT): Map<String, Npy> = read(bytes.inputStream(), limit)

    fun read(input: InputStream, limit: Long = DEFAULT_LIMIT): Map<String, Npy> {
        val out = LinkedHashMap<String, Npy>()
        var total = 0L
        ZipInputStream(BufferedInputStream(input)).use { zip ->
            while (true) {
                val entry = zip.nextEntry ?: break
                if (entry.isDirectory || !entry.name.endsWith(".npy")) continue
                val bytes = readLimited(zip, limit - total)
                total += bytes.size
                out[entry.name.removeSuffix(".npy")] = decode(bytes)
            }
        }
        return out
    }

    fun write(output: OutputStream, arrays: Map<String, Npy>) {
        ZipOutputStream(BufferedOutputStream(output)).use { zip ->
            for ((name, array) in arrays) {
                zip.putNextEntry(ZipEntry("$name.npy"))
                zip.write(encode(array))
                zip.closeEntry()
            }
        }
    }

    fun toBytes(arrays: Map<String, Npy>): ByteArray =
        ByteArrayOutputStream().also { write(it, arrays) }.toByteArray()

    /** Formato .npy version 1.0, igual que np.save. */
    fun encode(array: Npy): ByteArray {
        val descr: String
        val shape: IntArray
        val body: ByteArray
        when (array) {
            is Npy.Floats -> {
                require(array.shape.fold(1L) { a, b -> a * b } == array.data.size.toLong()) { "forma y datos no coinciden" }
                descr = "<f4"
                shape = array.shape
                val buf = ByteBuffer.allocate(array.data.size * 4).order(ByteOrder.LITTLE_ENDIAN)
                buf.asFloatBuffer().put(array.data)
                body = buf.array()
            }
            is Npy.Text -> {
                val codePoints = array.value.codePoints().toArray()
                val n = maxOf(1, codePoints.size)
                descr = "<U$n"
                shape = IntArray(0)
                val buf = ByteBuffer.allocate(n * 4).order(ByteOrder.LITTLE_ENDIAN)
                for (c in codePoints) buf.putInt(c)
                body = buf.array()
            }
        }
        val shapeText = when (shape.size) {
            0 -> "()"
            1 -> "(${shape[0]},)"
            else -> shape.joinToString(", ", "(", ")")
        }
        var header = "{'descr': '$descr', 'fortran_order': False, 'shape': $shapeText, }"
        // El encabezado se rellena con espacios para que los datos empiecen en un multiplo de 64
        val base = MAGIC.size + 2 + 2
        var pad = 64 - (base + header.length + 1) % 64
        if (pad == 64) pad = 0
        header = header + " ".repeat(pad) + "\n"
        val headerBytes = header.toByteArray(Charsets.US_ASCII)
        val out = ByteArrayOutputStream(base + headerBytes.size + body.size)
        out.write(MAGIC)
        out.write(1)
        out.write(0)
        out.write(headerBytes.size and 0xFF)
        out.write((headerBytes.size ushr 8) and 0xFF)
        out.write(headerBytes)
        out.write(body)
        return out.toByteArray()
    }

    fun decode(bytes: ByteArray): Npy {
        if (bytes.size < 12 || !bytes.copyOfRange(0, 6).contentEquals(MAGIC)) {
            throw NpzFormatException("No es un archivo .npy")
        }
        val major = bytes[6].toInt()
        val headerLen: Int
        val start: Int
        when (major) {
            1 -> {
                headerLen = (bytes[8].toInt() and 0xFF) or ((bytes[9].toInt() and 0xFF) shl 8)
                start = 10
            }
            2, 3 -> {
                headerLen = ByteBuffer.wrap(bytes, 8, 4).order(ByteOrder.LITTLE_ENDIAN).int
                start = 12
            }
            else -> throw NpzFormatException("Versión .npy desconocida")
        }
        if (headerLen < 0 || start + headerLen > bytes.size) throw NpzFormatException("Encabezado dañado")
        val header = String(bytes, start, headerLen, Charsets.ISO_8859_1)
        val descr = Regex("'descr':\\s*'([^']+)'").find(header)?.groupValues?.get(1)
            ?: throw NpzFormatException("Encabezado dañado")
        if (Regex("'fortran_order':\\s*True").containsMatchIn(header)) {
            throw NpzFormatException("Orden Fortran no soportado")
        }
        val shapeText = Regex("'shape':\\s*\\(([^)]*)\\)").find(header)?.groupValues?.get(1)
            ?: throw NpzFormatException("Encabezado dañado")
        val shape = shapeText.split(',').map { it.trim() }.filter { it.isNotEmpty() }
            .map { it.toIntOrNull() ?: throw NpzFormatException("Forma dañada") }.toIntArray()
        if (shape.any { it < 0 }) throw NpzFormatException("Forma dañada")
        val count = shape.fold(1L) { a, b -> a * b }
        val dataStart = start + headerLen
        val available = (bytes.size - dataStart).toLong()
        val data = ByteBuffer.wrap(bytes, dataStart, bytes.size - dataStart).order(ByteOrder.LITTLE_ENDIAN)
        return when {
            descr == "<f4" || descr == "=f4" -> {
                if (count * 4 > available || count > Int.MAX_VALUE) throw NpzFormatException("Datos incompletos")
                val floats = FloatArray(count.toInt())
                data.asFloatBuffer().get(floats)
                Npy.Floats(shape, floats)
            }
            descr == "<f8" || descr == "=f8" -> {
                if (count * 8 > available || count > Int.MAX_VALUE) throw NpzFormatException("Datos incompletos")
                val doubles = data.asDoubleBuffer()
                Npy.Floats(shape, FloatArray(count.toInt()) { doubles.get(it).toFloat() })
            }
            descr.startsWith("<U") || descr.startsWith("=U") -> {
                val n = descr.substring(2).toIntOrNull() ?: throw NpzFormatException("Texto dañado")
                if (count != 1L || n < 0 || n.toLong() * 4 > available) throw NpzFormatException("Texto dañado")
                val sb = StringBuilder(n)
                for (i in 0 until n) {
                    val cp = data.getInt(dataStart + i * 4)
                    if (cp == 0) break  // NumPy rellena con ceros al final
                    if (!Character.isValidCodePoint(cp)) throw NpzFormatException("Texto dañado")
                    sb.appendCodePoint(cp)
                }
                Npy.Text(sb.toString())
            }
            else -> throw NpzFormatException("Tipo $descr no soportado")
        }
    }

    private fun readLimited(input: InputStream, limit: Long): ByteArray {
        val out = ByteArrayOutputStream()
        val buffer = ByteArray(64 * 1024)
        var total = 0L
        while (true) {
            val n = input.read(buffer)
            if (n < 0) break
            total += n
            if (total > limit) throw NpzFormatException("El archivo es demasiado grande")
            out.write(buffer, 0, n)
        }
        return out.toByteArray()
    }
}
