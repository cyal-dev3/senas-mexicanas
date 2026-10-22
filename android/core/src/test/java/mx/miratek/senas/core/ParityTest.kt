package mx.miratek.senas.core

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

/**
 * Pruebas de PARIDAD: Android debe calcular lo mismo que Python.
 * Los datos esperados los genera tools/make_parity_vectors.py.
 */
class ParityTest {
    private fun resource(name: String): String =
        javaClass.classLoader!!.getResource("parity/$name")!!.readText()

    private fun rows(array: JSONArray): List<FloatArray> = (0 until array.length()).map { i ->
        val row = array.getJSONArray(i)
        FloatArray(row.length()) { j -> if (row.isNull(j)) Float.NaN else row.getDouble(j).toFloat() }
    }

    @Test
    fun featuresMatchPython() {
        val cases = JSONObject(resource("features.json")).getJSONArray("cases")
        assertTrue(cases.length() >= 10)
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val timesJson = c.getJSONArray("times")
            val times = DoubleArray(timesJson.length()) { timesJson.getDouble(it) }
            val got = Features.windowFeatures(
                times, rows(c.getJSONArray("image")), rows(c.getJSONArray("world")),
                c.getDouble("aspect"), c.getDouble("window_s"), c.getDouble("t_end"),
                if (c.isNull("mirror")) null else c.getBoolean("mirror"),
            )
            val expected = c.getJSONArray("expected")
            assertEquals(Features.FEATURE_SIZE, got.size)
            var worst = 0.0
            var worstIndex = -1
            for (k in got.indices) {
                val d = abs(got[k] - expected.getDouble(k))
                if (d > worst) { worst = d; worstIndex = k }
            }
            assertTrue("caso ${c.getString("name")}: diferencia $worst en el indice $worstIndex", worst < 1e-4)
        }
    }

    @Test
    fun modelMatchesPython() {
        val model = SignModel.fromJson(resource("model.json"))
        val data = JSONObject(resource("predictions.json"))
        val feats = rows(data.getJSONArray("features"))
        val expected = rows(data.getJSONArray("expected"))
        for ((f, e) in feats.zip(expected)) {
            val p = model.predictProba(f)
            assertEquals(e.size, p.size)
            for (k in p.indices) assertEquals(e[k].toDouble(), p[k], 1e-4)
        }
    }

    @Test
    fun phraseRulesMatchPython() {
        val data = JSONObject(resource("phrase.json"))
        val signsJson = data.getJSONArray("signs")
        val signs = (0 until signsJson.length()).associate { i ->
            val s = signsJson.getJSONObject(i)
            s.getString("id") to SignInfo(
                s.getString("id"), s.getString("name"), s.getString("category"),
                if (s.isNull("number")) null else s.getInt("number"),
            )
        }
        val cases = data.getJSONArray("cases")
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val p = PhraseBuilder()
            val tokens = c.getJSONArray("tokens")
            for (k in 0 until tokens.length()) {
                val t = tokens.getString(k)
                if (t == "|") p.close() else p.add(signs.getValue(t))
            }
            val expected = c.getJSONArray("expected").let { a -> (0 until a.length()).map { a.getString(it) } }
            assertEquals(expected, p.texts)
        }
    }
}
