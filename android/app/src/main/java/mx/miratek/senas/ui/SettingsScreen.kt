package mx.miratek.senas.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import mx.miratek.senas.BuildConfig
import mx.miratek.senas.MainViewModel
import mx.miratek.senas.UiState
import mx.miratek.senas.core.Sensitivity
import mx.miratek.senas.core.SignInfo

private val CATEGORY_NAMES = mapOf(
    SignInfo.CATEGORY_WORDS to "Palabras",
    SignInfo.CATEGORY_LETTERS to "Abecedario",
    SignInfo.CATEGORY_NUMBERS to "Números",
)

class SettingsActions(
    val onBack: () -> Unit = {},
    val onLoadModel: () -> Unit = {},
    val onUseBundled: () -> Unit = {},
    val onSensitivity: (Sensitivity) -> Unit = {},
    val onFrontCamera: (Boolean) -> Unit = {},
    val onAutoSpeak: (Boolean) -> Unit = {},
)

@Composable
fun SettingsScreen(vm: MainViewModel, onBack: () -> Unit, onLoadModel: () -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    StatusBarIcons(light = false)
    SettingsContent(
        state,
        SettingsActions(onBack, onLoadModel, vm::useBundledModel, vm::setSensitivity, vm::setFrontCamera, vm::setAutoSpeak),
    )
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SettingsContent(state: UiState, actions: SettingsActions) {
    Column(
        Modifier.fillMaxSize().background(Mira.Bg).verticalScroll(rememberScrollState())
            .statusBarsPadding().navigationBarsPadding().padding(horizontal = 18.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconCircleButton(MiraIcons.Back, "Regresar", actions.onBack)
            Spacer(Modifier.width(14.dp))
            Text("Ajustes", style = MaterialTheme.typography.headlineLarge, color = Mira.Text)
        }

        // ---- Modelo ----
        GlassCard(Modifier.fillMaxWidth()) {
            Overline("Modelo")
            VSpace(10.dp)
            val model = state.model
            if (model == null) {
                Text("Todavía no hay un modelo.", style = MaterialTheme.typography.titleLarge, color = Mira.Text)
                VSpace(6.dp)
                Text("Créalo en la app de PC con «Crear archivo para el celular».", color = Mira.Text2)
            } else {
                val report = model.report
                if (report != null) {
                    Row(verticalAlignment = Alignment.Bottom) {
                        val pct = (report.accuracy * 100).toInt()
                        Text("$pct%", fontSize = 54.sp, fontWeight = FontWeight.ExtraBold,
                            color = if (pct >= 85) Mira.Green else if (pct >= 65) Mira.Amber else Mira.Red)
                        Spacer(Modifier.width(12.dp))
                        Text(
                            if (report.evalMode == "personas") "de aciertos con personas que el modelo no conocía"
                            else "de aciertos con grabaciones que no usó para aprender",
                            color = Mira.Text2, modifier = Modifier.padding(bottom = 10.dp),
                        )
                    }
                    VSpace(6.dp)
                }
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    for ((cat, name) in CATEGORY_NAMES) {
                        val n = model.signs.count { it.category == cat && !it.isNothing }
                        if (n > 0) {
                            val acc = report?.perCategory?.get(cat)
                            StatPill(if (acc != null) "$name: $n · ${(acc * 100).toInt()}%" else "$name: $n")
                        }
                    }
                    if (report != null) {
                        StatPill("${report.signers} ${if (report.signers == 1) "persona" else "personas"} · ${report.clips} clips")
                    }
                }
                if (report?.trainedAt?.isNotBlank() == true) {
                    VSpace(8.dp)
                    Text("Entrenado: ${report.trainedAt.replace('T', ' ').take(16)}", color = Mira.Text3, fontSize = 13.sp)
                }
            }
            VSpace(16.dp)
            PrimaryButton("Cargar modelo desde archivo", actions.onLoadModel, Modifier.fillMaxWidth(), MiraIcons.Folder)
            if (state.hasUserModel && state.hasBundledModel) {
                TextButton(onClick = actions.onUseBundled, modifier = Modifier.align(Alignment.CenterHorizontally)) {
                    Text("Usar el modelo incluido en la app", color = Mira.Text2)
                }
            }
        }

        // ---- Reconocimiento ----
        GlassCard(Modifier.fillMaxWidth()) {
            Overline("Reconocimiento")
            VSpace(12.dp)
            Text("Sensibilidad", style = MaterialTheme.typography.titleMedium, color = Mira.Text)
            Text("Alta reconoce más rápido; baja se equivoca menos.", color = Mira.Text3, fontSize = 13.sp)
            VSpace(10.dp)
            SegmentedPills(
                Sensitivity.entries.map { it.name to it.label }, state.sensitivity.name,
                { actions.onSensitivity(Sensitivity.valueOf(it)) }, Modifier.fillMaxWidth(),
            )
            VSpace(18.dp)
            Text("Cámara", style = MaterialTheme.typography.titleMedium, color = Mira.Text)
            Text("Frontal si la persona que hace señas sostiene el teléfono; trasera si alguien más la apunta.",
                color = Mira.Text3, fontSize = 13.sp)
            VSpace(10.dp)
            SegmentedPills(
                listOf("front" to "Frontal", "back" to "Trasera"), if (state.frontCamera) "front" else "back",
                { actions.onFrontCamera(it == "front") }, Modifier.fillMaxWidth(),
            )
            VSpace(18.dp)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Leer en voz alta automáticamente", style = MaterialTheme.typography.titleMedium, color = Mira.Text)
                    Text("Dice cada palabra al reconocerla (con la voz del teléfono, sin internet).",
                        color = Mira.Text3, fontSize = 13.sp)
                }
                Switch(
                    checked = state.autoSpeak, onCheckedChange = actions.onAutoSpeak,
                    colors = SwitchDefaults.colors(checkedTrackColor = Mira.Accent, checkedThumbColor = Color.White),
                )
            }
        }

        // ---- Senas que conoce ----
        state.model?.let { model ->
            GlassCard(Modifier.fillMaxWidth()) {
                Overline("Señas que conoce")
                for ((cat, name) in CATEGORY_NAMES) {
                    val signs = model.signs.filter { it.category == cat && !it.isNothing }
                    if (signs.isEmpty()) continue
                    VSpace(14.dp)
                    Text(name, style = MaterialTheme.typography.titleMedium, color = Mira.Text)
                    VSpace(8.dp)
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        for (s in signs) StatPill(s.name, Mira.Text)
                    }
                }
            }
        }

        // ---- Acerca de ----
        GlassCard(Modifier.fillMaxWidth()) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Logo(48.dp)
                Spacer(Modifier.width(14.dp))
                Column {
                    Text("Mira&Tek", style = MaterialTheme.typography.titleLarge, color = Mira.Text)
                    Text("Technovation Girls 2026 · versión ${BuildConfig.VERSION_NAME}", color = Mira.Text3, fontSize = 13.sp)
                }
            }
            VSpace(16.dp)
            FeatureRow(MiraIcons.WifiOff, "Funciona sin internet", "Todo se procesa en este teléfono.")
            VSpace(12.dp)
            FeatureRow(MiraIcons.Lock, "Privada", "La cámara nunca sale del teléfono y no se guarda video.", Mira.Warm2)
        }
        VSpace(8.dp)
    }
}
