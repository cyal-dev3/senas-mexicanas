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

/** Manos del ultimo frame con el tamano de la imagen (para dibujar el esqueleto). */
data class HandsFrame(val hands: FrameHands, val width: Int, val height: Int)

/**
 * Lee cada frame de la camara, lo voltea como espejo (igual que en la PC) y
 * se lo pasa a MediaPipe. Todo corre en el telefono, sin internet.
 *
 * MediaPipe tarda ~1 s en cargar: se crea en el hilo de analisis la primera vez
 * que llega un frame (nunca en el hilo principal) y, si falla, se avisa en
 * espanol en lugar de cerrar la app.
 */
class HandAnalyzer(
    private val context: Context,
    private val onHands: (hands: FrameHands, tSeconds: Double, width: Int, height: Int) -> Unit,
    private val onError: (String) -> Unit,
) : ImageAnalysis.Analyzer {

    @Volatile private var landmarker: HandLandmarker? = null
    @Volatile private var failed = false
    @Volatile private var closed = false
    @Volatile private var ignoreBefore = 0L   // resultados mas viejos que esto ya no se dibujan
    private var previous: FrameHands? = null
    private var lastTs = 0L

    /**
     * Carga MediaPipe (se puede llamar desde cualquier hilo que no sea el principal).
     * Con retry = true vuelve a intentarlo aunque ya haya fallado («Intentar de nuevo»).
     */
    @Synchronized
    fun prepare(retry: Boolean = false): Boolean {
        if (landmarker != null) return true
        if (retry) failed = false
        if (failed || closed) return false
        return try {
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
                .setErrorListener { onError(DETECTOR_FAILED) }
                .build()
            val created = HandLandmarker.createFromOptions(context, options)
            if (closed) {  // nos cerraron mientras cargaba
                runCatching { created.close() }
                return false
            }
            landmarker = created
            true
        } catch (t: Throwable) {
            failed = true
            onError(DETECTOR_UNAVAILABLE)
            false
        }
    }

    /** Olvida la mano del frame anterior y descarta resultados en vuelo (al cambiar de camara o reabrirla). */
    fun resetTracking() {
        previous = null
        ignoreBefore = SystemClock.uptimeMillis()
    }

    override fun analyze(imageProxy: ImageProxy) {
        val lm = landmarker ?: run {
            if (!prepare()) {
                imageProxy.close()
                return
            }
            landmarker!!
        }
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
            lm.detectAsync(BitmapImageBuilder(bitmap).build(), ts)
        } catch (e: RuntimeException) {
            onError(DETECTOR_FAILED)
        }
    }

    private fun onResult(result: HandLandmarkerResult, input: MPImage) {
        if (result.timestampMs() < ignoreBefore) return  // de antes de cerrar/cambiar la camara
        val detections = ArrayList<Detection>()
        val landmarks = result.landmarks()
        val world = result.worldLandmarks()
        val handedness = result.handedness()
        for (i in landmarks.indices) {
            val wldPoints = world.getOrNull(i) ?: continue  // sin puntos 3D no hay forma de la mano
            val img = FloatArray(63)
            val wld = FloatArray(63)
            landmarks[i].forEachIndexed { p, lm ->
                img[p * 3] = lm.x(); img[p * 3 + 1] = lm.y(); img[p * 3 + 2] = lm.z()
            }
            wldPoints.forEachIndexed { p, lm ->
                wld[p * 3] = lm.x(); wld[p * 3 + 1] = lm.y(); wld[p * 3 + 2] = lm.z()
            }
            val label = handedness.getOrNull(i)?.firstOrNull()?.categoryName() ?: "Right"
            detections += Detection(label, img, wld)
        }
        val hands = HandSlots.assign(detections, previous)
        previous = hands
        onHands(hands, result.timestampMs() / 1000.0, input.width, input.height)
    }

    @Synchronized
    fun close() {
        closed = true
        runCatching { landmarker?.close() }
        landmarker = null
    }

    companion object {
        const val DETECTOR_UNAVAILABLE = "No pude iniciar el detector de manos en este teléfono."
        const val DETECTOR_FAILED = "El detector de manos falló. Toca «Intentar de nuevo»."
    }
}
