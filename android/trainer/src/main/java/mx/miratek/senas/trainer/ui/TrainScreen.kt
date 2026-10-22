package mx.miratek.senas.trainer.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import mx.miratek.senas.data.SignCatalog
import mx.miratek.senas.trainer.TrainResult
import mx.miratek.senas.trainer.TrainerState
import mx.miratek.senas.trainer.TrainerViewModel
import mx.miratek.senas.trainer.train.Trainer
import mx.miratek.senas.ui.ConfidenceRing
import mx.miratek.senas.ui.GlassCard
import mx.miratek.senas.ui.Mira
import mx.miratek.senas.ui.MiraIcons
import mx.miratek.senas.ui.Overline
import mx.miratek.senas.ui.PrimaryButton
import mx.miratek.senas.ui.SecondaryButton
import mx.miratek.senas.ui.StatPill
import mx.miratek.senas.ui.StatusBarIcons
import mx.miratek.senas.ui.VSpace

class TrainActions(
    val onTrain: () -> Unit = {},
    val onCancel: () -> Unit = {},
    val onEvaluateFully: (Boolean) -> Unit = {},
    val onShareModel: (toTranslator: Boolean) -> Unit = {},
)

@Composable
fun TrainScreen(state: TrainerState, vm: TrainerViewModel) =
    TrainContent(state, TrainActions(vm::train, vm::cancelTraining, vm::setEvaluateFully, vm::shareModel))

