package mx.miratek.senas.trainer

import android.app.Application
import android.content.Context
import android.net.Uri
import android.os.SystemClock
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import mx.miratek.senas.camera.HandAnalyzer
import mx.miratek.senas.camera.HandsFrame
import mx.miratek.senas.core.FrameHands
import mx.miratek.senas.core.SignInfo
import mx.miratek.senas.data.LearnClip
import mx.miratek.senas.data.LearnRepository
import mx.miratek.senas.data.SignCatalog
import mx.miratek.senas.data.SignSpec
import mx.miratek.senas.trainer.data.Clip
import mx.miratek.senas.trainer.data.ClipStore
import mx.miratek.senas.trainer.data.Packages
import mx.miratek.senas.trainer.train.TrainConfig
import mx.miratek.senas.trainer.train.TrainedModel
import mx.miratek.senas.trainer.train.Trainer
import mx.miratek.senas.trainer.train.TrainingCancelled
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean

enum class Phase { WAIT_CAMERA, COUNTDOWN, RECORDING, PAUSED, SIGN_DONE }

/** Una sesion de grabacion de UNA sena (cuenta regresiva -> graba -> guarda -> repite). */
data class Session(
    val signId: String,
    val phase: Phase,
    val remaining: Double = 0.0,   // segundos que faltan de la cuenta regresiva
    val total: Double = 1.0,
    val progress: Double = 0.0,    // 0..1 de la grabacion en curso
    val first: Boolean = true,
    val notice: String? = null,    // aviso breve ("No vi tus manos")
    val saved: Int = 0,            // clips guardados en esta sesion
)

data class TrainingProgress(val fraction: Double, val message: String)

/** Resumen del ultimo modelo entrenado (se guarda en modelos/reporte.json). */
data class TrainResult(
    val accuracy: Double,
    val evalMode: String,
    val nClips: Int,
    val nSigners: Int,
    val nClasses: Int,
    val perCategory: Map<String, Double>,
    val perSigner: Map<String, Double>,
    val topConfusions: List<Triple<String, String, Int>>,
    val warnings: List<String>,
    val seconds: Double,
    val trainedAt: String,
) {
    fun toJson(): JSONObject = JSONObject()
        .put("accuracy", accuracy).put("eval_mode", evalMode).put("n_clips", nClips).put("n_signers", nSigners)
        .put("n_classes", nClasses).put("per_category", JSONObject(perCategory)).put("per_signer", JSONObject(perSigner))
        .put("top_confusions", JSONArray(topConfusions.map { JSONArray(listOf(it.first, it.second, it.third)) }))
        .put("warnings", JSONArray(warnings)).put("seconds", seconds).put("trained_at", trainedAt)

    companion object {
        fun fromJson(o: JSONObject): TrainResult {
            fun doubles(key: String): Map<String, Double> {
                val j = o.optJSONObject(key) ?: return emptyMap()
                return j.keys().asSequence().associateWith { j.optDouble(it) }
            }
            val top = o.optJSONArray("top_confusions")
            val warnings = o.optJSONArray("warnings")
            return TrainResult(
                accuracy = o.optDouble("accuracy"), evalMode = o.optString("eval_mode"),
                nClips = o.optInt("n_clips"), nSigners = o.optInt("n_signers"), nClasses = o.optInt("n_classes"),
                perCategory = doubles("per_category"), perSigner = doubles("per_signer"),
                topConfusions = (0 until (top?.length() ?: 0)).map { i ->
                    val a = top!!.getJSONArray(i)
                    Triple(a.getString(0), a.getString(1), a.getInt(2))
                },
                warnings = (0 until (warnings?.length() ?: 0)).map { warnings!!.getString(it) },
                seconds = o.optDouble("seconds"), trainedAt = o.optString("trained_at"),
            )
        }
    }
}

