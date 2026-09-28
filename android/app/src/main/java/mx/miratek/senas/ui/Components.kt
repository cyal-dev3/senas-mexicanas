package mx.miratek.senas.ui

import mx.miratek.senas.R

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** El logo de Mira&Tek (res/drawable-nodpi/logo.png). */
@Composable
fun Logo(size: Dp, modifier: Modifier = Modifier) {
    Image(painterResource(R.drawable.logo), contentDescription = "Mira&Tek", modifier = modifier.size(size))
}

/** Tarjeta oscura semitransparente con borde sutil. */
@Composable
fun GlassCard(
    modifier: Modifier = Modifier,
    borderColor: Color = Mira.Border,
    alpha: Float = 0.96f,
    content: @Composable ColumnScope.() -> Unit,
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(28.dp),
        color = Mira.Surface.copy(alpha = alpha),
        border = BorderStroke(1.dp, borderColor),
        shadowElevation = 6.dp,
    ) {
        Column(Modifier.padding(20.dp), content = content)
    }
}

@Composable
fun Overline(text: String, color: Color = Mira.Text3) {
    Text(text.uppercase(), style = MaterialTheme.typography.labelSmall, color = color)
}

/** Selector tipo "pastilla" (Palabras / Deletreo / Numeros). */
@Composable
fun SegmentedPills(
    options: List<Pair<String, String>>,
    selected: String,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier
            .clip(RoundedCornerShape(16.dp))
            .background(Mira.Surface2)
            .padding(4.dp),
    ) {
        for ((key, label) in options) {
            val isSelected = key == selected
            val bg by animateColorAsState(if (isSelected) Mira.Surface else Color.Transparent, label = "seg")
            val fg by animateColorAsState(if (isSelected) Mira.AccentDeep else Mira.Text2, label = "segText")
            Box(
                Modifier
                    .weight(1f)
                    .clip(RoundedCornerShape(12.dp))
                    .background(bg)
                    .clickable { onSelect(key) }
                    .padding(vertical = 10.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    label, color = fg, fontSize = 14.sp,
                    fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Medium,
                )
            }
        }
    }
}

/** Anillo de confianza con el porcentaje al centro. */
@Composable
fun ConfidenceRing(value: Float, color: Color, size: Dp = 64.dp, label: String? = null) {
    val animated by animateFloatAsState(value.coerceIn(0f, 1f), tween(350), label = "ring")
    Box(Modifier.size(size), contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val stroke = this.size.minDimension * 0.11f
            val inset = stroke / 2
            val arcSize = Size(this.size.width - stroke, this.size.height - stroke)
            drawArc(Mira.Surface3, 0f, 360f, false, Offset(inset, inset), arcSize, style = Stroke(stroke))
            drawArc(color, -90f, 360f * animated, false, Offset(inset, inset), arcSize,
                style = Stroke(stroke, cap = StrokeCap.Round))
        }
        if (label != null) Text(label, color = Mira.Text, fontSize = 14.sp, fontWeight = FontWeight.Bold)
    }
}

@Composable
fun IconCircleButton(
    icon: ImageVector,
    description: String,
    onClick: () -> Unit,
    tint: Color = Mira.Text,
    background: Color = Mira.Surface2,
    size: Dp = 46.dp,
) {
    Box(
        Modifier
            .size(size)
            .clip(CircleShape)
            .background(background)
            .clickable(onClickLabel = description, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = description, tint = tint, modifier = Modifier.size(size * 0.46f))
    }
}

@Composable
fun PrimaryButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, icon: ImageVector? = null) {
    Row(
        modifier
            .clip(RoundedCornerShape(26.dp))
            .background(Mira.gradient)
            .clickable(onClick = onClick)
            .padding(horizontal = 24.dp, vertical = 15.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center,
    ) {
        if (icon != null) {
            Icon(icon, contentDescription = null, tint = Color.White, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(10.dp))
        }
        Text(text, color = Color.White, style = MaterialTheme.typography.labelLarge)
    }
}

@Composable
fun SecondaryButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, icon: ImageVector? = null) {
    Row(
        modifier
            .clip(RoundedCornerShape(26.dp))
            .background(Mira.Surface)
            .border(1.dp, Mira.Border, RoundedCornerShape(26.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 22.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center,
    ) {
        if (icon != null) {
            Icon(icon, contentDescription = null, tint = Mira.Text2, modifier = Modifier.size(19.dp))
            Spacer(Modifier.width(10.dp))
        }
        Text(text, color = Mira.Text, style = MaterialTheme.typography.labelLarge)
    }
}

/** Palabras reconocidas como "chips"; la ultima resaltada. */
@Composable
fun PhraseChips(texts: List<String>, modifier: Modifier = Modifier) {
    val listState = rememberLazyListState()
    LaunchedEffect(texts.size, texts.lastOrNull()) {
        if (texts.isNotEmpty()) listState.animateScrollToItem(texts.size - 1)
    }
    if (texts.isEmpty()) {
        Box(modifier.height(40.dp), contentAlignment = Alignment.CenterStart) {
            Text("Las señas que reconozca aparecerán aquí", color = Mira.Text3, fontSize = 14.sp)
        }
        return
    }
    LazyRow(modifier.height(40.dp), state = listState, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        itemsIndexed(texts) { i, text ->
            val last = i == texts.size - 1
            Box(
                Modifier
                    .clip(RoundedCornerShape(20.dp))
                    .background(if (last) Mira.brand else Brush.linearGradient(listOf(Mira.Surface2, Mira.Surface2)))
                    .padding(horizontal = 14.dp, vertical = 8.dp),
            ) {
                Text(text, color = if (last) Color.White else Mira.Text, fontSize = 16.sp,
                    fontWeight = if (last) FontWeight.Bold else FontWeight.Medium)
            }
        }
    }
}

/** Fila de beneficio con icono (pantalla de bienvenida y ajustes). */
@Composable
fun FeatureRow(icon: ImageVector, title: String, text: String, tint: Color = Mira.Accent) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier
                .size(44.dp)
                .clip(RoundedCornerShape(14.dp))
                .background(tint.copy(alpha = 0.15f)),
            contentAlignment = Alignment.Center,
        ) { Icon(icon, contentDescription = null, tint = tint, modifier = Modifier.size(22.dp)) }
        Spacer(Modifier.width(14.dp))
        Column {
            Text(title, style = MaterialTheme.typography.titleMedium, color = Mira.Text)
            Text(text, style = MaterialTheme.typography.bodyMedium, color = Mira.Text2)
        }
    }
}

@Composable
fun StatPill(text: String, color: Color = Mira.Text2) {
    Box(
        Modifier
            .clip(RoundedCornerShape(12.dp))
            .background(Mira.Surface2)
            .padding(horizontal = 12.dp, vertical = 7.dp),
    ) { Text(text, color = color, fontSize = 13.sp, textAlign = TextAlign.Center) }
}

@Composable
fun RowScope.Grow() = Spacer(Modifier.weight(1f))

@Composable
fun VSpace(dp: Dp) = Spacer(Modifier.height(dp))

@Composable
fun FullWidth(content: @Composable () -> Unit) = Box(Modifier.fillMaxWidth()) { content() }


/** Iconos de la barra de estado: blancos sobre la camara, oscuros sobre fondos claros. */
@Composable
fun StatusBarIcons(light: Boolean) {
    val view = androidx.compose.ui.platform.LocalView.current
    androidx.compose.runtime.DisposableEffect(light) {
        val window = (view.context as? android.app.Activity)?.window
        if (window != null) {
            androidx.core.view.WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !light
        }
        onDispose { }
    }
}
