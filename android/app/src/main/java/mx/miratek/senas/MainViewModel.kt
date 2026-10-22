package mx.miratek.senas

import android.app.Application
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.net.Uri
import android.os.Build
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import mx.miratek.senas.camera.HandAnalyzer
import mx.miratek.senas.camera.HandsFrame
import mx.miratek.senas.core.FrameHands
import mx.miratek.senas.core.LiveRecognizer
import mx.miratek.senas.core.ModelFormatException
import mx.miratek.senas.core.PhraseBuilder
import mx.miratek.senas.core.Prediction
import mx.miratek.senas.core.Sensitivity
import mx.miratek.senas.core.SignInfo
import mx.miratek.senas.core.SignModel
import mx.miratek.senas.data.LearnRepository
import mx.miratek.senas.data.LearnSign
import mx.miratek.senas.data.ModelRepository
import mx.miratek.senas.data.Speaker

/** Los modos del traductor en orden: Palabras, Deletreo, Numeros. */
private val MODE_ORDER = listOf(SignInfo.CATEGORY_WORDS, SignInfo.CATEGORY_LETTERS, SignInfo.CATEGORY_NUMBERS)

/** Los modos que el modelo sabe reconocer (si no tiene letras, no hay "Deletreo"). */
fun modesOf(model: SignModel): List<String> =
    MODE_ORDER.filter { cat -> model.signs.any { it.category == cat && !it.isNothing } }

data class UiState(
    val loading: Boolean = true,
    val model: SignModel? = null,
    val mode: String = SignInfo.CATEGORY_WORDS,
    val prediction: Prediction? = null,
    val phrase: List<String> = emptyList(),
    val eventCount: Int = 0,
    val sensitivity: Sensitivity = Sensitivity.MEDIUM,
    val autoSpeak: Boolean = true,
    val frontCamera: Boolean = true,
    val leftHanded: Boolean = false,  // hace las senas con la mano izquierda
    val cameraError: String? = null,
    val cameraKey: Int = 0,           // cambia para volver a abrir la camara
    val hasUserModel: Boolean = false,
    val hasBundledModel: Boolean = false,
    val usingUserModel: Boolean = false,  // el modelo activo es el que la persona cargo
    // Aprender y perfil
    val learn: List<LearnSign> = emptyList(),
    val practiced: Set<String> = emptySet(),
    val profileName: String = "Usuario",
    // Practica: sena que se esta practicando (null = modo traductor)
    val practiceTarget: String? = null,
    val practiceDone: Boolean = false,
    val practiceHint: String? = null,
) {
    fun modelKnows(signId: String) = model?.signs?.any { it.id == signId } == true

    /** Los modos que el traductor puede ofrecer con el modelo actual. */
    val modes: List<String> get() = model?.let(::modesOf).orEmpty()

    /** El modo elegido; si el modelo no lo conoce, el primero que si. */
    val activeMode: String get() = mode.takeIf { it in modes } ?: modes.firstOrNull() ?: mode
}

class MainViewModel(app: Application) : AndroidViewModel(app) {
    private val prefs = app.getSharedPreferences("miratek", Context.MODE_PRIVATE)
    private val repo = ModelRepository(app)
    private val learnRepo = LearnRepository(app)
    private val speaker = Speaker(app)
    private val phrase = PhraseBuilder()
    private val lock = Any()
    private var recognizer: LiveRecognizer? = null

    private val _state = MutableStateFlow(
        UiState(
            mode = prefs.getString("mode", SignInfo.CATEGORY_WORDS)!!,
            sensitivity = runCatching { Sensitivity.valueOf(prefs.getString("sensitivity", "MEDIUM")!!) }
                .getOrDefault(Sensitivity.MEDIUM),
            autoSpeak = prefs.getBoolean("autoSpeak", true),
            frontCamera = prefs.getBoolean("frontCamera", true),
            leftHanded = prefs.getBoolean("leftHanded", false),
            practiced = prefs.getStringSet("practiced", emptySet())!!.toSet(),
            profileName = prefs.getString("profileName", "Usuario")!!,
        )
    )
    val state: StateFlow<UiState> = _state.asStateFlow()

    private val _hands = MutableStateFlow<HandsFrame?>(null)
    val hands: StateFlow<HandsFrame?> = _hands.asStateFlow()

    private val _messages = MutableSharedFlow<String>(extraBufferCapacity = 4)
    val messages: SharedFlow<String> = _messages.asSharedFlow()

    /** Crearlo es barato: MediaPipe se carga en prepare() (ver init) o con el primer frame. */
    val analyzer = HandAnalyzer(app, ::onHands, ::reportCameraError)

