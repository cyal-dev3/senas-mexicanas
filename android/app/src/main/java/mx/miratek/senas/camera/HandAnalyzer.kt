package mx.miratek.senas.camera

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import android.os.SystemClock
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import com.google.mediapipe.framework.image.BitmapImageBuilder
import com.google.mediapipe.framework.image.MPImage
import com.google.mediapipe.tasks.core.BaseOptions
import com.google.mediapipe.tasks.core.Delegate
import com.google.mediapipe.tasks.vision.core.RunningMode
import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarker
import com.google.mediapipe.tasks.vision.handlandmarker.HandLandmarkerResult
import mx.miratek.senas.core.Detection
import mx.miratek.senas.core.FrameHands
import mx.miratek.senas.core.HandSlots

/**
 * Lee cada frame de la camara, lo voltea como espejo (igual que en la PC) y
 * se lo pasa a MediaPipe. Todo corre en el telefono, sin internet.
 */
class HandAnalyzer(
    context: Context,
    private val onHands: (hands: FrameHands, tSeconds: Double, width: Int, height: Int) -> Unit,
    private val onError: (String) -> Unit,
) : ImageAnalysis.Analyzer {

    private val landmarker: HandLandmarker
    private var previous: FrameHands? = null
    private var lastTs = 0L

    init {
        val base = BaseOptions.builder()
            .setModelAssetPath("hand_landmarker.task")
            .setDelegate(Delegate.CPU)
            .build()
        val options = HandLandmarker.HandLandmarkerOptions.builder()
            .setBaseOptions(base)
            .setRunningMode(RunningMode.LIVE_STREAM)
            .setNumHands(2)
            .setMinHandDetectionConfidence(0.6f)
            .setMinHandPresenceConfidence(0.5f)
            .setMinTrackingConfidence(0.5f)
            .setResultListener(this::onResult)
            .setErrorListener { e -> onError(e.message ?: "Error del detector de manos") }
            .build()
        landmarker = HandLandmarker.createFromOptions(context, options)
    }

    override fun analyze(imageProxy: ImageProxy) {
        var ts = SystemClock.uptimeMillis()
        if (ts <= lastTs) ts = lastTs + 1  // MediaPipe exige que el tiempo avance
        lastTs = ts
        val bitmap = try {
            val source = imageProxy.toBitmap()
            val matrix = Matrix().apply {
                postRotate(imageProxy.imageInfo.rotationDegrees.toFloat())
                postScale(-1f, 1f)  // espejo: la mano derecha queda a la derecha
            }
            Bitmap.createBitmap(source, 0, 0, source.width, source.height, matrix, true)
        } finally {
            imageProxy.close()
        }
        try {
            landmarker.detectAsync(BitmapImageBuilder(bitmap).build(), ts)
        } catch (e: RuntimeException) {
            onError(e.message ?: "Error del detector de manos")
        }
    }

    private fun onResult(result: HandLandmarkerResult, input: MPImage) {
        val detections = ArrayList<Detection>()
        val landmarks = result.landmarks()
        val world = result.worldLandmarks()
        val handedness = result.handedness()
        for (i in landmarks.indices) {
            val img = FloatArray(63)
            val wld = FloatArray(63)
            landmarks[i].forEachIndexed { p, lm ->
                img[p * 3] = lm.x(); img[p * 3 + 1] = lm.y(); img[p * 3 + 2] = lm.z()
            }
            world.getOrNull(i)?.forEachIndexed { p, lm ->
                wld[p * 3] = lm.x(); wld[p * 3 + 1] = lm.y(); wld[p * 3 + 2] = lm.z()
            }
            val label = handedness.getOrNull(i)?.firstOrNull()?.categoryName() ?: "Right"
            detections += Detection(label, img, wld)
        }
        val hands = HandSlots.assign(detections, previous)
        previous = hands
        onHands(hands, result.timestampMs() / 1000.0, input.width, input.height)
    }

    fun close() {
        runCatching { landmarker.close() }
    }
}
