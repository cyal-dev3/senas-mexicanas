package mx.miratek.senas.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import mx.miratek.senas.data.LearnClip
import kotlin.math.max
import kotlin.math.min

private val LINKS = arrayOf(
    0 to 1, 1 to 2, 2 to 3, 3 to 4, 0 to 5, 5 to 6, 6 to 7, 7 to 8, 5 to 9, 9 to 10, 10 to 11, 11 to 12,
    9 to 13, 13 to 14, 14 to 15, 15 to 16, 13 to 17, 17 to 18, 18 to 19, 19 to 20, 0 to 17,
)
private val FINGERTIPS = setOf(4, 8, 12, 16, 20)

/** Limites de todas las manos del clip, para centrar y acercar la animacion. */
private class Bounds(val minX: Float, val minY: Float, val maxX: Float, val maxY: Float)

private fun boundsOf(clip: LearnClip): Bounds {
    var minX = Float.MAX_VALUE
    var minY = Float.MAX_VALUE
    var maxX = -Float.MAX_VALUE
    var maxY = -Float.MAX_VALUE
    for (frame in clip.frames) for (hand in frame) {
        if (hand == null) continue
        for (p in 0 until 21) {
            val x = hand[p * 2] * clip.aspect
            val y = hand[p * 2 + 1]
            minX = min(minX, x); maxX = max(maxX, x); minY = min(minY, y); maxY = max(maxY, y)
        }
    }
    if (minX > maxX) return Bounds(0f, 0f, clip.aspect, 1f)
    return Bounds(minX, minY, maxX, maxY)
}

/**
 * Esqueleto animado de como se hace una sena (grabado por una persona del equipo).
 * Se ve como en un espejo: asi es mas facil imitarla.
 */
@Composable
fun SkeletonAnimation(
    clip: LearnClip?,
    modifier: Modifier = Modifier,
    animate: Boolean = true,
    background: Color = Mira.Ink,
    corner: Dp = 24.dp,
) {
    Box(modifier.clip(RoundedCornerShape(corner)).background(background), contentAlignment = Alignment.Center) {
        if (clip == null || clip.frames.isEmpty()) {
            Icon(MiraIcons.Hand, contentDescription = null, tint = Mira.Text3, modifier = Modifier.size(36.dp))
            return@Box
        }
        val index by produceState(clip.cover.coerceIn(0, clip.frames.size - 1), clip, animate) {
            if (!animate) return@produceState
            while (true) {
                for (i in clip.frames.indices) {
                    value = i
                    delay(1000L / clip.fps)
                }
                delay(700)
            }
        }
        val bounds = remember(clip) { boundsOf(clip) }
        Canvas(Modifier.fillMaxSize().padding(14.dp)) {
            drawFrame(clip.frames[index], clip.aspect, bounds)
        }
    }
}

private fun DrawScope.drawFrame(frame: Array<FloatArray?>, aspect: Float, b: Bounds) {
    val w = max(b.maxX - b.minX, 0.05f)
    val h = max(b.maxY - b.minY, 0.05f)
    val scale = min(size.width / w, size.height / h)
    val ox = (size.width - w * scale) / 2
    val oy = (size.height - h * scale) / 2
    val stroke = max(2.5f, size.minDimension * 0.022f)
    for (slot in 0..1) {
        val hand = frame[slot] ?: continue
        val color = if (slot == 1) Mira.Warm else Mira.Accent2
        val pts = Array(21) { p ->
            Offset(ox + (hand[p * 2] * aspect - b.minX) * scale, oy + (hand[p * 2 + 1] - b.minY) * scale)
        }
        for ((a, c) in LINKS) drawLine(color.copy(alpha = 0.28f), pts[a], pts[c], stroke * 2.6f, StrokeCap.Round)
        for ((a, c) in LINKS) drawLine(color, pts[a], pts[c], stroke, StrokeCap.Round)
        pts.forEachIndexed { i, pt ->
            val r = stroke * (if (i in FINGERTIPS) 1.35f else 0.95f)
            drawCircle(color, r + stroke * 0.45f, pt)
            drawCircle(Color.White, r, pt)
        }
    }
}
