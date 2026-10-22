package mx.miratek.senas.trainer.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import mx.miratek.senas.trainer.Phase
import mx.miratek.senas.trainer.Session
import mx.miratek.senas.trainer.TrainerState
import mx.miratek.senas.trainer.TrainerViewModel
import mx.miratek.senas.ui.CameraPreview
import mx.miratek.senas.ui.GlassCard
import mx.miratek.senas.ui.HandOverlay
import mx.miratek.senas.ui.IconCircleButton
import mx.miratek.senas.ui.Mira
import mx.miratek.senas.ui.MiraIcons
import mx.miratek.senas.ui.PrimaryButton
import mx.miratek.senas.ui.SecondaryButton
import mx.miratek.senas.ui.SkeletonAnimation
import mx.miratek.senas.ui.StatusBarIcons
import mx.miratek.senas.ui.VSpace
import kotlin.math.ceil

class RecordActions(
    val onStop: () -> Unit = {},
    val onPause: () -> Unit = {},
    val onUndo: () -> Unit = {},
    val onRecordMore: () -> Unit = {},
    val onNext: (String) -> Unit = {},
    val onRetryCamera: () -> Unit = {},
)

@Composable
fun RecordScreen(vm: TrainerViewModel, state: TrainerState, session: Session) {
    RecordContent(
        state, session,
        RecordActions(vm::stopSession, vm::togglePause, vm::undoLast, vm::recordMore, vm::startSession, vm::retryCamera),
    ) {
        CameraPreview(
            front = state.frontCamera, analyzer = vm.analyzer, onError = vm::reportCameraError,
            modifier = Modifier.fillMaxSize(), restartKey = state.cameraKey, onClosed = vm::onCameraClosed,
        )
        HandOverlay(vm.hands, state.frontCamera, Modifier.fillMaxSize())
    }
}

/** Grabacion guiada: la app cuenta, graba 2 s, revisa que se vieran las manos y repite. */
@Composable
fun RecordContent(state: TrainerState, session: Session, actions: RecordActions, camera: @Composable BoxScope.() -> Unit) {
    StatusBarIcons(light = true)
    val sign = state.sign(session.signId)
    val count = state.countOf(session.signId)
    val haptic = LocalHapticFeedback.current
    LaunchedEffect(session.saved) { if (session.saved > 0) haptic.performHapticFeedback(HapticFeedbackType.LongPress) }
    var showHelp by rememberSaveable { mutableStateOf(count == 0) }

    Box(Modifier.fillMaxSize().background(Mira.Ink)) {
        camera()
        // Sombras arriba y abajo para que se lea el texto
        Box(Modifier.fillMaxWidth().height(180.dp).background(Brush.verticalGradient(listOf(Color.Black.copy(alpha = 0.55f), Color.Transparent))))
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.BottomCenter) {
            Box(Modifier.fillMaxWidth().height(240.dp).background(Brush.verticalGradient(listOf(Color.Transparent, Color.Black.copy(alpha = 0.6f)))))
        }

        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(16.dp)) {
            // ---- Arriba: cerrar, nombre de la sena, ayuda ----
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconCircleButton(MiraIcons.Close, "Terminar", actions.onStop, tint = Color.White, background = Color.White.copy(alpha = 0.18f))
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(sign?.name ?: session.signId, color = Color.White, style = MaterialTheme.typography.headlineMedium)
                    Text(
                        "$count de ${state.goal} grabaciones",
                        color = Color.White.copy(alpha = 0.8f), style = MaterialTheme.typography.bodyMedium,
                    )
                }
                IconCircleButton(
                    TrainerIcons.Help, "Cómo se hace", { showHelp = !showHelp },
                    tint = if (showHelp) Mira.Ink else Color.White,
                    background = if (showHelp) Mira.Warm else Color.White.copy(alpha = 0.18f),
                )
            }
            VSpace(10.dp)
            LinearProgressIndicator(
                progress = { (count.toFloat() / state.goal).coerceIn(0f, 1f) },
                modifier = Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(3.dp)),
                color = Mira.Warm, trackColor = Color.White.copy(alpha = 0.25f),
            )
            // ---- Ayuda: animacion de referencia + instrucciones ----
            AnimatedVisibility(showHelp && sign != null, enter = fadeIn(), exit = fadeOut()) {
                Row(Modifier.padding(top = 12.dp), verticalAlignment = Alignment.Top) {
                    SkeletonAnimation(state.clips[session.signId], Modifier.size(118.dp), corner = 18.dp,
                        background = Color.Black.copy(alpha = 0.45f))
                    Spacer(Modifier.width(12.dp))
                    Column(
                        Modifier.weight(1f).clip(RoundedCornerShape(18.dp)).background(Color.Black.copy(alpha = 0.45f)).padding(12.dp),
                    ) {
                        val text = sign!!.text.ifBlank { "Imita la animación. Si tienes dudas, pregúntale a quien sepa LSM." }
                        Text(text, color = Color.White, fontSize = 13.sp, lineHeight = 18.sp, maxLines = 7)
                        if (!sign.isNothing) {
                            VSpace(6.dp)
                            Text(sign.hint, color = Mira.Warm, fontSize = 12.sp, lineHeight = 16.sp, maxLines = 3)
                        }
                    }
                }
            }

            Spacer(Modifier.weight(1f))

            // ---- Centro: cuenta regresiva / grabando / avisos ----
            Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) { CenterOverlay(session, state.handsVisible) }

            Spacer(Modifier.weight(1f))

            // ---- Abajo ----
            if (session.phase == Phase.SIGN_DONE) {
                DoneCard(state, session, actions)
            } else {
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                    IconCircleButton(TrainerIcons.Undo, "Borrar la última", actions.onUndo, tint = Color.White,
                        background = Color.White.copy(alpha = 0.18f), size = 54.dp)
                    Spacer(Modifier.width(22.dp))
                    val paused = session.phase == Phase.PAUSED
                    IconCircleButton(
                        if (paused) MiraIcons.Play else TrainerIcons.Pause, if (paused) "Continuar" else "Pausa", actions.onPause,
                        tint = Mira.Ink, background = if (paused) Mira.Warm else Color.White, size = 72.dp,
                    )
                    Spacer(Modifier.width(22.dp))
                    IconCircleButton(MiraIcons.Check, "Terminar esta seña", actions.onStop, tint = Color.White,
                        background = Color.White.copy(alpha = 0.18f), size = 54.dp)
                }
                VSpace(10.dp)
                Text(
                    when (session.phase) {
                        Phase.PAUSED -> "En pausa. Toca ▶ para seguir."
                        Phase.RECORDING -> if (sign?.isNothing == true) "Grabando: no hagas ninguna seña" else "Grabando: haz la seña ahora"
                        else -> "Ponte donde se vean bien tus manos y la cara"
                    },
                    color = Color.White.copy(alpha = 0.85f), fontSize = 14.sp, textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }

        val error = state.cameraError
        if (error != null) {
            Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
                GlassCard {
                    Text("Cámara", style = MaterialTheme.typography.titleMedium, color = Mira.Text)
                    VSpace(6.dp)
                    Text(error, color = Mira.Text2, style = MaterialTheme.typography.bodyMedium)
                    VSpace(14.dp)
                    PrimaryButton("Intentar de nuevo", actions.onRetryCamera, Modifier.fillMaxWidth())
                }
            }
        }
    }
}

