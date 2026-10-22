package mx.miratek.senas.trainer.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import mx.miratek.senas.core.SignInfo
import mx.miratek.senas.data.SignCatalog
import mx.miratek.senas.data.SignSpec
import mx.miratek.senas.trainer.TrainerState
import mx.miratek.senas.trainer.TrainerViewModel
import mx.miratek.senas.ui.ConfidenceRing
import mx.miratek.senas.ui.FeatureRow
import mx.miratek.senas.ui.GlassCard
import mx.miratek.senas.ui.IconCircleButton
import mx.miratek.senas.ui.Logo
import mx.miratek.senas.ui.Mira
import mx.miratek.senas.ui.MiraIcons
import mx.miratek.senas.ui.Overline
import mx.miratek.senas.ui.PrimaryButton
import mx.miratek.senas.ui.SegmentedPills
import mx.miratek.senas.ui.StatusBarIcons
import mx.miratek.senas.ui.VSpace

@Composable
fun LoadingScreen() {
    Box(Modifier.fillMaxSize().background(Mira.Bg), contentAlignment = Alignment.Center) { Logo(96.dp) }
}

/** Bienvenida: explica para que es esta app y pide la camara. */
@Composable
fun TrainerWelcome(denied: Boolean, onRequest: () -> Unit, onOpenSettings: () -> Unit) {
    StatusBarIcons(light = false)
    Box(
        Modifier.fillMaxSize().background(
            Brush.verticalGradient(listOf(Mira.Warm.copy(alpha = 0.22f), Mira.Bg, Mira.Accent2.copy(alpha = 0.18f)))
        )
    ) {
        Column(
            Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(28.dp),
            verticalArrangement = Arrangement.Center,
        ) {
            Logo(104.dp)
            VSpace(28.dp)
            Text("Entrenador", style = MaterialTheme.typography.displayLarge, color = Mira.Text)
            VSpace(8.dp)
            Text(
                "Graba tus señas para que Mira&Tek aprenda de muchas personas distintas y reconozca mejor a todas.",
                style = MaterialTheme.typography.bodyLarge, color = Mira.Text2,
            )
            VSpace(36.dp)
            FeatureRow(MiraIcons.Hand, "Solo posiciones de las manos", "Nunca se guarda video: solo 21 puntos por mano.", Mira.Warm2)
            VSpace(16.dp)
            FeatureRow(MiraIcons.WifiOff, "Funciona sin internet", "Todo se procesa y se guarda en tu teléfono.")
            VSpace(16.dp)
            FeatureRow(TrainerIcons.Share, "Tú decides a quién enviarlo", "Tus grabaciones se quedan aquí hasta que las compartes.", Mira.AccentDeep)
            VSpace(44.dp)
            PrimaryButton("Permitir cámara", onRequest, Modifier.fillMaxWidth())
            if (denied) {
                VSpace(10.dp)
                Text(
                    "Sin la cámara no se pueden grabar las señas.",
                    color = Mira.Amber, style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.align(Alignment.CenterHorizontally),
                )
                TextButton(onClick = onOpenSettings, modifier = Modifier.align(Alignment.CenterHorizontally)) {
                    Text("Abrir ajustes del teléfono", color = Mira.Text2)
                }
            }
        }
    }
}

/** Primera vez: pide el nombre de la persona y con que mano hace las senas. */
@Composable
fun SetupScreen(onDone: (name: String, leftHanded: Boolean) -> Unit) {
    StatusBarIcons(light = false)
    var name by rememberSaveable { mutableStateOf("") }
    var left by rememberSaveable { mutableStateOf(false) }
    val ready = name.trim().length >= 2
    Column(
        Modifier.fillMaxSize().background(Mira.Bg).statusBarsPadding().navigationBarsPadding().padding(28.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Logo(72.dp)
        VSpace(24.dp)
        Text("¿Cómo te llamas?", style = MaterialTheme.typography.headlineLarge, color = Mira.Text)
        VSpace(8.dp)
        Text(
            "Así sabremos de quién es cada grabación cuando se junten las de todo el equipo.",
            style = MaterialTheme.typography.bodyLarge, color = Mira.Text2,
        )
        VSpace(24.dp)
        NameField(name, { name = it }, onDone = { if (ready) onDone(name, left) })
        VSpace(18.dp)
        Overline("¿Con qué mano haces las señas?")
        VSpace(8.dp)
        HandChooser(left) { left = it }
        VSpace(20.dp)
        PrimaryButton("Empezar", { if (ready) onDone(name, left) }, Modifier.fillMaxWidth().let { if (ready) it else it.alpha(0.5f) })
    }
}

/** Derecha / Izquierda. Con la mano izquierda las grabaciones se reflejan al entrenar. */
@Composable
fun HandChooser(leftHanded: Boolean, onChange: (Boolean) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        for ((label, isLeft) in listOf("Derecha" to false, "Izquierda" to true)) {
            val selected = leftHanded == isLeft
            Box(
                Modifier.weight(1f).clip(RoundedCornerShape(14.dp))
                    .background(if (selected) Mira.Accent else Mira.Surface2)
                    .clickable { onChange(isLeft) }.padding(vertical = 11.dp),
                contentAlignment = Alignment.Center,
            ) { Text(label, color = if (selected) Color.White else Mira.Text, fontWeight = FontWeight.SemiBold) }
        }
    }
}

