package mx.miratek.senas.trainer

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
import mx.miratek.senas.data.LearnRepository
import mx.miratek.senas.data.SignCatalog
import mx.miratek.senas.trainer.ui.HomeActions
import mx.miratek.senas.trainer.ui.HomeContent
import mx.miratek.senas.trainer.ui.RecordActions
import mx.miratek.senas.trainer.ui.RecordContent
import mx.miratek.senas.trainer.ui.SetupScreen
import mx.miratek.senas.trainer.ui.ShareActions
import mx.miratek.senas.trainer.ui.ShareContent
import mx.miratek.senas.trainer.ui.TrainActions
import mx.miratek.senas.trainer.ui.TrainContent
import mx.miratek.senas.trainer.ui.TrainerNav
import mx.miratek.senas.trainer.ui.TrainerTab
import mx.miratek.senas.trainer.ui.TrainerWelcome
import mx.miratek.senas.ui.Mira
import mx.miratek.senas.ui.MiraTekTheme
import org.junit.Rule
import org.junit.Test
import java.io.File

/**
 * Capturas de las pantallas del Entrenador sin celular (./gradlew :trainer:recordPaparazziDebug).
 * Quedan en trainer/src/test/snapshots/images para revisar el diseno.
 */
class TrainerScreenshotTest {
    @get:Rule
    val paparazzi = Paparazzi(
        deviceConfig = DeviceConfig.PIXEL_6,
        theme = "android:Theme.Material.Light.NoActionBar",
        maxPercentDifference = 100.0,
    )

    private val info = File("../../assets/senas_info.json").readText()
    private val catalog = SignCatalog.parse(info)
    private val clips = File("../../assets/learn_clips.json").takeIf { it.exists() }?.readText()
        ?.let { LearnRepository.parse(info, it) }?.associate { it.id to it.clip }
        ?.filterValues { it != null }?.mapValues { it.value!! } ?: emptyMap()

    private fun state(): TrainerState {
        val mine = catalog.signs.take(9).associate { it.id to 15 } + mapOf("ayuda" to 7, "letra_a" to 15, "letra_b" to 3, "num_1" to 15)
        val other = catalog.signs.take(30).associate { it.id to 15 }
        return TrainerState(
            loading = false, signerId = "keysita-1a2b", signerName = "Keysita", signs = catalog.signs, clips = clips,
            myCounts = mine, allCounts = mapOf("keysita-1a2b" to mine, "ana-9f00" to other, "luis-77aa" to other.filterKeys { it.startsWith("letra") }),
            names = mapOf("keysita-1a2b" to "Keysita", "ana-9f00" to "Ana", "luis-77aa" to "Luis"),
        )
    }

    @Composable
    private fun FakeCamera() {
        Box(Modifier.fillMaxSize().background(Brush.verticalGradient(listOf(Color(0xFF3A5A63), Color(0xFF1B3A44), Color(0xFF0E2730))))) {
            Canvas(Modifier.fillMaxSize()) {
                val cx = size.width * 0.55f
                val cy = size.height * 0.5f
                val pts = Array(21) { i -> Offset(cx + (i % 5) * 26f - 50f, cy - (i / 5) * 40f + 60f) }
                for (i in 1 until 21) drawLine(Mira.Warm, pts[i - 1], pts[i], 6f, StrokeCap.Round)
                for (p in pts) drawCircle(Color.White, 7f, p)
            }
        }
    }

    @Composable
    private fun WithNav(tab: TrainerTab, content: @Composable () -> Unit) {
        Column(Modifier.fillMaxSize()) {
            Box(Modifier.weight(1f)) { content() }
            TrainerNav(tab) {}
        }
    }

    @Test
    fun welcome() {
        paparazzi.snapshot { MiraTekTheme { TrainerWelcome(denied = false, onRequest = {}, onOpenSettings = {}) } }
    }

    @Test
    fun setup() {
        paparazzi.snapshot { MiraTekTheme { SetupScreen { _, _ -> } } }
    }

    @Test
    fun home() {
        paparazzi.snapshot { MiraTekTheme { WithNav(TrainerTab.RECORD) { HomeContent(state(), HomeActions()) } } }
    }

    @Test
    fun homeLetters() {
        paparazzi.snapshot { MiraTekTheme { WithNav(TrainerTab.RECORD) { HomeContent(state().copy(category = "abecedario"), HomeActions()) } } }
    }

    @Test
    fun recordCountdown() {
        val session = Session("gracias", Phase.COUNTDOWN, remaining = 2.3, total = 3.0, first = true)
        paparazzi.snapshot { MiraTekTheme { RecordContent(state().copy(handsVisible = true), session, RecordActions()) { FakeCamera() } } }
    }

    @Test
    fun recording() {
        val session = Session("gracias", Phase.RECORDING, progress = 0.6, first = false, saved = 3)
        paparazzi.snapshot { MiraTekTheme { RecordContent(state().copy(handsVisible = true), session, RecordActions()) { FakeCamera() } } }
    }

    @Test
    fun recordDone() {
        val session = Session("gracias", Phase.SIGN_DONE, saved = 15)
        paparazzi.snapshot { MiraTekTheme { RecordContent(state(), session, RecordActions()) { FakeCamera() } } }
    }

    @Test
    fun train() {
        val result = TrainResult(
            0.87, "personas", 1215, 3, 71, mapOf("palabras" to 0.91, "abecedario" to 0.84, "numeros" to 0.86),
            mapOf("ana-9f00" to 0.9, "luis-77aa" to 0.82), listOf(Triple("letra_m", "letra_n", 6), Triple("num_6", "num_9", 4)),
            listOf("Graba la seña «Nada» para que el modelo sepa cuándo no estás haciendo ninguna seña."), 312.0, "2026-10-21T20:10:00",
        )
        paparazzi.snapshot { MiraTekTheme { WithNav(TrainerTab.TRAIN) { TrainContent(state().copy(result = result, hasModel = true), TrainActions()) } } }
    }

    @Test
    fun training() {
        val progress = TrainingProgress(0.42, "Examen con personas nuevas (2 de 3)…")
        paparazzi.snapshot { MiraTekTheme { WithNav(TrainerTab.TRAIN) { TrainContent(state().copy(training = progress), TrainActions()) } } }
    }

    @Test
    fun share() {
        paparazzi.snapshot { MiraTekTheme { WithNav(TrainerTab.SHARE) { ShareContent(state(), ShareActions()) } } }
    }
}
