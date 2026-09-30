package mx.miratek.senas.ui

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
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
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import mx.miratek.senas.MainViewModel
import mx.miratek.senas.UiState
import mx.miratek.senas.core.SignInfo
import mx.miratek.senas.data.LearnSign

val CATEGORY_TITLES = mapOf(
    SignInfo.CATEGORY_WORDS to "Palabras",
    SignInfo.CATEGORY_LETTERS to "Abecedario",
    SignInfo.CATEGORY_NUMBERS to "Números",
)

/** Senas de una categoria en el orden de la app (sin "Nada"). */
fun UiState.learnList(category: String): List<LearnSign> =
    learn.filter { it.category == category && it.id != SignInfo.NOTHING_ID }

// ============================================================
// Lista de senas
// ============================================================

@Composable
fun LearnScreen(state: UiState, onOpen: (String) -> Unit) {
    StatusBarIcons(light = false)
    var category by rememberSaveable { mutableStateOf(SignInfo.CATEGORY_WORDS) }
    val signs = state.learnList(category)
    val done = signs.count { it.id in state.practiced }
    LazyVerticalGrid(
        columns = GridCells.Fixed(2),
        modifier = Modifier.fillMaxSize().background(Mira.Bg),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) {
            Column(Modifier.statusBarsPadding().padding(top = 16.dp)) {
                Text("Aprender", style = MaterialTheme.typography.headlineLarge, color = Mira.Text)
                Text("Señas de la Lengua de Señas Mexicana (LSM)", color = Mira.Text2, fontSize = 15.sp)
                VSpace(14.dp)
                SegmentedPills(CATEGORY_TITLES.toList(), category, { category = it }, Modifier.fillMaxWidth())
                VSpace(12.dp)
                ProgressLine(done, signs.size, "practicadas")
            }
        }
        items(signs, key = { it.id }) { sign ->
            SignCard(sign, sign.id in state.practiced) { onOpen(sign.id) }
        }
        if (signs.isEmpty()) {
            item(span = { GridItemSpan(maxLineSpan) }) {
                Text("Cargando señas…", color = Mira.Text3, modifier = Modifier.padding(24.dp))
            }
        }
    }
}

@Composable
fun ProgressLine(done: Int, total: Int, label: String) {
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("$done de $total $label", color = Mira.Text2, fontSize = 13.sp, fontWeight = FontWeight.Medium)
        }
        VSpace(6.dp)
        Box(Modifier.fillMaxWidth().height(8.dp).clip(RoundedCornerShape(4.dp)).background(Mira.Surface3)) {
            val fraction = if (total > 0) done.toFloat() / total else 0f
            if (fraction > 0f) {
                Box(Modifier.fillMaxWidth(fraction).height(8.dp).clip(RoundedCornerShape(4.dp)).background(Mira.brand))
            }
        }
    }
}

@Composable
private fun SignCard(sign: LearnSign, practiced: Boolean, onClick: () -> Unit) {
    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(22.dp),
        color = Mira.Surface,
        border = BorderStroke(1.dp, if (practiced) Mira.Green.copy(alpha = 0.55f) else Mira.Border),
        shadowElevation = 2.dp,
    ) {
        Column(Modifier.padding(10.dp)) {
            SkeletonAnimation(sign.clip, Modifier.fillMaxWidth().aspectRatio(1.2f), animate = false, corner = 16.dp)
            VSpace(10.dp)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    sign.name, color = Mira.Text, fontWeight = FontWeight.Bold,
                    fontSize = if (sign.category == SignInfo.CATEGORY_WORDS) 17.sp else 26.sp,
                    maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f),
                )
                if (practiced) Icon(MiraIcons.CheckCircle, contentDescription = "Practicada", tint = Mira.Green,
                    modifier = Modifier.size(20.dp))
            }
            Text(
                when {
                    practiced -> "Practicada"
                    sign.pending -> "Mira la animación"
                    else -> "Ver cómo se hace"
                },
                color = Mira.Text3, fontSize = 12.sp,
            )
        }
    }
}

// ============================================================
// Detalle de una sena
// ============================================================

