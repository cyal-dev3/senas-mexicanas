package mx.miratek.senas.ui

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.BorderStroke
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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
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
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import mx.miratek.senas.MainViewModel
import mx.miratek.senas.UiState
import mx.miratek.senas.core.SignInfo

val MODES = listOf(
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
    val onLoadModel: () -> Unit = {},
    val onRetryCamera: () -> Unit = {},
)

@Composable
fun TranslatorScreen(vm: MainViewModel, onLoadModel: () -> Unit) {
    val state by vm.state.collectAsStateWithLifecycle()
    StatusBarIcons(light = true)
    val actions = remember(vm) {
        TranslatorActions(
            onMode = vm::setMode, onDeleteLast = vm::deleteLast, onClear = vm::clearPhrase,
            onSpeak = vm::speakPhrase, onSwitchCamera = { vm.setFrontCamera(!vm.state.value.frontCamera) },
            onLoadModel = onLoadModel, onRetryCamera = vm::retryCamera,
        )
    }
    TranslatorContent(state, actions) {
        CameraPreview(
            front = state.frontCamera, analyzer = vm.analyzer, onError = vm::reportCameraError,
            modifier = Modifier.fillMaxSize(), restartKey = state.cameraKey,
        )
        HandOverlay(vm.hands, state.frontCamera, Modifier.fillMaxSize())
    }
}

/**
 * La camara ocupa casi toda la pantalla para que te veas completo haciendo las
 * senas: arriba van el modo y lo que la app esta viendo; abajo, solo una barra
 * delgada con la frase.
 */
@Composable
fun TranslatorContent(state: UiState, actions: TranslatorActions, camera: @Composable BoxScope.() -> Unit) {
    Box(Modifier.fillMaxSize().background(Mira.Ink)) {
        camera()
        Box(
            Modifier.fillMaxWidth().height(150.dp)
                .background(Brush.verticalGradient(listOf(Mira.Ink.copy(alpha = 0.45f), Color.Transparent)))
        )

        Column(Modifier.statusBarsPadding().padding(horizontal = 14.dp, vertical = 8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                LogoPill(state)
                Spacer(Modifier.weight(1f))
                IconCircleButton(MiraIcons.FlipCamera, "Cambiar de cámara", actions.onSwitchCamera,
                    tint = Mira.Text, background = Mira.Surface.copy(alpha = 0.92f), size = 42.dp)
            }
            if (state.model != null) {
                Spacer(Modifier.height(10.dp))
                SegmentedPills(MODES, state.mode, actions.onMode,
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(Mira.Surface.copy(alpha = 0.9f)))
                Spacer(Modifier.height(10.dp))
                GuessPill(state, Modifier.align(Alignment.CenterHorizontally))
            }
        }

        Column(Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(horizontal = 12.dp, vertical = 10.dp)) {
            AnimatedVisibility(visible = state.cameraError != null, enter = fadeIn(), exit = fadeOut()) {
                CameraErrorCard(state.cameraError.orEmpty(), actions.onRetryCamera)
            }
            when {
                state.loading -> Unit
                state.model == null -> NoModelCard(actions.onLoadModel)
                else -> SubtitleBar(state, actions)
            }
        }
    }
}

@Composable
private fun LogoPill(state: UiState) {
    Row(
        Modifier.clip(RoundedCornerShape(22.dp)).background(Mira.Surface.copy(alpha = 0.92f))
            .padding(start = 5.dp, end = 14.dp, top = 5.dp, bottom = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Logo(32.dp)
        Spacer(Modifier.width(8.dp))
        Column {
            Text("Mira&Tek", color = Mira.Text, fontSize = 15.sp, fontWeight = FontWeight.Bold)
            val signs = state.model?.signs?.count { !it.isNothing } ?: 0
            Text(
                if (state.model != null) "$signs señas" else "Sin modelo",
                color = if (state.model != null) Mira.Text2 else Mira.Amber, fontSize = 11.sp,
            )
        }
    }
}

/** Lo que la app esta viendo ahora (o un aviso si no ve tus manos). */
@Composable
fun GuessPill(state: UiState, modifier: Modifier = Modifier) {
    val prediction = state.prediction
    val handsVisible = prediction?.handsVisible == true && state.cameraError == null
    val sign = prediction?.sign
    Row(
        modifier.clip(RoundedCornerShape(24.dp)).background(Mira.Surface.copy(alpha = 0.93f))
            .padding(horizontal = 14.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (!handsVisible) {
            Box(Modifier.size(8.dp).clip(CircleShape).background(Mira.Amber))
            Spacer(Modifier.width(8.dp))
            Text("Muestra tus manos a la cámara", color = Mira.Text, fontSize = 14.sp)
        } else {
            val conf = (prediction?.confidence ?: 0.0).toFloat()
            val sure = conf >= state.sensitivity.threshold && sign?.isNothing == false
            ConfidenceRing(conf, if (sure) Mira.Green else Mira.Amber, 30.dp)
            Spacer(Modifier.width(10.dp))
            val text = if (sign == null || sign.isNothing) "…" else sign.name
            AnimatedContent(
                targetState = text,
                transitionSpec = { (fadeIn(tween(160)) + slideInVertically { it / 3 }) togetherWith fadeOut(tween(100)) },
                label = "guess",
            ) { value ->
                Text(value, color = Mira.Text, fontSize = 22.sp, fontWeight = FontWeight.ExtraBold, maxLines = 1,
                    overflow = TextOverflow.Ellipsis)
            }
            Spacer(Modifier.width(8.dp))
            Text("${(conf * 100).toInt()}%", color = Mira.Text2, fontSize = 13.sp)
        }
    }
}

/** Barra delgada: la frase y sus botones. Destella cuando se confirma una sena. */
@Composable
private fun SubtitleBar(state: UiState, actions: TranslatorActions) {
    val glow = remember { Animatable(0f) }
    LaunchedEffect(state.eventCount) {
        if (state.eventCount > 0) {
            glow.snapTo(1f)
            glow.animateTo(0f, tween(700))
        }
    }
    Surface(
        shape = RoundedCornerShape(26.dp),
        color = Mira.Surface.copy(alpha = 0.94f),
        border = BorderStroke(if (glow.value > 0.05f) 2.dp else 1.dp, lerp(Mira.Border, Mira.Warm, glow.value)),
        shadowElevation = 6.dp,
    ) {
        Row(
            Modifier.padding(start = 12.dp, end = 8.dp, top = 8.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            PhraseChips(state.phrase, Modifier.weight(1f))
            IconCircleButton(MiraIcons.Speaker, "Leer en voz alta", actions.onSpeak, tint = Color.White,
                background = Mira.Accent, size = 42.dp)
            IconCircleButton(MiraIcons.Backspace, "Borrar lo último", actions.onDeleteLast, tint = Mira.Text2, size = 42.dp)
            IconCircleButton(MiraIcons.Close, "Borrar todo", actions.onClear, tint = Mira.Text2, size = 42.dp)
        }
    }
}

@Composable
fun CameraErrorCard(message: String, onRetry: () -> Unit) {
    GlassCard(Modifier.fillMaxWidth().padding(bottom = 12.dp), borderColor = Mira.Amber) {
        Overline("Cámara", Mira.Amber)
        VSpace(6.dp)
        Text(message, style = MaterialTheme.typography.bodyMedium, color = Mira.Text)
        VSpace(12.dp)
        SecondaryButton("Reintentar", onRetry, Modifier.fillMaxWidth(), MiraIcons.FlipCamera)
    }
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
