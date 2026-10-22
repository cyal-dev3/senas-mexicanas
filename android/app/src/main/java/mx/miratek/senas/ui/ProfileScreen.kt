package mx.miratek.senas.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import mx.miratek.senas.UiState
import mx.miratek.senas.core.SignInfo

private enum class PlanStyle { PLAIN, HIGHLIGHT, PREMIUM }

private class Plan(
    val badge: String,
    val icon: ImageVector,
    val tag: String?,
    val price: String,
    val per: String?,
    val subtitle: String,
    val features: List<String>,
    val current: Boolean,
    val style: PlanStyle,
)

// Los planes del diseno original del equipo. Hoy todo es gratis y funciona sin internet:
// PRO y ALIADO solo suman cosas nuevas cuando lleguen, no le quitan nada al plan gratis.
private val PLANS = listOf(
    Plan("INCLUSIÓN", MiraIcons.Hand, null, "Gratis", null, "Todo lo que hoy tiene la app",
        listOf("Traductor de señas en tiempo real", "Toda la sección Aprender: palabras, abecedario y números",
            "Funciona sin internet", "La cámara nunca sale de tu teléfono"),
        current = true, style = PlanStyle.PLAIN),
    Plan("PRO", MiraIcons.Star, "RECOMENDADO", "\$89", "/mes", "Para comunicarte cada día más",
        listOf("Todo lo del plan Inclusión", "Más señas y frases nuevas", "Prácticas con más niveles",
            "También funciona sin internet"),
        current = false, style = PlanStyle.HIGHLIGHT),
    Plan("ALIADO", MiraIcons.Heart, "PREMIUM SOCIAL", "\$149", "/mes", "Para apoyar a la comunidad Sorda",
        listOf("Todo lo del plan PRO", "Apoyo a asociaciones de personas Sordas",
            "Material para enseñar LSM en escuelas y familias"),
        current = false, style = PlanStyle.PREMIUM),
)

private fun levelFor(done: Int) = when {
    done >= 40 -> "Experto en LSM"
    done >= 15 -> "Intermedio en LSM"
    else -> "Aprendiz de LSM"
}

@Composable
fun ProfileScreen(state: UiState, onRename: (String) -> Unit) {
    StatusBarIcons(light = false)
    var editing by remember { mutableStateOf(false) }
    var chosen by remember { mutableStateOf<String?>(null) }
    // Solo cuentan las senas que se pueden practicar con la camara (las que el modelo conoce)
    val known = state.model?.signs?.map { it.id }?.toSet().orEmpty()
    val learnable = state.learn.filter { it.id != SignInfo.NOTHING_ID && it.id in known }
    val done = learnable.count { it.id in state.practiced }

    Column(Modifier.fillMaxSize().background(Mira.Bg).verticalScroll(rememberScrollState())) {
        Box(
            Modifier.fillMaxWidth()
                .clip(RoundedCornerShape(bottomStart = 36.dp, bottomEnd = 36.dp))
                .background(Brush.verticalGradient(listOf(Mira.Accent2.copy(alpha = 0.55f), Mira.Accent2.copy(alpha = 0.22f))))
        ) {
            Column(Modifier.statusBarsPadding().padding(start = 18.dp, end = 18.dp, top = 12.dp, bottom = 22.dp)) {
                Surface(shape = RoundedCornerShape(28.dp), color = Mira.Surface, shadowElevation = 6.dp) {
                    Row(Modifier.fillMaxWidth().padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            Modifier.size(76.dp).clip(CircleShape).background(Mira.gradient),
                            contentAlignment = Alignment.Center,
                        ) {
                            Text(state.profileName.trim().take(1).uppercase().ifEmpty { "U" }, color = Color.White,
                                fontSize = 32.sp, fontWeight = FontWeight.Bold)
                        }
                        Spacer(Modifier.width(16.dp))
                        Column(Modifier.weight(1f)) {
                            Overline("Perfil del usuario")
                            Row(verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.clickable { editing = true }) {
                                Text(state.profileName, fontSize = 26.sp, fontWeight = FontWeight.ExtraBold,
                                    color = Mira.Text, maxLines = 1, modifier = Modifier.weight(1f, fill = false))
                                Spacer(Modifier.width(6.dp))
                                Icon(MiraIcons.Edit, contentDescription = "Cambiar nombre", tint = Mira.Text3,
                                    modifier = Modifier.size(18.dp))
                            }
                            VSpace(6.dp)
                            Text(
                                levelFor(done), color = Color.White, fontSize = 13.sp, fontWeight = FontWeight.SemiBold,
                                modifier = Modifier.clip(RoundedCornerShape(14.dp)).background(Mira.Ink)
                                    .padding(horizontal = 14.dp, vertical = 6.dp),
                            )
                        }
                    }
                }
                VSpace(14.dp)
                Surface(shape = RoundedCornerShape(20.dp), color = Mira.Surface.copy(alpha = 0.9f)) {
                    Box(Modifier.padding(16.dp)) { ProgressLine(done, learnable.size, "señas practicadas") }
                }
            }
        }

        VSpace(22.dp)
        Text("Elige el plan que mejor se adapte a ti", color = Mira.Text2, fontSize = 16.sp,
            textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
        Text("Hoy todo es gratis. PRO y ALIADO llegarán con Mira&Tek en Google Play.", color = Mira.Text3,
            fontSize = 13.sp, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 4.dp))
        VSpace(12.dp)
        val pager = rememberPagerState { PLANS.size }
        HorizontalPager(pager, contentPadding = PaddingValues(horizontal = 30.dp), pageSpacing = 14.dp) { page ->
            PlanCard(PLANS[page]) { chosen = PLANS[page].badge }
        }
        VSpace(14.dp)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
            repeat(PLANS.size) { i ->
                Box(
                    Modifier.padding(4.dp).size(width = if (i == pager.currentPage) 22.dp else 8.dp, height = 8.dp)
                        .clip(CircleShape).background(if (i == pager.currentPage) Mira.Accent else Mira.Surface3)
                )
            }
        }
        VSpace(28.dp)
    }

    if (editing) NameDialog(state.profileName, onDismiss = { editing = false }) { onRename(it); editing = false }
    chosen?.let { plan ->
        AlertDialog(
            onDismissRequest = { chosen = null },
            title = { Text("Plan $plan") },
            text = {
                Text("¡Gracias por tu interés! Las membresías se activarán cuando Mira&Tek esté en Google Play. " +
                    "Por ahora puedes usar todas las funciones gratis.")
            },
            confirmButton = { TextButton(onClick = { chosen = null }) { Text("Entendido") } },
            containerColor = Mira.Surface,
        )
    }
}