@Composable
private fun NameField(value: String, onChange: (String) -> Unit, onDone: () -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = { onChange(it.take(40)) },
        singleLine = true,
        label = { Text("Tu nombre") },
        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Words, imeAction = ImeAction.Done),
        keyboardActions = KeyboardActions(onDone = { onDone() }),
        colors = OutlinedTextFieldDefaults.colors(
            focusedBorderColor = Mira.Accent, unfocusedBorderColor = Mira.Border,
            focusedLabelColor = Mira.Accent, cursorColor = Mira.Accent,
        ),
        shape = RoundedCornerShape(16.dp),
        modifier = Modifier.fillMaxWidth(),
    )
}

/** Acciones de la pantalla principal (separadas para poder probarla sin ViewModel). */
class HomeActions(
    val onCategory: (String) -> Unit = {},
    val onRecord: (String) -> Unit = {},
    val onRename: (String) -> Unit = {},
    val onGoal: (Int) -> Unit = {},
    val onFront: (Boolean) -> Unit = {},
    val onLeftHanded: (Boolean) -> Unit = {},
)

@Composable
fun HomeScreen(state: TrainerState, vm: TrainerViewModel) = HomeContent(
    state,
    HomeActions(vm::setCategory, vm::startSession, vm::renameSigner, vm::setGoal, vm::setFrontCamera, vm::setLeftHanded),
)

/** Pantalla principal: progreso, categorias y la cuadricula de senas. */
@Composable
fun HomeContent(state: TrainerState, actions: HomeActions) {
    StatusBarIcons(light = false)
    var settings by rememberSaveable { mutableStateOf(false) }
    val signs = state.signsIn(state.category)
    val next = state.nextPending(state.category)
    LazyVerticalGrid(
        columns = GridCells.Adaptive(minSize = 104.dp),
        modifier = Modifier.fillMaxSize().background(Mira.Bg),
        contentPadding = PaddingValues(start = 18.dp, end = 18.dp, bottom = 24.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) {
            Column(Modifier.statusBarsPadding()) {
                VSpace(12.dp)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Logo(40.dp)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Overline("Entrenador")
                        Text(state.signerName, style = MaterialTheme.typography.titleLarge, color = Mira.Text)
                    }
                    IconCircleButton(MiraIcons.Settings, "Ajustes", { settings = true })
                }
                VSpace(18.dp)
                ProgressCard(state, next, onContinue = { next?.let { actions.onRecord(it) } })
                VSpace(18.dp)
                SegmentedPills(
                    options = SignCatalog.CATEGORIES.map { it to SignCatalog.CATEGORY_NAMES[it]!! },
                    selected = state.category,
                    onSelect = actions.onCategory,
                    modifier = Modifier.fillMaxWidth(),
                )
                VSpace(14.dp)
            }
        }
        items(signs, key = { it.id }) { sign ->
            SignTile(sign, state.countOf(sign.id), state.goal) { actions.onRecord(sign.id) }
        }
    }
    if (settings) {
        SettingsDialog(state, onDismiss = { settings = false }, onRename = actions.onRename, onGoal = actions.onGoal,
            onFront = actions.onFront, onLeftHanded = actions.onLeftHanded)
    }
}

@Composable
private fun ProgressCard(state: TrainerState, next: String?, onContinue: () -> Unit) {
    val done = state.myTotal
    val total = state.totalGoal
    val categoryDone = state.signsIn(state.category).count { state.countOf(it.id) >= state.goal }
    val categoryTotal = state.signsIn(state.category).size
    GlassCard(Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            ConfidenceRing(if (total == 0) 0f else done.toFloat() / total, Mira.Warm, 72.dp,
                label = if (total == 0) "0%" else "${(100 * done / total)}%")
            Spacer(Modifier.width(16.dp))
            Column(Modifier.weight(1f)) {
                Text("$done de $total grabaciones", style = MaterialTheme.typography.titleMedium, color = Mira.Text)
                Text(
                    "${SignCatalog.CATEGORY_NAMES[state.category]}: $categoryDone de $categoryTotal señas completas",
                    style = MaterialTheme.typography.bodyMedium, color = Mira.Text2,
                )
                if (state.allCounts.size > 1) {
                    Text(
                        "Todo el equipo: ${state.everyoneTotal} grabaciones de ${state.allCounts.size} personas",
                        style = MaterialTheme.typography.bodyMedium, color = Mira.Text3,
                    )
                }
            }
        }
        VSpace(16.dp)
        if (next != null) {
            PrimaryButton(
                if (done == 0) "Empezar a grabar" else "Continuar: ${state.sign(next)?.name ?: next}",
                onContinue, Modifier.fillMaxWidth(), icon = TrainerIcons.Videocam,
            )
        } else {
            Row(
                Modifier.fillMaxWidth().clip(RoundedCornerShape(26.dp)).background(Mira.Green.copy(alpha = 0.12f))
                    .padding(vertical = 14.dp),
                horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(MiraIcons.CheckCircle, null, tint = Mira.Green, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Text("Categoría completa. ¡Gracias!", color = Mira.Green, fontWeight = FontWeight.SemiBold)
            }
        }
    }
}

