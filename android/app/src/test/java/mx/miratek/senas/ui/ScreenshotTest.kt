package mx.miratek.senas.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import app.cash.paparazzi.DeviceConfig
import app.cash.paparazzi.Paparazzi
import mx.miratek.senas.UiState
import mx.miratek.senas.core.Prediction
import mx.miratek.senas.core.SignModel
import mx.miratek.senas.data.LearnRepository
import org.json.JSONObject
import org.junit.Rule
import org.junit.Test
import java.io.File

/**
 * Capturas de las pantallas sin celular (./gradlew recordPaparazziDebug).
 * Quedan en app/src/test/snapshots/images para revisar el diseno.
 */
class ScreenshotTest {
    @get:Rule
    val paparazzi = Paparazzi(
        deviceConfig = DeviceConfig.PIXEL_6,
        theme = "android:Theme.Material.Light.NoActionBar",
        maxPercentDifference = 100.0,
    )

    private val model by lazy {
        SignModel.fromJson(javaClass.classLoader!!.getResource("parity/model.json")!!.readText())
    }

    /** Las senas de "Aprender" tal como van en la APK (las animaciones solo si ya se generaron). */
    private val learn by lazy {
        val info = File("../../assets/senas_info.json").readText()
        val clips = File("src/main/assets/learn_clips.json").takeIf { it.exists() }?.readText()
        LearnRepository.parse(info, clips)
    }

    private val handPoints: List<Offset> by lazy {
        val case = JSONObject(javaClass.classLoader!!.getResource("parity/features.json")!!.readText())
            .getJSONArray("cases").getJSONObject(0)
        val frame = case.getJSONArray("image").getJSONArray(32)
        val slot = if (frame.isNull(63)) 0 else 1
        (0 until 21).map { p ->
            Offset(frame.getDouble(slot * 63 + p * 3).toFloat(), frame.getDouble(slot * 63 + p * 3 + 1).toFloat())
        }
    }

    @Composable
    private fun FakeCamera() {
        Box(
            Modifier.fillMaxSize().background(
                Brush.verticalGradient(listOf(Color(0xFF3A5A63), Color(0xFF1B3A44), Color(0xFF0E2730)))
            )
        ) {
            Canvas(Modifier.fillMaxSize()) {
                val pts = handPoints.map { Offset((it.x - 0.2f) * size.width * 1.3f, (it.y + 0.05f) * size.height * 0.8f) }
                val links = listOf(0 to 1, 1 to 2, 2 to 3, 3 to 4, 0 to 5, 5 to 6, 6 to 7, 7 to 8, 5 to 9, 9 to 10,
                    10 to 11, 11 to 12, 9 to 13, 13 to 14, 14 to 15, 15 to 16, 13 to 17, 17 to 18, 18 to 19, 19 to 20, 0 to 17)
                for ((a, b) in links) drawLine(Mira.Warm.copy(alpha = 0.3f), pts[a], pts[b], 16f, StrokeCap.Round)
                for ((a, b) in links) drawLine(Mira.Warm, pts[a], pts[b], 6f, StrokeCap.Round)
                pts.forEachIndexed { i, p ->
                    val r = if (i in setOf(4, 8, 12, 16, 20)) 10f else 6.5f
                    drawCircle(Mira.Warm, r + 3f, p)
                    drawCircle(Color.White, r, p)
                }
            }
        }
    }

    @Composable
    private fun WithNav(tab: Tab, content: @Composable () -> Unit) {
        Column(Modifier.fillMaxSize()) {
            Box(Modifier.weight(1f)) { content() }
            BottomNav(tab) {}
        }
    }

    private fun baseState() = UiState(loading = false, model = model, learn = learn, practiced = setOf("gracias", "hola", "letra_a"))

    @Test
    fun translator() {
        val hola = model.signs.first { it.id == "hola" }
        val gracias = model.signs.first { it.id == "gracias" }
        val state = baseState().copy(
            prediction = Prediction(hola, 0.86, listOf(hola to 0.86, gracias to 0.09), true),
            phrase = listOf("Hola", "ANA", "Gracias", "23"),
        )
        paparazzi.snapshot { MiraTekTheme { WithNav(Tab.TRANSLATE) { TranslatorContent(state, TranslatorActions()) { FakeCamera() } } } }
    }

    @Test
    fun translatorWithoutModel() {
        paparazzi.snapshot {
            MiraTekTheme { WithNav(Tab.TRANSLATE) { TranslatorContent(UiState(loading = false), TranslatorActions()) { FakeCamera() } } }
        }
    }

    @Test
    fun translatorCameraError() {
        val state = baseState().copy(cameraError = "No pude abrir la cámara. Cierra otras apps que la usen e intenta de nuevo.")
        paparazzi.snapshot { MiraTekTheme { WithNav(Tab.TRANSLATE) { TranslatorContent(state, TranslatorActions()) { FakeCamera() } } } }
    }

    @Test
    fun learnList() {
        paparazzi.snapshot { MiraTekTheme { WithNav(Tab.LEARN) { LearnScreen(baseState()) {} } } }
    }

    @Test
    fun learnDetail() {
        paparazzi.snapshot { MiraTekTheme { WithNav(Tab.LEARN) { SignDetailScreen(baseState(), "familia", {}, {}, {}) } } }
    }

    @Test
    fun practice() {
        val gracias = model.signs.first { it.id == "gracias" }
        val state = baseState().copy(practiceTarget = "gracias",
            prediction = Prediction(gracias, 0.72, listOf(gracias to 0.72), true))
        paparazzi.snapshot {
            MiraTekTheme { PracticeContent(state, "gracias", {}, {}, {}, {}, {}) { FakeCamera() } }
        }
    }

    @Test
    fun practiceDone() {
        val state = baseState().copy(practiceTarget = "gracias", practiceDone = true)
        paparazzi.snapshot {
            MiraTekTheme { PracticeContent(state, "gracias", {}, {}, {}, {}, {}) { FakeCamera() } }
        }
    }

    @Test
    fun profile() {
        paparazzi.snapshot { MiraTekTheme { WithNav(Tab.PROFILE) { ProfileScreen(baseState().copy(profileName = "Keysita")) {} } } }
    }

    @Test
    fun settings() {
        val state = baseState().copy(hasUserModel = true, hasBundledModel = true)
        paparazzi.snapshot { MiraTekTheme { WithNav(Tab.SETTINGS) { SettingsContent(state, SettingsActions()) } } }
    }

    @Test
    fun welcome() {
        paparazzi.snapshot { MiraTekTheme { PermissionScreen(denied = false, onRequest = {}, onOpenSettings = {}) } }
    }
}