@Composable
fun SignDetailScreen(state: UiState, signId: String, onBack: () -> Unit, onPractice: (String) -> Unit, onOpen: (String) -> Unit) {
    StatusBarIcons(light = false)
    val sign = state.learn.firstOrNull { it.id == signId } ?: return
    val list = state.learnList(sign.category)
    val index = list.indexOfFirst { it.id == signId }
    Column(
        Modifier.fillMaxSize().background(Mira.Bg).verticalScroll(rememberScrollState())
            .statusBarsPadding().padding(horizontal = 18.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconCircleButton(MiraIcons.Back, "Regresar", onBack)
            Spacer(Modifier.width(12.dp))
            StatPill(CATEGORY_TITLES[sign.category] ?: "")
            Spacer(Modifier.weight(1f))
            if (sign.id in state.practiced) StatPill("Practicada ✓", Mira.Green)
        }
        Text(sign.name, fontSize = if (sign.category == SignInfo.CATEGORY_WORDS) 40.sp else 64.sp,
            fontWeight = FontWeight.ExtraBold, color = Mira.Text)
        SkeletonAnimation(sign.clip, Modifier.fillMaxWidth().aspectRatio(1.15f))
        Text(
            sign.clip?.let { "Grabada por ${it.signer}. Imítala como si te vieras en un espejo." }
                ?: "Todavía no hay una grabación de esta seña.",
            color = Mira.Text3, fontSize = 13.sp,
        )
        GlassCard(Modifier.fillMaxWidth(), alpha = 1f) {
            Overline("Cómo se hace")
            VSpace(8.dp)
            if (sign.pending) {
                Text("Todavía no tenemos la descripción escrita de esta seña. Imita la animación; pronto " +
                    "agregaremos las instrucciones.", color = Mira.Text2, style = MaterialTheme.typography.bodyLarge)
            } else {
                Text(sign.text, color = Mira.Text, style = MaterialTheme.typography.bodyLarge)
                sign.alt?.let {
                    VSpace(10.dp)
                    Text(it, color = Mira.Text2, style = MaterialTheme.typography.bodyMedium)
                }
            }
            VSpace(12.dp)
            Text(sign.sourceLabel, color = Mira.Text3, fontSize = 12.sp)
        }
        if (state.modelKnows(sign.id)) {
            PrimaryButton("Practicar con la cámara", { onPractice(sign.id) }, Modifier.fillMaxWidth(), MiraIcons.Play)
        } else {
            Text("Para practicarla con la cámara, primero hay que grabarla y entrenar el modelo en la PC.",
                color = Mira.Text3, fontSize = 13.sp)
        }
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (index > 0) SecondaryButton("Anterior", { onOpen(list[index - 1].id) }, icon = MiraIcons.ChevronLeft)
            Spacer(Modifier.weight(1f))
            if (index in 0 until list.size - 1) {
                SecondaryButton("Siguiente", { onOpen(list[index + 1].id) }, icon = MiraIcons.ChevronRight)
            }
        }
        VSpace(8.dp)
    }
}

// ============================================================
// Practicar con la camara
// ============================================================

@Composable
fun PracticeScreen(vm: MainViewModel, state: UiState, signId: String, onExit: () -> Unit, onNext: (() -> Unit)?) {
    StatusBarIcons(light = true)
    val haptics = LocalHapticFeedback.current
    LaunchedEffect(state.practiceDone) {
        if (state.practiceDone) haptics.performHapticFeedback(HapticFeedbackType.LongPress)
    }
    PracticeContent(
        state, signId, onExit, onNext,
        onRetry = { vm.startPractice(signId) },
        onFlip = { vm.setFrontCamera(!state.frontCamera) },
        onRetryCamera = vm::retryCamera,
    ) {
        CameraPreview(
            front = state.frontCamera, analyzer = vm.analyzer, onError = vm::reportCameraError,
            modifier = Modifier.fillMaxSize(), restartKey = state.cameraKey,
        )
        HandOverlay(vm.hands, state.frontCamera, Modifier.fillMaxSize())
    }
}

