package mx.miratek.senas.trainer

import mx.miratek.senas.trainer.data.ClipStore
import mx.miratek.senas.trainer.data.Packages
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class StoreAndPackagesTest {
    @get:Rule
    val tmp = TemporaryFolder()

    private fun frames(n: Int, left: Boolean = false): Pair<List<FloatArray>, List<FloatArray>> {
        val image = List(n) { f ->
            FloatArray(126) { k ->
                val hand = k / 63
                if ((hand == 1) || (left && hand == 0)) 0.3f + 0.001f * f + 0.0001f * k else Float.NaN
            }
        }
        val world = List(n) { f -> FloatArray(126) { k -> if (image[f][k].isNaN()) Float.NaN else 0.01f * (k % 63) } }
        return image to world
    }

    private fun fill(store: ClipStore, signer: String, signs: List<String>, clips: Int) {
        for (sign in signs) repeat(clips) { i ->
            val (image, world) = frames(30)
            store.saveClip(sign, signer, DoubleArray(30) { 100.0 + it / 15.0 }, image, world, 4.0 / 3,
                mirror = if (signer.startsWith("luis")) true else null)
        }
        store.setSignerName(signer, signer.uppercase())
    }

    @Test
    fun saveListLoadDelete() {
        val store = ClipStore(tmp.newFolder("datos"))
        fill(store, "ana-1234", listOf("hola", "nada"), 3)
        assertEquals(mapOf("hola" to 3, "nada" to 3), store.counts("ana-1234"))
        val refs = store.listClips("ana-1234")
        assertEquals(6, refs.size)
        val clip = store.load(refs.first { it.signId == "hola" })
        assertEquals(30, clip.frames)
        assertEquals(0.0, clip.times[0], 0.0)              // los tiempos empiezan en 0
        assertEquals(29.0 / 15.0, clip.times[29], 1e-5)
        assertTrue(clip.image[0][0].isNaN())               // mano izquierda ausente
        assertEquals(0.3f + 0.0001f * 63, clip.image[0][63], 1e-6f)
        assertEquals(4.0 / 3, clip.aspect, 1e-9)
        assertEquals(null, clip.mirror)
        assertTrue(clip.clipId.contains('-'))
        store.delete(refs[0])
        assertEquals(5, store.listClips().size)
        assertEquals("ANA-1234", store.signerNames()["ana-1234"])
        store.deleteSigner("ana-1234")
        assertTrue(store.listClips().isEmpty())
        assertTrue(store.signerNames().isEmpty())
    }

    @Test
    fun exportImportRoundTrip() {
        val a = ClipStore(tmp.newFolder("a"))
        fill(a, "ana-1234", listOf("hola", "gracias"), 2)
        fill(a, "luis-9999", listOf("hola"), 2)
        val model = tmp.newFile("modelo_actual.json").apply { writeText("{\"fake\": true}") }
        val zip = Packages.export(a, tmp.newFolder("out"), "María Peña", modelJson = model)
        assertTrue(zip.name.startsWith("MiraTek_maria-pena_grabaciones_"))

        val b = ClipStore(tmp.newFolder("b"))
        val models = File(tmp.root, "modelos")
        val result = Packages.import(b, zip, models)
        assertEquals(6, result.added)
        assertEquals(0, result.skipped)
        assertEquals(mapOf("ana-1234" to 4, "luis-9999" to 2), result.signers)
        assertEquals("María Peña", result.author)
        assertNotNull(result.modelJson)
        assertEquals(a.signerNames(), b.signerNames())
        val again = Packages.import(b, zip, models)
        assertEquals(0, again.added)
        assertEquals(6, again.skipped)  // sin duplicados
    }

    @Test
    fun rejectsBadFilesAndIgnoresUnsafeMembers() {
        val store = ClipStore(tmp.newFolder("c"))
        val notZip = tmp.newFile("foto.jpg").apply { writeBytes(ByteArray(300) { 7 }) }
        try {
            Packages.import(store, notZip, tmp.newFolder("m1"))
            fail("debio fallar")
        } catch (e: Packages.PackageException) {
            assertTrue(e.message!!.contains("no es un paquete"))
        }

        val evil = tmp.newFile("evil.zip")
        ZipOutputStream(evil.outputStream()).use { z ->
            z.putNextEntry(ZipEntry("manifest.json")); z.write("{\"format\": 1, \"author\": \"x\"}".toByteArray()); z.closeEntry()
            z.putNextEntry(ZipEntry("clips/../../x.npz")); z.write(ByteArray(10)); z.closeEntry()
            z.putNextEntry(ZipEntry("clips/Ana/hola/a.npz")); z.write(ByteArray(10)); z.closeEntry()   // mayuscula: no es id seguro
            z.putNextEntry(ZipEntry("clips/ana/hola/basura.npz")); z.write("no es npz".toByteArray()); z.closeEntry()
            z.putNextEntry(ZipEntry("otra/cosa.txt")); z.write(ByteArray(3)); z.closeEntry()
        }
        val result = Packages.import(store, evil, tmp.newFolder("m2"))
        assertEquals(0, result.added)
        assertEquals(0, result.skipped)
        assertEquals(1, result.invalid)  // solo el que parecia clip pero no lo era
        assertTrue(store.listClips().isEmpty())
        assertFalse(File(tmp.root, "x.npz").exists())

        val future = tmp.newFile("futuro.zip")
        ZipOutputStream(future.outputStream()).use { z ->
            z.putNextEntry(ZipEntry("manifest.json")); z.write("{\"format\": 99}".toByteArray()); z.closeEntry()
        }
        try {
            Packages.import(store, future, tmp.newFolder("m3"))
            fail("debio fallar")
        } catch (e: Packages.PackageException) {
            assertTrue(e.message!!.contains("más nueva"))
        }
    }
}
