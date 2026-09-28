package mx.miratek.senas.ui

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import mx.miratek.senas.MainViewModel
import mx.miratek.senas.UiState
import mx.miratek.senas.core.SignInfo

private val MODES = listOf(
    SignInfo.CATEGORY_WORDS to "Palabras",
    SignInfo.CATEGORY_LETTERS to "Deletreo",
    SignInfo.CATEGORY_NUMBERS to "Números",
)

/** Lo que la pantalla puede pedir (asi se puede dibujar sin camara en las pruebas). */
class TranslatorActions(
    val onMode: (String) -> Unit = {},
    val onDeleteLast: () -> Unit = {},
    val onClear: () -> Unit = {},
    val onSpeak: () -> Unit = {},
    val onSwitchCamera: () -> Unit = {},
    val onSettings: () -> Unit = {},
    val onLoadModel: () -> Unit = {},
)

@Composable
fun TranslatorScreen(vm: MainViewModel, onOpenSettings: () -> Unit, onLoadModel: () -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    StatusBarIcons(light = true)
    val actions = remember(vm) {
        TranslatorActions(
            onMode = vm::setMode, onDeleteLast = vm::deleteLast, onClear = vm::clearPhrase,
            onSpeak = vm::speakPhrase, onSwitchCamera = { vm.setFrontCamera(!vm.state.value.frontCamera) },
            onSettings = onOpenSettings, onLoadModel = onLoadModel,
        )
    }
    TranslatorContent(state, actions) {
        CameraPreview(front = state.frontCamera, analyzer = vm.analyzer, onError = { }, modifier = Modifier.fillMaxSize())
        HandOverlay(vm.hands, state.frontCamera, Modifier.fillMaxSize())
    }
}

@Composable
fun TranslatorContent(state: UiState, actions: TranslatorActions, camera: @Composable BoxScope.() -> Unit) {
    Box(Modifier.fillMaxSize().background(Mira.Ink)) {
        camera()

        // Sombra suave arriba para que la barra se distinga sobre cualquier fondo
        Box(
            Modifier.fillMaxWidth().height(140.dp)
                .background(Brush.verticalGradient(listOf(Mira.Ink.copy(alpha = 0.35f), Color.Transparent)))
        )

        TopBar(state, onSwitch = actions.onSwitchCamera, onSettings = actions.onSettings)

        Column(
            Modifier.align(Alignment.BottomCenter).fillMaxWidth().navigationBarsPadding()
                .padding(horizontal = 12.dp, vertical = 12.dp),
        ) {
            when {
                state.loading -> Unit
                state.model == null -> NoModelCard(actions.onLoadModel)
                else -> BottomPanel(state, actions)
            }
        }
    }
}