/** Entrenar el modelo con TODAS las grabaciones que hay en este telefono. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun TrainContent(state: TrainerState, actions: TrainActions) {
    StatusBarIcons(light = false)
    val training = state.training
    if (training != null) KeepScreenOn()
    Column(
        Modifier.fillMaxSize().background(Mira.Bg).verticalScroll(rememberScrollState()).statusBarsPadding()
            .padding(horizontal = 18.dp).padding(top = 12.dp, bottom = 24.dp),
    ) {
        Overline("Entrenador")
        Text("Entrenar", style = MaterialTheme.typography.headlineLarge, color = Mira.Text)
        VSpace(16.dp)

        // ---- Lo que hay ----
        val people = state.allCounts.size
        val ready = state.signsReady
        GlassCard(Modifier.fillMaxWidth()) {
            Text("Grabaciones en este teléfono", style = MaterialTheme.typography.titleMedium, color = Mira.Text)
            VSpace(12.dp)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                StatPill("$people persona${if (people == 1) "" else "s"}")
                StatPill("${state.everyoneTotal} grabaciones")
                StatPill("$ready de ${state.signs.size} señas", if (ready == state.signs.size) Mira.Green else Mira.Text2)
            }
            VSpace(12.dp)
            Text(
                when {
                    ready < 2 -> "Hacen falta grabaciones: cada seña necesita al menos ${Trainer.MIN_CLIPS_PER_CLASS}. Graba o abre los archivos que te manden."
                    people == 1 -> "Con una sola persona el modelo aprende sus manos, no las de todos. Junta grabaciones de más personas para que sea certero."
                    else -> "Con $people personas distintas el examen mide cómo le irá a alguien que el modelo nunca vio. Entre más personas, mejor."
                },
                color = Mira.Text2, style = MaterialTheme.typography.bodyMedium,
            )
            if (people >= 2) {
                VSpace(12.dp)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Examen con personas nuevas", color = Mira.Text, style = MaterialTheme.typography.titleMedium)
                        Text("Más honesto, pero tarda varios minutos más", color = Mira.Text3, fontSize = 13.sp)
                    }
                    Switch(
                        checked = state.evaluateFully, onCheckedChange = actions.onEvaluateFully, enabled = training == null,
                        colors = SwitchDefaults.colors(checkedTrackColor = Mira.Accent, checkedThumbColor = Color.White),
                    )
                }
            }
            VSpace(16.dp)
            if (training == null) {
                val enabled = ready >= 2
                PrimaryButton(
                    if (state.hasModel) "Entrenar de nuevo" else "Entrenar modelo",
                    { if (enabled) actions.onTrain() },
                    Modifier.fillMaxWidth().alpha(if (enabled) 1f else 0.5f), icon = TrainerIcons.Bolt,
                )
                VSpace(8.dp)
                Text(
                    "Tarda de 1 a 10 minutos según cuántas grabaciones haya. Deja la app abierta.",
                    color = Mira.Text3, fontSize = 13.sp,
                )
            } else {
                TrainingCard(training, actions.onCancel)
            }
        }

        // ---- Resultado ----
        val result = state.result
        if (result != null) {
            VSpace(16.dp)
            ResultCard(state, result, actions)
        }
    }
}

@Composable
private fun KeepScreenOn() {
    val view = LocalView.current
    DisposableEffect(Unit) {
        view.keepScreenOn = true
        onDispose { view.keepScreenOn = false }
    }
}

@Composable
private fun TrainingCard(progress: mx.miratek.senas.trainer.TrainingProgress, onCancel: () -> Unit) {
    Column {
        Text(progress.message, color = Mira.Text, style = MaterialTheme.typography.titleMedium)
        VSpace(10.dp)
        LinearProgressIndicator(
            progress = { progress.fraction.toFloat().coerceIn(0f, 1f) },
            modifier = Modifier.fillMaxWidth().height(10.dp).clip(RoundedCornerShape(5.dp)),
            color = Mira.Accent, trackColor = Mira.Surface3,
        )
        VSpace(8.dp)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("${(progress.fraction * 100).toInt()}%", color = Mira.Text2, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.weight(1f))
            Text("No cierres la app", color = Mira.Text3, fontSize = 13.sp)
        }
        VSpace(14.dp)
        SecondaryButton("Cancelar", onCancel, Modifier.fillMaxWidth())
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ResultCard(state: TrainerState, r: TrainResult, actions: TrainActions) {
    val percent = (r.accuracy * 100).toInt()
    val color = when {
        r.accuracy >= 0.85 -> Mira.Green
        r.accuracy >= 0.65 -> Mira.Amber
        else -> Mira.Red
    }
    GlassCard(Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            ConfidenceRing(r.accuracy.toFloat(), color, 84.dp, label = "$percent%")
            Spacer(Modifier.width(16.dp))
            Column(Modifier.weight(1f)) {
                Text("Último modelo", style = MaterialTheme.typography.titleMedium, color = Mira.Text)
                Text(
                    if (r.evalMode == "personas") "Aciertos con personas que el modelo no vio al entrenar"
                    else "Aciertos con grabaciones apartadas de la misma persona (sale más alto que con gente nueva)",
                    color = Mira.Text2, style = MaterialTheme.typography.bodyMedium,
                )
                VSpace(4.dp)
                Text(
                    "${r.nClasses} señas · ${r.nClips} grabaciones · ${r.nSigners} persona${if (r.nSigners == 1) "" else "s"}",
                    color = Mira.Text3, fontSize = 13.sp,
                )
            }
        }
        if (r.perCategory.isNotEmpty()) {
            VSpace(14.dp)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                for ((cat, acc) in r.perCategory) {
                    StatPill("${SignCatalog.CATEGORY_NAMES[cat] ?: cat} ${(acc * 100).toInt()}%")
                }
            }
        }
        if (r.perSigner.isNotEmpty()) {
            VSpace(14.dp)
            Overline("Por persona")
            VSpace(6.dp)
            for ((id, acc) in r.perSigner) {
                Row(Modifier.padding(vertical = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(state.names[id] ?: id, color = Mira.Text, modifier = Modifier.weight(1f))
                    Text("${(acc * 100).toInt()}%", color = Mira.Text2, fontWeight = FontWeight.SemiBold)
                }
            }
        }
        if (r.topConfusions.isNotEmpty()) {
            VSpace(14.dp)
            Overline("Lo que más confunde")
            VSpace(6.dp)
            for ((a, b, n) in r.topConfusions) {
                Text("${state.catalog.nameOf(a)} → ${state.catalog.nameOf(b)} ($n)", color = Mira.Text2, fontSize = 14.sp)
            }
        }
        for (w in r.warnings) {
            VSpace(10.dp)
            Row(verticalAlignment = Alignment.Top) {
                Box(Modifier.padding(top = 6.dp).size(8.dp).clip(RoundedCornerShape(4.dp)).background(Mira.Amber))
                Spacer(Modifier.width(10.dp))
                Text(w, color = Mira.Text2, fontSize = 14.sp, lineHeight = 19.sp)
            }
        }
        VSpace(18.dp)
        PrimaryButton("Abrir en Mira&Tek", { actions.onShareModel(true) }, Modifier.fillMaxWidth(), icon = TrainerIcons.Smartphone)
        VSpace(10.dp)
        SecondaryButton("Compartir el modelo", { actions.onShareModel(false) }, Modifier.fillMaxWidth(), icon = TrainerIcons.Share)
        VSpace(10.dp)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(MiraIcons.Lock, null, tint = Mira.Text3, modifier = Modifier.size(16.dp))
            Spacer(Modifier.width(6.dp))
            Text("El modelo no contiene grabaciones: solo números aprendidos.", color = Mira.Text3, fontSize = 12.sp)
        }
    }
}
