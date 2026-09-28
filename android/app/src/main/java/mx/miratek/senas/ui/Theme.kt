package mx.miratek.senas.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

/**
 * La paleta sale del logo (igual que en la app de PC): fondo aqua claro,
 * turquesa (mano izquierda) como color principal y amarillo-naranja
 * (mano derecha) como acento.
 */
object Mira {
    val Bg = Color(0xFFF2FAFB)
    val Surface = Color(0xFFFFFFFF)
    val Surface2 = Color(0xFFEDF7F9)
    val Surface3 = Color(0xFFD8EDF1)
    val Border = Color(0xFFDCEBEF)
    val Text = Color(0xFF0A2530)
    val Text2 = Color(0xFF4A6670)
    val Text3 = Color(0xFF86A0A8)
    val Accent = Color(0xFF0A9CB1)
    val AccentDeep = Color(0xFF067488)
    val Accent2 = Color(0xFF22C3D4)
    val Warm = Color(0xFFFFB81C)
    val Warm2 = Color(0xFFFF8A00)
    val Green = Color(0xFF14A865)
    val Amber = Color(0xFFF08C00)
    val Red = Color(0xFFE5484D)
    val Ink = Color(0xFF0C2530)

    /** Botones principales: turquesa profundo -> cian. */
    val gradient = Brush.linearGradient(listOf(AccentDeep, Accent2))

    /** Marca: turquesa -> amarillo, como la flecha del logo. */
    val brand = Brush.linearGradient(listOf(Accent, Warm))
}

private val typography = Typography(
    displayLarge = TextStyle(fontSize = 52.sp, fontWeight = FontWeight.ExtraBold, letterSpacing = (-1).sp),
    headlineLarge = TextStyle(fontSize = 32.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.5).sp),
    headlineMedium = TextStyle(fontSize = 24.sp, fontWeight = FontWeight.Bold),
    titleLarge = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.SemiBold),
    titleMedium = TextStyle(fontSize = 16.sp, fontWeight = FontWeight.SemiBold),
    bodyLarge = TextStyle(fontSize = 16.sp, lineHeight = 23.sp),
    bodyMedium = TextStyle(fontSize = 14.sp, lineHeight = 20.sp),
    labelLarge = TextStyle(fontSize = 15.sp, fontWeight = FontWeight.SemiBold),
    labelSmall = TextStyle(fontSize = 11.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.2.sp),
)

@Composable
fun MiraTekTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = Mira.Accent,
            onPrimary = Color.White,
            secondary = Mira.Warm,
            tertiary = Mira.Accent2,
            background = Mira.Bg,
            onBackground = Mira.Text,
            surface = Mira.Surface,
            onSurface = Mira.Text,
            surfaceVariant = Mira.Surface2,
            onSurfaceVariant = Mira.Text2,
            outline = Mira.Border,
            error = Mira.Red,
        ),
        typography = typography,
        content = content,
    )
}