    init {
        viewModelScope.launch(Dispatchers.IO) {
            setModel(repo.load())
            val learn = runCatching { learnRepo.load() }.getOrDefault(emptyList())
            _state.update { it.copy(learn = learn) }
        }
        prepareDetector()
    }

    /**
     * MediaPipe tarda ~1 s en cargar: se prepara aqui, nunca en el hilo principal.
     * Si falla, solo se muestra la tarjeta de la camara para intentar de nuevo.
     */
    private fun prepareDetector(retry: Boolean = false) {
        viewModelScope.launch(Dispatchers.IO) {
            val ready = runCatching { analyzer.prepare(retry) }.getOrDefault(false)
            if (!ready) reportCameraError(HandAnalyzer.DETECTOR_UNAVAILABLE)
        }
    }

    private fun setModel(model: SignModel?) {
        val current = _state.value
        synchronized(lock) {
            recognizer = model?.let {
                LiveRecognizer(it, sensitivity = current.sensitivity, mirror = current.leftHanded).apply {
                    setAllowedCategory(allowedFor(current.mode, it))
                }
            }
            phrase.clear()
        }
        _state.update {
            it.copy(loading = false, model = model, phrase = emptyList(), prediction = null,
                hasUserModel = repo.hasUserModel, hasBundledModel = repo.hasBundledModel,
                usingUserModel = model != null && repo.usingUserModel)
        }
    }

    /** La categoria que compite en el modo elegido (o la primera que el modelo conoce). */
    private fun allowedFor(mode: String, model: SignModel): String? {
        val modes = modesOf(model)
        return mode.takeIf { it in modes } ?: modes.firstOrNull()
    }

    private fun onHands(hands: FrameHands, t: Double, width: Int, height: Int) {
        _hands.value = HandsFrame(hands, width, height)
        val rec = recognizer ?: return
        synchronized(lock) {
            rec.aspect = width.toDouble() / height
            val (prediction, event) = rec.push(t, hands.image, hands.world, hands.any)
            if (prediction == null && event == null) return
            val target = _state.value.practiceTarget
            if (target != null) {
                onPracticeEvent(target, prediction, event?.sign)
                return
            }
            val speak = _state.value.autoSpeak
            // La palabra deletreada se cierra cuando ya lleva un rato sin sena
            // (no con una sola prediccion de "Nada" ni con un frame sin manos)
            if (prediction?.wordBreak == true) {
                phrase.close()?.let { finished -> if (speak) speaker.speak(finished) }
            }
            if (event != null) {
                phrase.add(event.sign)
                if (speak && event.sign.category == SignInfo.CATEGORY_WORDS) speaker.speak(event.sign.name)
            }
            _state.update {
                it.copy(
                    prediction = prediction ?: it.prediction,
                    phrase = phrase.texts,
                    eventCount = if (event != null) it.eventCount + 1 else it.eventCount,
                    cameraError = null,
                )
            }
        }
    }

    /** En modo practica: la sena correcta cuenta como aprendida; otra da una pista. */
    private fun onPracticeEvent(target: String, prediction: Prediction?, sign: SignInfo?) {
        var done = false
        var hint: String? = null
        if (sign != null) {
            if (sign.id == target) done = true else hint = "Parece «${sign.name}». Intenta otra vez."
        }
        if (done) {
            val practiced = _state.value.practiced + target
            prefs.edit().putStringSet("practiced", practiced).apply()
            _state.update { it.copy(practiced = practiced) }
        }
        _state.update {
            it.copy(
                prediction = prediction ?: it.prediction,
                practiceDone = it.practiceDone || done,
                practiceHint = if (done) null else hint ?: it.practiceHint,
                eventCount = if (sign != null) it.eventCount + 1 else it.eventCount,
                cameraError = null,
            )
        }
    }

    // ---------------- Practica ----------------

    fun startPractice(signId: String) {
        val category = _state.value.learn.firstOrNull { it.id == signId }?.category
        synchronized(lock) {
            recognizer?.reset()
            recognizer?.setAllowedCategory(category)
        }
        _state.update { it.copy(practiceTarget = signId, practiceDone = false, practiceHint = null, prediction = null) }
    }

    fun stopPractice() {
        synchronized(lock) {
            recognizer?.reset()
            val model = _state.value.model
            if (model != null) recognizer?.setAllowedCategory(allowedFor(_state.value.mode, model))
        }
        _state.update { it.copy(practiceTarget = null, practiceDone = false, practiceHint = null, prediction = null) }
    }

