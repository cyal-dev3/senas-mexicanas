package mx.miratek.senas.core

/**
 * Arma la frase con las senas reconocidas: copia de miratek/phrase.py.
 *
 *  - Palabras: cada una es un elemento nuevo.
 *  - Letras: se juntan mientras no bajes las manos (H-O-L-A -> HOLA).
 *  - Numeros (como en LSM): 20 y 3 -> 23; 100, 20 y 5 -> 125. Del 0 al 19,
 *    las decenas y el 100 tienen su propia sena.
 */
class PhraseBuilder {
    enum class Kind { WORD, SPELL, NUMBER }

    data class Item(
        var text: String,
        val kind: Kind,
        var open: Boolean = false,
        var value: Int = 0,
        var lastToken: Int = -1,
    )

    private val items = ArrayList<Item>()

    val texts: List<String> get() = items.map { it.text }
    val isEmpty get() = items.isEmpty()

    fun add(sign: SignInfo) {
        val number = sign.number
        when {
            sign.category == SignInfo.CATEGORY_NUMBERS && number != null -> addNumber(number)
            sign.isLetter -> addLetter(sign.name)
            !sign.isNothing -> {
                close()
                items += Item(sign.name, Kind.WORD)
            }
        }
    }

    /** Termina la palabra deletreada o el numero en curso. Devuelve su texto si estaba abierta. */
    fun close(): String? {
        val last = items.lastOrNull()
        if (last == null || !last.open) return null
        last.open = false
        return last.text
    }

    private fun lastOpen(kind: Kind): Item? = items.lastOrNull()?.takeIf { it.open && it.kind == kind }

    private fun addLetter(letter: String) {
        val item = lastOpen(Kind.SPELL)
        if (item != null) {
            item.text += letter
        } else {
            close()
            items += Item(letter, Kind.SPELL, open = true)
        }
    }

    private fun addNumber(v: Int) {
        val item = lastOpen(Kind.NUMBER)
        if (item != null) {
            val prev = item.lastToken
            val new = when {
                prev == 100 && v in 1..99 -> item.value + v
                prev in 20..90 && prev % 10 == 0 && v in 1..9 -> item.value + v
                else -> null
            }
            if (new != null) {
                item.value = new
                item.lastToken = v
                item.text = new.toString()
                return
            }
        }
        close()
        items += Item(v.toString(), Kind.NUMBER, open = true, value = v, lastToken = v)
    }

    fun deleteLast() {
        val item = items.lastOrNull() ?: return
        if (item.kind == Kind.SPELL && item.open && item.text.length > 1) {
            item.text = item.text.dropLast(1)
        } else {
            items.removeAt(items.size - 1)
        }
    }

    fun clear() = items.clear()

    /** Texto para leer en voz alta. */
    fun sentence(): String = texts.joinToString(" ")
}