@Composable
private fun TopBar(state: UiState, onSwitch: () -> Unit, onSettings: () -> Unit) {
    Column(Modifier.statusBarsPadding().padding(horizontal = 18.dp, vertical = 10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Row(
                Modifier.clip(RoundedCornerShape(24.dp))
                    .background(Mira.Surface.copy(alpha = 0.94f)).padding(start = 6.dp, end = 16.dp, top = 6.dp, bottom = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Logo(38.dp)
                Spacer(Modifier.width(10.dp))
                Column {
                    Text("Mira&Tek", color = Mira.Text, fontSize = 17.sp, fontWeight = FontWeight.Bold)
                    val signs = state.model?.signs?.count { !it.isNothing } ?: 0
                    Text(
                        if (state.model != null) "Modelo listo · $signs señas" else "Sin modelo",
                        color = if (state.model != null) Mira.Text2 else Mira.Amber, fontSize = 12.sp,
                    )
                }
            }
            Spacer(Modifier.weight(1f))
            IconCircleButton(MiraIcons.FlipCamera, "Cambiar de cámara", onSwitch,
                tint = Mira.Text, background = Mira.Surface.copy(alpha = 0.94f))
            Spacer(Modifier.width(10.dp))
            IconCircleButton(MiraIcons.Settings, "Ajustes", onSettings,
                tint = Mira.Text, background = Mira.Surface.copy(alpha = 0.94f))
        }
        val visible = state.prediction?.handsVisible == true
        AnimatedVisibility(
            visible = state.model != null && !visible,
            enter = fadeIn() + slideInVertically(),
            exit = fadeOut() + slideOutVertically(),
        ) {
            Row(
                Modifier.padding(top = 12.dp).clip(RoundedCornerShape(16.dp))
                    .background(Mira.Surface.copy(alpha = 0.94f)).padding(horizontal = 14.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(Modifier.size(8.dp).clip(CircleShape).background(Mira.Amber))
                Spacer(Modifier.width(8.dp))
                Text("Muestra tus manos a la cámara", color = Mira.Text, fontSize = 13.sp)
            }
        }
    }
}

@Composable
private fun BottomPanel(state: UiState, actions: TranslatorActions) {
    // Destello del borde cada vez que se confirma una sena
    val glow = remember { Animatable(0f) }
    LaunchedEffect(state.eventCount) {
        if (state.eventCount > 0) {
            glow.snapTo(1f)
            glow.animateTo(0f, tween(700))
        }
    }
    val border = androidx.compose.ui.graphics.lerp(Mira.Border, Mira.Warm, glow.value)

    GlassCard(Modifier.fillMaxWidth(), borderColor = border) {
        SegmentedPills(MODES, state.mode, actions.onMode, Modifier.fillMaxWidth())
        VSpace(18.dp)
        val prediction = state.prediction
        val handsVisible = prediction?.handsVisible == true
        val sign = prediction?.sign
        val text = when {
            !handsVisible -> "—"
            sign == null || sign.isNothing -> "…"
            else -> sign.name
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Overline("Estoy viendo")
                AnimatedContent(
                    targetState = text,
                    transitionSpec = {
                        (fadeIn(tween(180)) + slideInVertically { it / 3 }) togetherWith fadeOut(tween(120))
                    },
                    label = "sign",
                ) { value ->
                    Text(
                        value, color = Mira.Text, fontSize = if (value.length > 10) 32.sp else 42.sp,
                        fontWeight = FontWeight.ExtraBold, maxLines = 1, overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            val conf = if (handsVisible) (prediction?.confidence ?: 0.0).toFloat() else 0f
            val sure = conf >= state.sensitivity.threshold
            ConfidenceRing(conf, if (sure) Mira.Green else Mira.Amber, 66.dp,
                if (handsVisible) "${(conf * 100).toInt()}%" else "")
        }
        VSpace(6.dp)
        Text(
            hintFor(state.mode), color = Mira.Text3, fontSize = 12.sp,
        )
        VSpace(12.dp)
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Overline("Frase")
            Spacer(Modifier.weight(1f))
            IconCircleButton(MiraIcons.Backspace, "Borrar lo último", actions.onDeleteLast, tint = Mira.Text2, size = 38.dp)
            IconCircleButton(MiraIcons.Close, "Borrar todo", actions.onClear, tint = Mira.Text2, size = 38.dp)
        }
        VSpace(8.dp)
        PhraseChips(state.phrase, Modifier.fillMaxWidth())
        VSpace(16.dp)
        PrimaryButton("Leer en voz alta", actions.onSpeak, Modifier.fillMaxWidth(), MiraIcons.Speaker)
    }
}

private fun hintFor(mode: String) = when (mode) {
    SignInfo.CATEGORY_LETTERS -> "Mantén cada letra un segundo. Baja las manos para terminar la palabra."
    SignInfo.CATEGORY_NUMBERS -> "Para 23 haz 20 y luego 3 (o 2 y luego 3). Baja las manos al terminar."
    else -> "Haz la seña completa y regresa las manos a reposo."
}

@Composable
private fun NoModelCard(onLoadModel: () -> Unit) {
    GlassCard(Modifier.fillMaxWidth()) {
        Overline("Falta un paso", Mira.Amber)
        VSpace(8.dp)
        Text("Carga el modelo", style = MaterialTheme.typography.headlineMedium, color = Mira.Text)
        VSpace(6.dp)
        Text(
            "En la PC entrena el modelo y presiona «Crear archivo para el celular». Mándalo a este " +
                "teléfono (WhatsApp, correo o USB) y ábrelo aquí.",
            style = MaterialTheme.typography.bodyMedium, color = Mira.Text2,
        )
        VSpace(16.dp)
        PrimaryButton("Cargar modelo", onLoadModel, Modifier.fillMaxWidth(), MiraIcons.Folder)
    }
}