@Composable
private fun SignTile(sign: SignSpec, count: Int, goal: Int, onClick: () -> Unit) {
    val done = count >= goal
    val big = sign.category != SignInfo.CATEGORY_WORDS
    val tint = if (sign.isNothing) Mira.Accent2 else Mira.Warm
    Column(
        Modifier
            .clip(RoundedCornerShape(22.dp))
            .background(Mira.Surface)
            .border(1.dp, if (done) Mira.Green.copy(alpha = 0.5f) else Mira.Border, RoundedCornerShape(22.dp))
            .clickable(onClick = onClick)
            .padding(14.dp)
            .height(104.dp),
    ) {
        Row(verticalAlignment = Alignment.Top) {
            Text(
                sign.name,
                modifier = Modifier.weight(1f),
                color = Mira.Text,
                fontSize = if (big) 28.sp else 16.sp,
                fontWeight = if (big) FontWeight.ExtraBold else FontWeight.SemiBold,
                lineHeight = if (big) 30.sp else 20.sp,
                maxLines = 2,
            )
            Box(Modifier.size(34.dp), contentAlignment = Alignment.Center) {
                ConfidenceRing((count.toFloat() / goal).coerceIn(0f, 1f), if (done) Mira.Green else tint, 34.dp)
                if (done) Icon(MiraIcons.Check, null, tint = Mira.Green, modifier = Modifier.size(16.dp))
            }
        }
        Spacer(Modifier.weight(1f))
        Text(
            if (done) "Listo · $count" else "$count de $goal",
            color = if (done) Mira.Green else Mira.Text3,
            fontSize = 13.sp,
        )
    }
}

@Composable
private fun SettingsDialog(
    state: TrainerState, onDismiss: () -> Unit, onRename: (String) -> Unit, onGoal: (Int) -> Unit, onFront: (Boolean) -> Unit,
    onLeftHanded: (Boolean) -> Unit,
) {
    var name by remember { mutableStateOf(state.signerName) }
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = Mira.Surface,
        shape = RoundedCornerShape(28.dp),
        title = { Text("Ajustes", color = Mira.Text) },
        text = {
            Column {
                NameField(name, { name = it }, onDone = {})
                VSpace(18.dp)
                Overline("Grabaciones por seña")
                VSpace(8.dp)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    for (g in listOf(10, 15, 20, 30)) {
                        val selected = state.goal == g
                        Box(
                            Modifier.weight(1f).clip(RoundedCornerShape(14.dp))
                                .background(if (selected) Mira.Accent else Mira.Surface2)
                                .clickable { onGoal(g) }.padding(vertical = 10.dp),
                            contentAlignment = Alignment.Center,
                        ) { Text("$g", color = if (selected) Color.White else Mira.Text, fontWeight = FontWeight.SemiBold) }
                    }
                }
                VSpace(6.dp)
                Text("Más grabaciones = mejor modelo. 15 es un buen punto medio.", color = Mira.Text3, fontSize = 13.sp)
                VSpace(14.dp)
                Overline("Mano con la que haces las señas")
                VSpace(8.dp)
                HandChooser(state.leftHanded, onLeftHanded)
                VSpace(14.dp)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Cámara frontal", color = Mira.Text, style = MaterialTheme.typography.titleMedium)
                        Text("Para verte mientras grabas", color = Mira.Text3, fontSize = 13.sp)
                    }
                    Switch(
                        checked = state.frontCamera, onCheckedChange = onFront,
                        colors = SwitchDefaults.colors(checkedTrackColor = Mira.Accent, checkedThumbColor = Color.White),
                    )
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { if (name.trim().length >= 2) onRename(name); onDismiss() }) {
                Text("Guardar", color = Mira.AccentDeep, fontWeight = FontWeight.SemiBold)
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar", color = Mira.Text2) } },
    )
}

/** Dialogo de confirmacion sencillo. */
@Composable
fun ConfirmDialog(title: String, text: String, confirm: String, onDismiss: () -> Unit, onConfirm: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = Mira.Surface,
        shape = RoundedCornerShape(28.dp),
        title = { Text(title, color = Mira.Text) },
        text = { Text(text, color = Mira.Text2) },
        confirmButton = {
            TextButton(onClick = { onConfirm(); onDismiss() }) { Text(confirm, color = Mira.Red, fontWeight = FontWeight.SemiBold) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar", color = Mira.Text2) } },
    )
}

/** Etiqueta redonda con un numero (ej. clips de una persona). */
@Composable
fun CountBadge(text: String, color: Color = Mira.Accent) {
    Box(
        Modifier.clip(CircleShape).background(color.copy(alpha = 0.14f)).padding(horizontal = 10.dp, vertical = 5.dp),
    ) { Text(text, color = color, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, textAlign = TextAlign.Center) }
}