data class TrainerState(
    val loading: Boolean = true,
    val signerId: String = "",
    val signerName: String = "",
    val leftHanded: Boolean = false,   // hace las senas con la mano izquierda (se refleja al entrenar)
    val goal: Int = GOAL_DEFAULT,
    val category: String = SignInfo.CATEGORY_WORDS,
    val signs: List<SignSpec> = emptyList(),
    val clips: Map<String, LearnClip> = emptyMap(),     // animaciones de referencia
    val myCounts: Map<String, Int> = emptyMap(),
    val allCounts: Map<String, Map<String, Int>> = emptyMap(),  // por persona
    val names: Map<String, String> = emptyMap(),
    val session: Session? = null,
    val handsVisible: Boolean = false,
    val frontCamera: Boolean = true,
    val cameraError: String? = null,
    val cameraKey: Int = 0,
    val training: TrainingProgress? = null,
    val result: TrainResult? = null,
    val hasModel: Boolean = false,
    val evaluateFully: Boolean = true,
) {
    val setupDone get() = signerId.isNotEmpty()
    val catalog get() = SignCatalog(signs)
    fun sign(id: String): SignSpec? = signs.firstOrNull { it.id == id }
    fun signsIn(category: String): List<SignSpec> = catalog.inCategory(category)
    fun countOf(id: String) = myCounts[id] ?: 0
    val totalGoal get() = signs.size * goal
    val myTotal get() = myCounts.values.sum()
    val everyoneTotal get() = allCounts.values.sumOf { it.values.sum() }
    val signsReady get() = signs.count { s -> allCounts.values.sumOf { it[s.id] ?: 0 } >= Trainer.MIN_CLIPS_PER_CLASS }

    /** La siguiente sena de la categoria a la que le faltan clips (o null si ya esta completa). */
    fun nextPending(category: String, after: String? = null): String? {
        val list = signsIn(category)
        val start = if (after == null) 0 else list.indexOfFirst { it.id == after } + 1
        val rotated = list.drop(start) + list.take(start)
        return rotated.firstOrNull { countOf(it.id) < goal }?.id
    }

    companion object {
        const val GOAL_DEFAULT = 15
    }
}

/** Pide a la Activity que comparta un archivo (hoja de compartir del sistema). */
data class ShareRequest(val file: File, val mime: String, val title: String, val toTranslator: Boolean = false)

class TrainerViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("entrenador", Context.MODE_PRIVATE)
    val store = ClipStore(File(app.filesDir, "datos"))
    private val modelsDir = File(app.filesDir, "modelos")
    val modelJson = File(modelsDir, "modelo_actual.json")
    val modelNpz = File(modelsDir, "modelo_actual.npz")
    private val reportFile = File(modelsDir, "reporte.json")
    private val shareDir = File(app.cacheDir, "compartir")

    private val _state = MutableStateFlow(
        TrainerState(
            signerId = prefs.getString("signerId", "")!!,
            signerName = prefs.getString("signerName", "")!!,
            leftHanded = prefs.getBoolean("leftHanded", false),
            goal = prefs.getInt("goal", TrainerState.GOAL_DEFAULT).coerceIn(5, 60),
            category = prefs.getString("category", SignInfo.CATEGORY_WORDS)!!,
            frontCamera = prefs.getBoolean("frontCamera", true),
            evaluateFully = prefs.getBoolean("evaluateFully", true),
        )
    )
    val state: StateFlow<TrainerState> = _state.asStateFlow()

    private val _hands = MutableStateFlow<HandsFrame?>(null)
    val hands: StateFlow<HandsFrame?> = _hands.asStateFlow()

    private val _messages = MutableSharedFlow<String>(extraBufferCapacity = 4)
    val messages: SharedFlow<String> = _messages.asSharedFlow()

    private val _shares = MutableSharedFlow<ShareRequest>(extraBufferCapacity = 2)
    val shares: SharedFlow<ShareRequest> = _shares.asSharedFlow()

    // Grabacion en curso (solo se toca desde onHands y el ciclo de la sesion)
    private class Frame(val t: Double, val image: FloatArray, val world: FloatArray)
    private val lock = Any()
    private val frames = ArrayList<Frame>()
    @Volatile private var recording = false
    @Volatile private var lastFrameAt = 0.0
    @Volatile private var aspect = 4.0 / 3
    private var countdownEnd = 0.0
    private var recordStart = 0.0
    private var sessionJob: Job? = null
    private var trainJob: Job? = null
    private val cancelTraining = AtomicBoolean(false)

    /** Crearlo es barato: MediaPipe se carga en prepare() (ver init) o con el primer frame. */
    val analyzer = HandAnalyzer(app, ::onHands) { error -> _state.update { it.copy(cameraError = error) } }

    private fun prepareDetector(retry: Boolean = false) {
        viewModelScope.launch(Dispatchers.IO) {
            val ready = runCatching { analyzer.prepare(retry) }.getOrDefault(false)
            if (!ready) _state.update { it.copy(cameraError = HandAnalyzer.DETECTOR_UNAVAILABLE) }
        }
    }

    init {
        ClipStore.APP_VERSION = "android-entrenador ${BuildConfig.VERSION_NAME}"
        viewModelScope.launch(Dispatchers.IO) {
            val info = readAsset(LearnRepository.INFO)
            val catalog = info?.let { runCatching { SignCatalog.parse(it) }.getOrNull() }
            val clips = info?.let { i ->
                runCatching { LearnRepository.parse(i, readAsset(LearnRepository.CLIPS)) }.getOrNull()
            }?.associate { it.id to it.clip }?.filterValues { it != null }?.mapValues { it.value!! } ?: emptyMap()
            val result = runCatching { TrainResult.fromJson(JSONObject(reportFile.readText())) }.getOrNull()
            _state.update {
                it.copy(loading = false, signs = catalog?.signs ?: emptyList(), clips = clips, result = result,
                    hasModel = modelJson.exists())
            }
            refreshCounts()
        }
        prepareDetector()
    }

    private fun readAsset(name: String): String? =
        runCatching { getApplication<Application>().assets.open(name).bufferedReader().use { it.readText() } }.getOrNull()

    private fun refreshCounts() {
        val all = store.countsBySigner()
        val names = store.signerNames()
        _state.update { it.copy(allCounts = all, names = names, myCounts = all[it.signerId] ?: emptyMap()) }
    }

    // ---------------- Persona ----------------

    fun createSigner(name: String, leftHanded: Boolean) {
        val clean = name.trim().take(40)
        if (clean.isBlank()) return
        val id = "${Packages.slugify(clean)}-${UUID.randomUUID().toString().replace("-", "").take(4)}"
        prefs.edit().putString("signerId", id).putString("signerName", clean).putBoolean("leftHanded", leftHanded).apply()
        store.setSignerName(id, clean)
        _state.update { it.copy(signerId = id, signerName = clean, leftHanded = leftHanded) }
        refreshCounts()
    }

    fun setLeftHanded(left: Boolean) {
        prefs.edit().putBoolean("leftHanded", left).apply()
        _state.update { it.copy(leftHanded = left) }
    }

    fun renameSigner(name: String) {
        val clean = name.trim().take(40)
        if (clean.isBlank()) return
        prefs.edit().putString("signerName", clean).apply()
        store.setSignerName(_state.value.signerId, clean)
        _state.update { it.copy(signerName = clean) }
        refreshCounts()
    }

    fun setGoal(goal: Int) {
        val g = goal.coerceIn(5, 60)
        prefs.edit().putInt("goal", g).apply()
        _state.update { it.copy(goal = g) }
    }

    fun setCategory(category: String) {
        prefs.edit().putString("category", category).apply()
        _state.update { it.copy(category = category) }
    }

    fun setFrontCamera(front: Boolean) {
        prefs.edit().putBoolean("frontCamera", front).apply()
        _hands.value = null
        analyzer.resetTracking()
        _state.update { it.copy(frontCamera = front) }
    }

    /** La camara se cerro (al salir de la grabacion): no dejar un esqueleto viejo dibujado. */
    fun onCameraClosed() {
        _hands.value = null
        analyzer.resetTracking()
    }

    fun setEvaluateFully(on: Boolean) {
        prefs.edit().putBoolean("evaluateFully", on).apply()
        _state.update { it.copy(evaluateFully = on) }
    }

    fun reportCameraError(message: String) = _state.update { it.copy(cameraError = message) }

    fun retryCamera() {
        _hands.value = null
        analyzer.resetTracking()
        _state.update { it.copy(cameraError = null, cameraKey = it.cameraKey + 1) }
        prepareDetector(retry = true)
    }

    // ---------------- Camara ----------------

    private fun onHands(hands: FrameHands, t: Double, width: Int, height: Int) {
        _hands.value = HandsFrame(hands, width, height)
        lastFrameAt = SystemClock.uptimeMillis() / 1000.0
        aspect = width.toDouble() / height
        if (recording) synchronized(lock) { frames += Frame(t, hands.image, hands.world) }
        val visible = hands.any
        if (_state.value.handsVisible != visible) _state.update { it.copy(handsVisible = visible, cameraError = null) }
    }

    // ---------------- Sesion de grabacion ----------------

    fun startSession(signId: String) {
        stopSession()
        _state.update { it.copy(session = Session(signId, Phase.WAIT_CAMERA, total = FIRST_COUNTDOWN)) }
        sessionJob = viewModelScope.launch(Dispatchers.Default) {
            while (isActive) {
                tick()
                delay(40)
            }
        }
    }

    fun stopSession() {
        sessionJob?.cancel()
        sessionJob = null
        recording = false
        synchronized(lock) { frames.clear() }
        _state.update { it.copy(session = null) }
    }

    fun togglePause() {
        val s = _state.value.session ?: return
        if (s.phase == Phase.PAUSED) {
            _state.update { it.copy(session = s.copy(phase = Phase.WAIT_CAMERA, first = true, notice = null)) }
        } else if (s.phase == Phase.COUNTDOWN || s.phase == Phase.RECORDING || s.phase == Phase.WAIT_CAMERA) {
            recording = false
            synchronized(lock) { frames.clear() }
            _state.update { it.copy(session = s.copy(phase = Phase.PAUSED, progress = 0.0, notice = null)) }
        }
    }

    /** Grabar mas clips de la misma sena aunque ya se cumplio la meta. */
    fun recordMore() {
        val s = _state.value.session ?: return
        _state.update { it.copy(session = s.copy(phase = Phase.WAIT_CAMERA, first = true, notice = null)) }
    }

    /** Borra la ultima grabacion de esta sena (por si salio mal). */
    fun undoLast() {
        val st = _state.value
        val s = st.session ?: return
        viewModelScope.launch(Dispatchers.IO) {
            val last = store.lastClip(st.signerId, s.signId)
            if (last == null) {
                message("No hay grabaciones de esta seña para borrar.")
                return@launch
            }
            store.delete(last)
            refreshCounts()
            val now = _state.value.session ?: return@launch
            val phase = if (now.phase == Phase.SIGN_DONE) Phase.WAIT_CAMERA else now.phase
            _state.update {
                it.copy(session = now.copy(phase = phase, first = true, saved = (now.saved - 1).coerceAtLeast(0),
                    notice = "Se borró la última grabación"))
            }
        }
    }

    private fun tick() {
        val st = _state.value
        val s = st.session ?: return
        val now = SystemClock.uptimeMillis() / 1000.0
        val cameraAlive = now - lastFrameAt < 1.2
        when (s.phase) {
            Phase.WAIT_CAMERA -> if (cameraAlive) beginCountdown(s.first)
            Phase.COUNTDOWN -> {
                if (!cameraAlive) {
                    _state.update { it.copy(session = s.copy(phase = Phase.WAIT_CAMERA)) }
                    return
                }
                val remaining = countdownEnd - now
                if (remaining <= 0) beginRecording() else _state.update { it.copy(session = s.copy(remaining = remaining)) }
            }
            Phase.RECORDING -> {
                if (!cameraAlive) {
                    recording = false
                    synchronized(lock) { frames.clear() }
                    _state.update { it.copy(session = s.copy(phase = Phase.WAIT_CAMERA, progress = 0.0)) }
                    return
                }
                val progress = (now - recordStart) / CLIP_SECONDS
                if (progress >= 1.0) finishClip() else _state.update { it.copy(session = s.copy(progress = progress)) }
            }
            Phase.PAUSED, Phase.SIGN_DONE -> Unit
        }
    }

    private fun beginCountdown(first: Boolean, notice: String? = null) {
        val total = if (first) FIRST_COUNTDOWN else BETWEEN_CLIPS + (if (notice != null) 0.8 else 0.0)
        countdownEnd = SystemClock.uptimeMillis() / 1000.0 + total
        _state.update { st ->
            st.copy(session = st.session?.copy(phase = Phase.COUNTDOWN, remaining = total, total = total, first = first,
                progress = 0.0, notice = notice))
        }
    }

    private fun beginRecording() {
        synchronized(lock) { frames.clear() }
        recordStart = SystemClock.uptimeMillis() / 1000.0
        recording = true
        _state.update { st -> st.copy(session = st.session?.copy(phase = Phase.RECORDING, progress = 0.0, notice = null)) }
    }

    private fun finishClip() {
        recording = false
        val taken = synchronized(lock) { ArrayList(frames).also { frames.clear() } }
        val st = _state.value
        val s = st.session ?: return
        val needsHands = s.signId != SignInfo.NOTHING_ID
        val present = taken.count { !it.image[0].isNaN() || !it.image[63].isNaN() }
        when {
            taken.size < ClipStore.MIN_FRAMES -> beginCountdown(false, "La cámara va lenta, otra vez…")
            needsHands && present < MIN_HAND_FRACTION * taken.size ->
                beginCountdown(false, "No vi tus manos. Ponlas frente a la cámara")
            else -> {
                try {
                    store.saveClip(
                        s.signId, st.signerId, DoubleArray(taken.size) { taken[it].t },
                        taken.map { it.image }, taken.map { it.world }, aspect, mirror = st.leftHanded,
                    )
                } catch (e: Exception) {
                    beginCountdown(false, "No pude guardar: ${e.message}")
                    return
                }
                refreshCounts()
                val saved = s.saved + 1
                val count = _state.value.countOf(s.signId)
                if (count >= st.goal) {
                    _state.update { it.copy(session = it.session?.copy(phase = Phase.SIGN_DONE, saved = saved, progress = 0.0)) }
                } else {
                    _state.update { it.copy(session = it.session?.copy(saved = saved)) }
                    beginCountdown(false)
                }
            }
        }
    }

    // ---------------- Entrenar ----------------

    val isTraining get() = trainJob?.isActive == true

    fun train() {
        if (isTraining) return
        cancelTraining.set(false)
        val st = _state.value
        trainJob = viewModelScope.launch(Dispatchers.Default) {
            _state.update { it.copy(training = TrainingProgress(0.0, "Leyendo las grabaciones…")) }
            try {
                val refs = store.listClips()
                val clips = ArrayList<Clip>(refs.size)
                for ((i, ref) in refs.withIndex()) {
                    runCatching { store.load(ref) }.getOrNull()?.let { clips += it }  // un clip danado no tumba todo
                    if (i % 25 == 0) {
                        _state.update { it.copy(training = TrainingProgress(0.05 * i / refs.size, "Leyendo las grabaciones…")) }
                        if (cancelTraining.get()) throw TrainingCancelled()
                    }
                }
                val model = Trainer.train(
                    clips, st.catalog, TrainConfig(evaluate = st.evaluateFully),
                    progress = { f, m -> _state.update { it.copy(training = TrainingProgress(0.05 + 0.95 * f, m)) } },
                    shouldCancel = { cancelTraining.get() },
                )
                saveModel(model, st.catalog)
                val r = model.report!!
                val result = TrainResult(
                    r.accuracy, r.evalMode, r.nClips, r.nSigners, r.classes.size, r.perCategory, r.perSigner,
                    r.topConfusions, r.warnings, r.seconds, r.trainedAt,
                )
                writeAtomic(reportFile, result.toJson().toString().toByteArray())
                _state.update { it.copy(training = null, result = result, hasModel = true) }
                message("Modelo listo: ${(r.accuracy * 100).toInt()}% de aciertos en el examen.")
            } catch (e: TrainingCancelled) {
                _state.update { it.copy(training = null) }
                message("Entrenamiento cancelado.")
            } catch (e: Trainer.TrainingException) {
                _state.update { it.copy(training = null) }
                message(e.message ?: "No pude entrenar.")
            } catch (e: OutOfMemoryError) {
                _state.update { it.copy(training = null) }
                message("El teléfono se quedó sin memoria. Cierra otras apps e intenta de nuevo.")
            } catch (e: Exception) {
                _state.update { it.copy(training = null) }
                message("No pude entrenar: ${e.message ?: e.javaClass.simpleName}")
            }
        }
    }

    fun cancelTraining() {
        cancelTraining.set(true)
    }

    private fun saveModel(model: TrainedModel, catalog: SignCatalog) {
        modelsDir.mkdirs()
        writeAtomic(modelJson, model.toAndroidJson(catalog, ClipStore.APP_VERSION).toByteArray())
        writeAtomic(modelNpz, model.toNpz(ClipStore.APP_VERSION))
    }

    private fun writeAtomic(target: File, bytes: ByteArray) {
        target.parentFile?.mkdirs()
        val tmp = File(target.parentFile, target.name + ".tmp")
        FileOutputStream(tmp).use { it.write(bytes) }
        if (!tmp.renameTo(target)) {
            target.delete()
            tmp.renameTo(target)
        }
    }

    // ---------------- Compartir e importar ----------------

    /** Un .zip con TODAS las grabaciones (y el modelo si existe) para mandar a quien coordina o a la PC. */
    fun shareRecordings() {
        val st = _state.value
        viewModelScope.launch(Dispatchers.IO) {
            try {
                shareDir.deleteRecursively()
                val file = Packages.export(store, shareDir, st.signerName.ifBlank { "persona" },
                    modelNpz.takeIf { it.exists() }, modelJson.takeIf { it.exists() }, includeClips = true)
                _shares.tryEmit(ShareRequest(file, "application/zip", "Enviar grabaciones"))
            } catch (e: Packages.PackageException) {
                message(e.message ?: "No pude crear el archivo.")
            } catch (e: Exception) {
                message("No pude crear el archivo: ${e.message}")
            }
        }
    }

    /** El modelo en el formato de la app de traduccion. */
    fun shareModel(toTranslator: Boolean) {
        if (!modelJson.exists()) {
            message("Primero entrena un modelo.")
            return
        }
        viewModelScope.launch(Dispatchers.IO) {
            try {
                shareDir.mkdirs()
                val copy = File(shareDir, "MiraTek_modelo_celular_${stamp()}.json")
                modelJson.copyTo(copy, overwrite = true)
                _shares.tryEmit(ShareRequest(copy, "application/json", "Enviar modelo", toTranslator))
            } catch (e: Exception) {
                message("No pude preparar el modelo: ${e.message}")
            }
        }
    }

    /** Abre un archivo recibido (.zip de otra persona o de la PC). */
    fun importPackage(uri: Uri) {
        viewModelScope.launch(Dispatchers.IO) {
            val tmp = File(getApplication<Application>().cacheDir, "recibido_${stamp()}.zip")
            try {
                getApplication<Application>().contentResolver.openInputStream(uri)?.use { input ->
                    FileOutputStream(tmp).use { out ->
                        val buffer = ByteArray(64 * 1024)
                        var total = 0L
                        while (true) {
                            val n = input.read(buffer)
                            if (n < 0) break
                            total += n
                            if (total > MAX_IMPORT_BYTES) throw Packages.PackageException("El archivo es demasiado grande.")
                            out.write(buffer, 0, n)
                        }
                    }
                } ?: throw Packages.PackageException("No pude abrir el archivo.")
                val result = Packages.import(store, tmp, modelsDir)
                refreshCounts()
                val people = result.signers.size
                val text = StringBuilder()
                if (result.added > 0) {
                    text.append("Se agregaron ${result.added} grabaciones")
                    if (people > 0) text.append(" de $people persona${if (people == 1) "" else "s"}")
                    if (result.author.isNotBlank()) text.append(" (de ${result.author})")
                    text.append('.')
                } else {
                    text.append("No había grabaciones nuevas.")
                }
                if (result.skipped > 0) text.append(" ${result.skipped} ya las tenías.")
                if (result.invalid > 0) text.append(" ${result.invalid} no se pudieron leer.")
                if (result.modelJson != null || result.modelNpz != null) text.append(" También traía un modelo.")
                message(text.toString())
            } catch (e: Packages.PackageException) {
                message(e.message ?: "Ese archivo no sirve.")
            } catch (e: Exception) {
                message("No pude abrir el archivo.")
            } finally {
                tmp.delete()
            }
        }
    }

    fun deleteSigner(signerId: String) {
        viewModelScope.launch(Dispatchers.IO) {
            store.deleteSigner(signerId)
            if (signerId == _state.value.signerId) store.setSignerName(signerId, _state.value.signerName)
            refreshCounts()
            message("Grabaciones borradas.")
        }
    }

    private fun stamp() = java.text.SimpleDateFormat("yyyy-MM-dd_HHmm", java.util.Locale.US).format(java.util.Date())

    private fun message(text: String) {
        _messages.tryEmit(text)
    }

    override fun onCleared() {
        stopSession()
        cancelTraining.set(true)
        runCatching { analyzer.close() }
    }

    companion object {
        const val CLIP_SECONDS = 2.0
        const val FIRST_COUNTDOWN = 3.0
        const val BETWEEN_CLIPS = 1.4
        const val MIN_HAND_FRACTION = 0.5
        const val MAX_IMPORT_BYTES = 1024L * 1024 * 1024
    }
}
