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
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import mx.miratek.senas.BuildConfig
import mx.miratek.senas.MainViewModel
import mx.miratek.senas.UiState
import mx.miratek.senas.core.Sensitivity
import mx.miratek.senas.core.SignInfo
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

private val CATEGORY_NAMES = mapOf(
    SignInfo.CATEGORY_WORDS to "Palabras",
    SignInfo.CATEGORY_LETTERS to "Abecedario",
    SignInfo.CATEGORY_NUMBERS to "Números",
)

class SettingsActions(
    val onBack: (() -> Unit)? = null,
    val onLoadModel: () -> Unit = {},
    val onUseBundled: () -> Unit = {},
    val onSensitivity: (Sensitivity) -> Unit = {},
    val onFrontCamera: (Boolean) -> Unit = {},
    val onAutoSpeak: (Boolean) -> Unit = {},
    val onLeftHanded: (Boolean) -> Unit = {},
)

@Composable
fun SettingsScreen(vm: MainViewModel, onBack: (() -> Unit)?, onLoadModel: () -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    StatusBarIcons(light = false)
    SettingsContent(
        state,
        SettingsActions(
            onBack = onBack, onLoadModel = onLoadModel, onUseBundled = vm::useBundledModel,
            onSensitivity = vm::setSensitivity, onFrontCamera = vm::setFrontCamera,
            onAutoSpeak = vm::setAutoSpeak, onLeftHanded = vm::setLeftHanded,
        ),
    )
}

/** "2026-10-20T14:33:05" -> "20 de octubre de 2026, 14:33" (si no se entiende, se muestra tal cual). */
private fun friendlyDate(iso: String): String = runCatching {
    LocalDateTime.parse(iso.take(19))
        .format(DateTimeFormatter.ofPattern("d 'de' MMMM 'de' yyyy, HH:mm", Locale("es", "MX")))
}.getOrDefault(iso.replace('T', ' ').take(16))

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SettingsContent(state: UiState, actions: SettingsActions) {
    var confirmBundled by rememberSaveable { mutableStateOf(false) }
    Column(
        Modifier.fillMaxSize().background(Mira.Bg).verticalScroll(rememberScrollState())
            .statusBarsPadding().navigationBarsPadding().padding(horizontal = 18.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            actions.onBack?.let {
                IconCircleButton(MiraIcons.Back, "Regresar", it)
                Spacer(Modifier.width(14.dp))
            }
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
                // Cual modelo esta activo: el que cargo la persona o el que trae la app
                Text(
                    if (state.usingUserModel) "Usas el modelo que cargaste" else "Usas el modelo incluido en la app",
                    style = MaterialTheme.typography.titleLarge, color = Mira.Text,
                )
                if (report?.trainedAt?.isNotBlank() == true) {
                    Text("Entrenado el ${friendlyDate(report.trainedAt)}", color = Mira.Text3, fontSize = 13.sp)
                }
                VSpace(10.dp)
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
            }
            VSpace(16.dp)
            PrimaryButton("Cargar modelo desde archivo", actions.onLoadModel, Modifier.fillMaxWidth(), MiraIcons.Folder)
            if (state.usingUserModel && state.hasBundledModel) {
                TextButton(onClick = { confirmBundled = true }, modifier = Modifier.align(Alignment.CenterHorizontally)) {
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
            VSpace(14.dp)
            SwitchRow(
                "Hago las señas con la mano izquierda",
                "Actívalo si tu mano principal es la izquierda: así la app te entiende mejor.",
                state.leftHanded, actions.onLeftHanded,
            )
            VSpace(8.dp)
            SwitchRow(
                "Leer en voz alta automáticamente",
                "Dice cada palabra al reconocerla (con la voz del teléfono, sin internet).",
                state.autoSpeak, actions.onAutoSpeak,
            )
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

    if (confirmBundled) {
        AlertDialog(
            onDismissRequest = { confirmBundled = false },
            title = { Text("¿Usar el modelo incluido?") },
            text = {
                Text("Se borrará de este teléfono el modelo que cargaste y la app volverá a usar el que trae " +
                    "incluido. Si después lo quieres de vuelta, tendrás que cargar el archivo otra vez.")
            },
            confirmButton = {
                TextButton(onClick = { confirmBundled = false; actions.onUseBundled() }) { Text("Sí, usar el incluido") }
            },
            dismissButton = { TextButton(onClick = { confirmBundled = false }) { Text("Cancelar") } },
            containerColor = Mira.Surface,
        )
    }
}

/** Fila con interruptor: se puede tocar toda la fila y TalkBack la lee como un solo interruptor. */
@Composable
private fun SwitchRow(title: String, text: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp))
            .toggleable(value = checked, role = Role.Switch, onValueChange = onChange)
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium, color = Mira.Text)
            Text(text, color = Mira.Text3, fontSize = 13.sp)
        }
        Spacer(Modifier.width(12.dp))
        Switch(
            checked = checked, onCheckedChange = null,
            colors = SwitchDefaults.colors(
                checkedTrackColor = Mira.Accent, checkedThumbColor = Color.White,
                // Apagado con los colores de la app (si no, Material usa un lila que no es nuestro)
                uncheckedTrackColor = Mira.Surface3, uncheckedThumbColor = Mira.Text3, uncheckedBorderColor = Mira.Text3,
            ),
        )
    }
}
