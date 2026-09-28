package mx.miratek.senas.data

import android.content.Context
import android.speech.tts.TextToSpeech
import java.util.Locale

/** Lee la frase en voz alta con la voz del telefono (funciona sin internet). */
class Speaker(context: Context) : TextToSpeech.OnInitListener {
    private val tts = TextToSpeech(context.applicationContext, this)
    var ready = false
        private set

    override fun onInit(status: Int) {
        if (status != TextToSpeech.SUCCESS) return
        val mx = tts.setLanguage(Locale("es", "MX"))
        if (mx == TextToSpeech.LANG_MISSING_DATA || mx == TextToSpeech.LANG_NOT_SUPPORTED) {
            tts.setLanguage(Locale("es"))
        }
        ready = true
    }

    fun speak(text: String) {
        if (ready && text.isNotBlank()) tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "miratek")
    }

    fun shutdown() = tts.shutdown()
}