@Composable
private fun PlanCard(plan: Plan, onSelect: () -> Unit) {
    val premium = plan.style == PlanStyle.PREMIUM
    val textColor = if (premium) Color.White else Mira.Text
    val subColor = if (premium) Color.White.copy(alpha = 0.75f) else Mira.Text2
    val border = when (plan.style) {
        PlanStyle.HIGHLIGHT -> BorderStroke(2.dp, Mira.Accent)
        PlanStyle.PLAIN -> BorderStroke(1.dp, Mira.Border)
        PlanStyle.PREMIUM -> null
    }
    Surface(shape = RoundedCornerShape(30.dp), color = Mira.Surface, border = border, shadowElevation = 4.dp) {
        Column(
            Modifier.fillMaxWidth()
                .background(if (premium) Brush.linearGradient(listOf(Mira.AccentDeep, Mira.Ink)) else Brush.linearGradient(listOf(Mira.Surface, Mira.Surface)))
                .padding(24.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Row(
                    Modifier.clip(RoundedCornerShape(16.dp))
                        .background(if (premium) Color.White.copy(alpha = 0.14f) else Mira.Ink)
                        .padding(horizontal = 12.dp, vertical = 7.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(plan.icon, contentDescription = null, tint = if (plan.style == PlanStyle.HIGHLIGHT) Mira.Warm else Color.White,
                        modifier = Modifier.size(18.dp))
                    Spacer(Modifier.width(6.dp))
                    Text(plan.badge, color = Color.White, fontSize = 15.sp, fontWeight = FontWeight.ExtraBold)
                }
                Spacer(Modifier.weight(1f))
                plan.tag?.let {
                    Text(
                        it, fontSize = 11.sp, fontWeight = FontWeight.ExtraBold,
                        color = if (premium) Mira.Ink else Color.White,
                        modifier = Modifier.clip(RoundedCornerShape(14.dp))
                            .background(if (premium) Mira.Warm else Mira.Accent)
                            .padding(horizontal = 10.dp, vertical = 6.dp),
                    )
                }
            }
            VSpace(18.dp)
            Row(verticalAlignment = Alignment.Bottom) {
                Text(plan.price, fontSize = 38.sp, fontWeight = FontWeight.ExtraBold, color = textColor)
                plan.per?.let {
                    Spacer(Modifier.width(6.dp))
                    Text(it, fontSize = 16.sp, color = subColor, modifier = Modifier.padding(bottom = 7.dp))
                }
            }
            Text(plan.subtitle, color = subColor, fontSize = 15.sp)
            VSpace(16.dp)
            HorizontalDivider(color = if (premium) Color.White.copy(alpha = 0.18f) else Mira.Border)
            VSpace(16.dp)
            for (feature in plan.features) {
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 6.dp)) {
                    Icon(MiraIcons.CheckCircle, contentDescription = null,
                        tint = if (premium) Mira.Accent2 else Mira.Green, modifier = Modifier.size(22.dp))
                    Spacer(Modifier.width(12.dp))
                    Text(feature, color = textColor, fontSize = 15.sp)
                }
            }
            VSpace(18.dp)
            if (plan.current) {
                Text("Plan actual", color = Mira.Text3, fontSize = 16.sp, fontWeight = FontWeight.SemiBold,
                    textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth().padding(vertical = 14.dp))
            } else {
                Box(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(26.dp)).background(Mira.Warm)
                        .clickable(onClick = onSelect).padding(vertical = 15.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text("Seleccionar Plan", color = Mira.Ink, fontSize = 16.sp, fontWeight = FontWeight.ExtraBold)
                }
            }
        }
    }
}

@Composable
private fun NameDialog(current: String, onDismiss: () -> Unit, onSave: (String) -> Unit) {
    var text by remember { mutableStateOf(current) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("¿Cómo te llamas?") },
        text = {
            OutlinedTextField(
                value = text, onValueChange = { text = it.take(30) }, singleLine = true,
                colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Mira.Accent),
            )
        },
        confirmButton = { TextButton(onClick = { onSave(text) }) { Text("Guardar") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
        containerColor = Mira.Surface,
    )
}
