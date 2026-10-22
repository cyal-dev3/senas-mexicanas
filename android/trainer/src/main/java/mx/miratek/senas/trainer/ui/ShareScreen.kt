package mx.miratek.senas.trainer.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import mx.miratek.senas.trainer.TrainerState
import mx.miratek.senas.trainer.TrainerViewModel
import mx.miratek.senas.ui.FeatureRow
import mx.miratek.senas.ui.GlassCard
import mx.miratek.senas.ui.IconCircleButton
import mx.miratek.senas.ui.Mira
import mx.miratek.senas.ui.MiraIcons
import mx.miratek.senas.ui.Overline
import mx.miratek.senas.ui.PrimaryButton
import mx.miratek.senas.ui.SecondaryButton
import mx.miratek.senas.ui.StatusBarIcons
import mx.miratek.senas.ui.VSpace

enum class TrainerTab(val label: String, val icon: ImageVector) {
    RECORD("Grabar", TrainerIcons.Videocam),
    TRAIN("Entrenar", TrainerIcons.Bolt),
    SHARE("Compartir", TrainerIcons.Share),
}

@Composable
fun TrainerNav(selected: TrainerTab, onSelect: (TrainerTab) -> Unit) {
    Surface(color = Mira.Surface, shadowElevation = 10.dp) {
        Row(Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 12.dp, vertical = 8.dp)) {
            for (tab in TrainerTab.entries) NavItem(tab, tab == selected) { onSelect(tab) }
        }
    }
}

@Composable
private fun RowScope.NavItem(tab: TrainerTab, selected: Boolean, onClick: () -> Unit) {
    val tint = if (selected) Mira.AccentDeep else Mira.Text3
    Column(
        Modifier.weight(1f).clip(RoundedCornerShape(18.dp)).clickable(onClick = onClick).padding(vertical = 6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Box(
            Modifier.clip(RoundedCornerShape(16.dp)).background(if (selected) Mira.Accent.copy(alpha = 0.14f) else Color.Transparent)
                .padding(horizontal = 20.dp, vertical = 4.dp),
        ) { Icon(tab.icon, contentDescription = tab.label, tint = tint, modifier = Modifier.size(24.dp)) }
        Text(tab.label, color = tint, fontSize = 12.sp, fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium)
    }
}

class ShareActions(
    val onShareRecordings: () -> Unit = {},
    val onPickFile: () -> Unit = {},
    val onDeleteSigner: (String) -> Unit = {},
)

@Composable
fun ShareScreen(state: TrainerState, vm: TrainerViewModel, onPickFile: () -> Unit) =
    ShareContent(state, ShareActions(vm::shareRecordings, onPickFile, vm::deleteSigner))

/** Enviar grabaciones, abrir archivos recibidos y ver quien ha grabado. */
@Composable
fun ShareContent(state: TrainerState, actions: ShareActions) {
    StatusBarIcons(light = false)
    var toDelete by rememberSaveable { mutableStateOf<String?>(null) }
    Column(
        Modifier.fillMaxSize().background(Mira.Bg).verticalScroll(rememberScrollState()).statusBarsPadding()
            .padding(horizontal = 18.dp).padding(top = 12.dp, bottom = 24.dp),
    ) {
        Overline("Entrenador")
        Text("Compartir", style = MaterialTheme.typography.headlineLarge, color = Mira.Text)
        VSpace(16.dp)

        GlassCard(Modifier.fillMaxWidth()) {
            FeatureRow(TrainerIcons.Send, "Enviar mis grabaciones", "Un solo archivo .zip para quien coordina.", Mira.Accent)
            VSpace(12.dp)
            Text(
                "Mándalo por WhatsApp, correo o Drive. Solo lleva posiciones de las manos (nunca video) y, si ya entrenaste, el modelo.",
                color = Mira.Text2, style = MaterialTheme.typography.bodyMedium,
            )
            VSpace(14.dp)
            PrimaryButton("Crear archivo para enviar", actions.onShareRecordings, Modifier.fillMaxWidth(), icon = TrainerIcons.Share)
        }
        VSpace(14.dp)
        GlassCard(Modifier.fillMaxWidth()) {
            FeatureRow(MiraIcons.Folder, "Abrir archivo recibido", "Junta las grabaciones de otras personas con las tuyas.", Mira.Warm2)
            VSpace(12.dp)
            Text(
                "También puedes tocar el .zip en WhatsApp o Archivos y elegir «Mira&Tek Entrenador». Los archivos de la app de PC sirven igual.",
                color = Mira.Text2, style = MaterialTheme.typography.bodyMedium,
            )
            VSpace(14.dp)
            SecondaryButton("Elegir archivo", actions.onPickFile, Modifier.fillMaxWidth(), icon = MiraIcons.Folder)
        }
        VSpace(14.dp)
        GlassCard(Modifier.fillMaxWidth()) {
            FeatureRow(TrainerIcons.People, "Personas", "Quién ha grabado en este teléfono.", Mira.AccentDeep)
            VSpace(8.dp)
            val rows = state.allCounts.entries.sortedByDescending { it.value.values.sum() }
            if (rows.isEmpty()) {
                Text("Todavía no hay grabaciones.", color = Mira.Text3, style = MaterialTheme.typography.bodyMedium)
            }
            for ((id, counts) in rows) {
                val me = id == state.signerId
                Row(Modifier.padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text((state.names[id] ?: id) + if (me) " (tú)" else "", color = Mira.Text, fontWeight = FontWeight.SemiBold)
                        Text("${counts.values.sum()} grabaciones · ${counts.size} señas", color = Mira.Text3, fontSize = 13.sp)
                    }
                    Spacer(Modifier.width(8.dp))
                    IconCircleButton(TrainerIcons.Delete, "Borrar grabaciones", { toDelete = id }, tint = Mira.Red, size = 40.dp)
                }
            }
        }
        VSpace(14.dp)
        GlassCard(Modifier.fillMaxWidth()) {
            FeatureRow(TrainerIcons.Laptop, "¿Y la computadora?", "Mismo formato que la app de PC.", Mira.Text2)
            VSpace(10.dp)
            Text(
                "El archivo que creas aquí se abre en la PC con «Abrir archivo recibido», y los de la PC se abren aquí. " +
                    "Así pueden entrenar donde prefieran con las grabaciones de todas las personas.",
                color = Mira.Text2, style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
    val id = toDelete
    if (id != null) {
        val name = state.names[id] ?: id
        ConfirmDialog(
            "¿Borrar las grabaciones de $name?",
            "Se borran de este teléfono las ${state.allCounts[id]?.values?.sum() ?: 0} grabaciones. No se puede deshacer.",
            "Borrar", onDismiss = { toDelete = null }, onConfirm = { actions.onDeleteSigner(id) },
        )
    }
}