    fun setProfileName(name: String) {
        val clean = name.trim().take(30).ifBlank { "Usuario" }
        prefs.edit().putString("profileName", clean).apply()
        _state.update { it.copy(profileName = clean) }
    }

    // ---------------- Acciones de la pantalla ----------------

    fun setMode(mode: String) {
        prefs.edit().putString("mode", mode).apply()
        synchronized(lock) {
            phrase.close()
            val model = _state.value.model
            if (model != null) recognizer?.setAllowedCategory(allowedFor(mode, model))
        }
        _state.update { it.copy(mode = mode, prediction = null) }
    }

    fun setSensitivity(s: Sensitivity) {
        prefs.edit().putString("sensitivity", s.name).apply()
        synchronized(lock) { recognizer?.setSensitivity(s) }
        _state.update { it.copy(sensitivity = s) }
    }

    fun setAutoSpeak(on: Boolean) {
        prefs.edit().putBoolean("autoSpeak", on).apply()
        _state.update { it.copy(autoSpeak = on) }
    }

    /** Con la mano izquierda las senas se reflejan como espejo antes de reconocerlas. */
    fun setLeftHanded(on: Boolean) {
        prefs.edit().putBoolean("leftHanded", on).apply()
        synchronized(lock) {
            recognizer?.mirror = on
            recognizer?.reset()
        }
        _state.update { it.copy(leftHanded = on, prediction = null) }
    }

    fun setFrontCamera(front: Boolean) {
        prefs.edit().putBoolean("frontCamera", front).apply()
        synchronized(lock) { recognizer?.reset() }
        forgetHands()
        _state.update { it.copy(frontCamera = front) }
    }

    fun reportCameraError(message: String) {
        _state.update { it.copy(cameraError = message) }
    }

    fun retryCamera() {
        synchronized(lock) { recognizer?.reset() }
        forgetHands()
        _state.update { it.copy(cameraError = null, cameraKey = it.cameraKey + 1, prediction = null) }
        prepareDetector(retry = true)  // si el detector de manos no habia cargado, se intenta otra vez
    }

    /** La camara se cerro (otra pantalla u otra camara): que no quede dibujada una mano vieja. */
    fun onCameraClosed() {
        synchronized(lock) { recognizer?.reset() }
        forgetHands()
        _state.update { it.copy(prediction = null) }
    }

    private fun forgetHands() {
        _hands.value = null
        analyzer.resetTracking()
    }

    fun speakPhrase() {
        val text = phraseText("Todavía no hay nada que leer.") ?: return
        speaker.speak(text)
    }

    /** El texto de la frase, o null (con un aviso) si todavia no hay nada. */
    fun phraseText(emptyMessage: String = "Todavía no hay una frase."): String? {
        val text = synchronized(lock) { phrase.sentence() }
        if (text.isBlank()) message(emptyMessage)
        return text.takeIf { it.isNotBlank() }
    }

    fun copyPhrase() {
        val text = phraseText("Todavía no hay nada que copiar.") ?: return
        val clipboard = getApplication<Application>().getSystemService(ClipboardManager::class.java) ?: return
        clipboard.setPrimaryClip(ClipData.newPlainText("Frase", text))
        // Desde Android 13 el telefono ya avisa que se copio
        if (Build.VERSION.SDK_INT < 33) message("Frase copiada.")
    }

    fun deleteLast() {
        synchronized(lock) { phrase.deleteLast() }
        _state.update { it.copy(phrase = synchronized(lock) { phrase.texts }) }
    }

    fun clearPhrase() {
        synchronized(lock) { phrase.clear() }
        _state.update { it.copy(phrase = emptyList()) }
    }

    fun importModel(uri: Uri) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val model = repo.import(uri)
                setModel(model)
                message("Modelo cargado: ${model.signs.count { !it.isNothing }} señas.")
            } catch (e: ModelFormatException) {
                message(e.message ?: "Ese archivo no sirve.")
            } catch (e: Exception) {
                message("No pude cargar el archivo.")
            } catch (e: OutOfMemoryError) {
                message("El archivo es demasiado grande para este teléfono.")
            }
        }
    }

    fun useBundledModel() {
        viewModelScope.launch(Dispatchers.IO) {
            repo.useBundled()
            setModel(repo.load())
            message("Ahora usas el modelo incluido en la app.")
        }
    }

    private fun message(text: String) {
        _messages.tryEmit(text)
    }

    override fun onCleared() {
        analyzer.close()  // si MediaPipe nunca cargo, no hay nada que cerrar
        speaker.shutdown()
    }
}