@Composable
private fun BoxScope.CenterOverlay(session: Session, handsVisible: Boolean) {
    when (session.phase) {
        Phase.WAIT_CAMERA -> Pill("Abriendo la cámara…")
        Phase.COUNTDOWN -> {
            val n = ceil(session.remaining).toInt().coerceAtLeast(1)
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                if (session.notice != null) {
                    Pill(session.notice, Mira.Warm)
                    VSpace(14.dp)
                }
                Text(
                    "$n", color = Color.White, fontSize = if (session.first) 112.sp else 72.sp, fontWeight = FontWeight.ExtraBold,
                    textAlign = TextAlign.Center,
                )
                Text(
                    if (session.first) "Prepárate" else "Regresa las manos a reposo",
                    color = Color.White.copy(alpha = 0.85f), fontSize = 16.sp,
                )
                if (!handsVisible && session.first) {
                    VSpace(8.dp)
                    Pill("No veo tus manos todavía", Mira.Amber)
                }
            }
        }
        Phase.RECORDING -> {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(14.dp).clip(RoundedCornerShape(7.dp)).background(Mira.Red))
                    Spacer(Modifier.width(10.dp))
                    Text("Grabando", color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                }
                VSpace(12.dp)
                LinearProgressIndicator(
                    progress = { session.progress.toFloat().coerceIn(0f, 1f) },
                    modifier = Modifier.width(220.dp).height(10.dp).clip(RoundedCornerShape(5.dp)),
                    color = Mira.Warm, trackColor = Color.White.copy(alpha = 0.25f),
                )
            }
        }
        Phase.PAUSED -> Pill("Pausa", Mira.Warm)
        Phase.SIGN_DONE -> Unit
    }
}

@Composable
private fun Pill(text: String, color: Color = Color.White.copy(alpha = 0.2f)) {
    Box(
        Modifier.clip(RoundedCornerShape(20.dp)).background(color).padding(horizontal = 16.dp, vertical = 9.dp),
    ) {
        Text(text, color = if (color == Mira.Warm || color == Mira.Amber) Mira.Ink else Color.White,
            fontWeight = FontWeight.SemiBold, fontSize = 15.sp, textAlign = TextAlign.Center)
    }
}

@Composable
private fun DoneCard(state: TrainerState, session: Session, actions: RecordActions) {
    val sign = state.sign(session.signId)
    val next = state.nextPending(state.category, after = session.signId)
    GlassCard(Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(MiraIcons.CheckCircle, null, tint = Mira.Green, modifier = Modifier.size(30.dp))
            Spacer(Modifier.width(10.dp))
            Column {
                Text("¡Listo!", style = MaterialTheme.typography.titleLarge, color = Mira.Text)
                Text(
                    "${state.countOf(session.signId)} grabaciones de «${sign?.name ?: session.signId}»",
                    color = Mira.Text2, style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
        VSpace(16.dp)
        if (next != null) {
            PrimaryButton("Siguiente: ${state.sign(next)?.name ?: next}", { actions.onNext(next) }, Modifier.fillMaxWidth(),
                icon = MiraIcons.ChevronRight)
            VSpace(10.dp)
        }
        Row {
            SecondaryButton("Grabar más", actions.onRecordMore, Modifier.weight(1f))
            Spacer(Modifier.width(10.dp))
            SecondaryButton(if (next == null) "Terminar" else "Salir", actions.onStop, Modifier.weight(1f))
        }
    }
}