@Composable
fun PracticeContent(
    state: UiState,
    signId: String,
    onExit: () -> Unit,
    onNext: (() -> Unit)?,
    onRetry: () -> Unit,
    onFlip: () -> Unit,
    onRetryCamera: () -> Unit,
    camera: @Composable BoxScope.() -> Unit,
) {
    val sign = state.learn.firstOrNull { it.id == signId }
    Box(Modifier.fillMaxSize().background(Mira.Ink)) {
        camera()
        Box(
            Modifier.fillMaxWidth().height(170.dp)
                .background(Brush.verticalGradient(listOf(Mira.Ink.copy(alpha = 0.45f), Color.Transparent)))
        )
        Column(Modifier.statusBarsPadding().padding(horizontal = 14.dp, vertical = 8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconCircleButton(MiraIcons.Back, "Salir de la práctica", onExit, tint = Mira.Text,
                    background = Mira.Surface.copy(alpha = 0.92f), size = 42.dp)
                Spacer(Modifier.width(10.dp))
                Text(
                    "Practica", color = Mira.Text, fontSize = 15.sp, fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.clip(RoundedCornerShape(20.dp)).background(Mira.Surface.copy(alpha = 0.92f))
                        .padding(horizontal = 14.dp, vertical = 9.dp),
                )
                Spacer(Modifier.weight(1f))
                IconCircleButton(MiraIcons.FlipCamera, "Cambiar de cámara", onFlip, tint = Mira.Text,
                    background = Mira.Surface.copy(alpha = 0.92f), size = 42.dp)
            }
            VSpace(12.dp)
            Row {
                Spacer(Modifier.weight(1f))
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    SkeletonAnimation(sign?.clip, Modifier.size(130.dp), corner = 20.dp,
                        background = Mira.Ink.copy(alpha = 0.85f))
                    Text("Así se hace", color = Color.White, fontSize = 12.sp, modifier = Modifier.padding(top = 4.dp))
                }
            }
        }
        Column(Modifier.align(Alignment.BottomCenter).fillMaxWidth().navigationBarsPadding().padding(12.dp)) {
            if (state.cameraError != null) CameraErrorCard(state.cameraError, onRetryCamera)
            GlassCard(Modifier.fillMaxWidth()) {
                AnimatedContent(state.practiceDone, label = "practice") { done ->
                    if (done) SuccessContent(sign?.name.orEmpty(), onNext, onRetry)
                    else TryContent(state, sign)
                }
            }
        }
    }
}

@Composable
private fun TryContent(state: UiState, sign: LearnSign?) {
    Column {
        Overline("Haz la seña")
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(sign?.name.orEmpty(), fontSize = 36.sp, fontWeight = FontWeight.ExtraBold, color = Mira.Text,
                modifier = Modifier.weight(1f))
            val prediction = state.prediction
            val onTarget = prediction?.handsVisible == true && prediction.sign?.id == sign?.id
            val conf = if (onTarget) (prediction?.confidence ?: 0.0).toFloat() else 0f
            ConfidenceRing(conf, if (onTarget) Mira.Green else Mira.Amber, 56.dp,
                if (onTarget) "${(conf * 100).toInt()}%" else "")
        }
        VSpace(6.dp)
        Text(
            state.practiceHint ?: if (state.prediction?.handsVisible == true)
                "Imita la animación de arriba y mantén la seña un momento."
            else "Muestra tus manos a la cámara.",
            color = if (state.practiceHint != null) Mira.Amber else Mira.Text2, fontSize = 14.sp,
        )
    }
}

@Composable
private fun SuccessContent(name: String, onNext: (() -> Unit)?, onRetry: () -> Unit) {
    val pop by animateFloatAsState(1f, spring(dampingRatio = Spring.DampingRatioMediumBouncy), label = "pop")
    Column {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(MiraIcons.CheckCircle, contentDescription = null, tint = Mira.Green,
                modifier = Modifier.size(52.dp).scale(pop))
            Spacer(Modifier.width(12.dp))
            Column {
                Text("¡Muy bien!", fontSize = 26.sp, fontWeight = FontWeight.ExtraBold, color = Mira.Text)
                Text("Hiciste «$name» correctamente.", color = Mira.Text2, fontSize = 14.sp)
            }
        }
        VSpace(14.dp)
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            SecondaryButton("Otra vez", onRetry, Modifier.weight(1f))
            if (onNext != null) PrimaryButton("Siguiente", onNext, Modifier.weight(1f), MiraIcons.ChevronRight)
        }
    }
}
