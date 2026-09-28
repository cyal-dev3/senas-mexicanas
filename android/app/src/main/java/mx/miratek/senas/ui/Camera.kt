package mx.miratek.senas.ui

import android.util.Size
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.AspectRatioStrategy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.flow.StateFlow
import mx.miratek.senas.HandsFrame
import java.util.concurrent.Executors
import kotlin.math.max

private val CONNECTIONS = arrayOf(
    0 to 1, 1 to 2, 2 to 3, 3 to 4, 0 to 5, 5 to 6, 6 to 7, 7 to 8, 5 to 9, 9 to 10, 10 to 11, 11 to 12,
    9 to 13, 13 to 14, 14 to 15, 15 to 16, 13 to 17, 17 to 18, 18 to 19, 19 to 20, 0 to 17,
)
private val TIPS = setOf(4, 8, 12, 16, 20)

/** Vista de la camara con CameraX: vista previa + analisis de manos. */
@Composable
fun CameraPreview(front: Boolean, analyzer: ImageAnalysis.Analyzer, onError: (String) -> Unit, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val previewView = remember {
        PreviewView(context).apply {
            scaleType = PreviewView.ScaleType.FILL_CENTER
            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
            keepScreenOn = true
        }
    }
    val executor = remember { Executors.newSingleThreadExecutor() }
    AndroidView(factory = { previewView }, modifier = modifier)

    DisposableEffect(front) {
        val future = ProcessCameraProvider.getInstance(context)
        var provider: ProcessCameraProvider? = null
        future.addListener({
            try {
                val p = future.get()
                provider = p
                val ratio = ResolutionSelector.Builder()
                    .setAspectRatioStrategy(AspectRatioStrategy.RATIO_4_3_FALLBACK_AUTO_STRATEGY)
                    .build()
                val preview = Preview.Builder().setResolutionSelector(ratio).build()
                preview.setSurfaceProvider(previewView.surfaceProvider)
                val analysisSelector = ResolutionSelector.Builder()
                    .setAspectRatioStrategy(AspectRatioStrategy.RATIO_4_3_FALLBACK_AUTO_STRATEGY)
                    .setResolutionStrategy(
                        ResolutionStrategy(Size(640, 480), ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER)
                    )
                    .build()
                val analysis = ImageAnalysis.Builder()
                    .setResolutionSelector(analysisSelector)
                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                    .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)
                    .build()
                analysis.setAnalyzer(executor, analyzer)
                val wanted = if (front) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA
                val selector = if (p.hasCamera(wanted)) wanted else {
                    if (front) CameraSelector.DEFAULT_BACK_CAMERA else CameraSelector.DEFAULT_FRONT_CAMERA
                }
                p.unbindAll()
                p.bindToLifecycle(lifecycleOwner, selector, preview, analysis)
            } catch (e: Exception) {
                onError("No pude abrir la cámara. Cierra otras apps que la usen e intenta de nuevo.")
            }
        }, ContextCompat.getMainExecutor(context))
        onDispose { provider?.unbindAll() }
    }
}

/**
 * Dibuja el esqueleto de las manos sobre la camara.
 * Las coordenadas vienen de la imagen ya volteada como espejo; la camara
 * frontal tambien se muestra como espejo, la trasera no.
 */
@Composable
fun HandOverlay(handsFlow: StateFlow<HandsFrame?>, front: Boolean, modifier: Modifier = Modifier) {
    val frame by handsFlow.collectAsStateWithLifecycle()
    Canvas(modifier) {
        val f = frame ?: return@Canvas
        val w = f.width.toFloat()
        val h = f.height.toFloat()
        val scale = max(size.width / w, size.height / h)
        val ox = (size.width - w * scale) / 2
        val oy = (size.height - h * scale) / 2
        for (slot in 0..1) {
            if (!f.hands.present(slot)) continue
            val color = if (slot == 1) Mira.Warm else Mira.Accent2
            val pts = Array(21) { p ->
                var x = f.hands.image[slot * 63 + p * 3]
                val y = f.hands.image[slot * 63 + p * 3 + 1]
                if (!front) x = 1f - x
                Offset(ox + x * w * scale, oy + y * h * scale)
            }
            for ((a, b) in CONNECTIONS) {
                drawLine(color.copy(alpha = 0.28f), pts[a], pts[b], strokeWidth = 16f, cap = StrokeCap.Round)
            }
            for ((a, b) in CONNECTIONS) {
                drawLine(color, pts[a], pts[b], strokeWidth = 6f, cap = StrokeCap.Round)
            }
            pts.forEachIndexed { i, pt ->
                val r = if (i in TIPS) 10f else 6.5f
                drawCircle(color, r + 3f, pt)
                drawCircle(Color.White, r, pt)
            }
        }
    }
}
