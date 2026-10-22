package mx.miratek.senas.trainer

import mx.miratek.senas.trainer.data.Npy
import mx.miratek.senas.trainer.data.Npz
import mx.miratek.senas.trainer.data.NpzFormatException
import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class NpzTest {
    @Test
    fun roundTripFloatsAndText() {
        val image = FloatArray(3 * 2 * 21 * 3) { if (it % 7 == 0) Float.NaN else it * 0.001f }
        val arrays = linkedMapOf<String, Npy>(
            "image" to Npy.Floats(intArrayOf(3, 2, 21, 3), image),
            "t" to Npy.Floats(intArrayOf(3), floatArrayOf(0f, 0.033f, 0.066f)),
            "meta" to Npy.Text("{\"nombre\": \"Señas ✓ 🙌\"}"),
        )
        val back = Npz.read(Npz.toBytes(arrays))
        assertEquals(setOf("image", "t", "meta"), back.keys)
        val img = back["image"] as Npy.Floats
        assertArrayEquals(intArrayOf(3, 2, 21, 3), img.shape)
        for (i in image.indices) {
            if (image[i].isNaN()) assertTrue(img.data[i].isNaN()) else assertEquals(image[i], img.data[i], 0f)
        }
        assertEquals("{\"nombre\": \"Señas ✓ 🙌\"}", (back["meta"] as Npy.Text).value)
    }

    @Test
    fun headerIsAlignedLikeNumpy() {
        for (array in listOf(Npy.Floats(intArrayOf(2, 2), FloatArray(4)), Npy.Text("hola"), Npy.Floats(intArrayOf(0), FloatArray(0)))) {
            val bytes = Npz.encode(array)
            val headerLen = (bytes[8].toInt() and 0xFF) or ((bytes[9].toInt() and 0xFF) shl 8)
            assertEquals(0, (10 + headerLen) % 64)
            assertEquals('\n'.code.toByte(), bytes[10 + headerLen - 1])
        }
    }

    @Test
    fun readsFilesWrittenByNumpy() {
        val bytes = javaClass.classLoader!!.getResourceAsStream("npz/python_sample.npz")!!.readBytes()
        val arrays = Npz.read(bytes)
        val a = arrays["a"] as Npy.Floats
        assertArrayEquals(intArrayOf(2, 3), a.shape)
        assertArrayEquals(floatArrayOf(0f, 0.25f, 0.5f, 0.75f, 1f, 1.25f), a.data, 0f)
        val d = arrays["d"] as Npy.Floats  // float64 se convierte a float32
        assertArrayEquals(floatArrayOf(1.5f, -2.25f, 1e6f), d.data, 0f)
        val nan = arrays["nan"] as Npy.Floats
        assertTrue(nan.data[0].isNaN())
        assertEquals(1f, nan.data[1], 0f)
        val meta = JSONObject((arrays["meta"] as Npy.Text).value)
        assertEquals("Señas ✓ 🙌", meta.getString("nombre"))
        assertEquals(3, meta.getInt("n"))
    }

    @Test
    fun rejectsGarbage() {
        for (bad in listOf(ByteArray(0), "hola".toByteArray(), ByteArray(100) { 0x50 })) {
            try {
                Npz.read(bad)
                // Un zip vacio o invalido: o lanza o no devuelve arreglos
            } catch (e: Exception) {
                assertTrue(e is NpzFormatException || e is java.io.IOException || e is java.util.zip.ZipException)
            }
        }
        try {
            Npz.decode("no es npy".toByteArray())
            fail("debio fallar")
        } catch (e: NpzFormatException) {
            // esperado
        }
    }
}
