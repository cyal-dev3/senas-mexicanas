package mx.miratek.senas.data

import mx.miratek.senas.core.SignInfo
import org.json.JSONObject

/** Lo minimo que hay que saber de una sena para exportar un modelo. */
interface SignMeta {
    fun categoryOf(id: String): String
    fun nameOf(id: String): String
    fun numberOf(id: String): Int?
}

/** Una sena del catalogo (assets/senas_info.json, compartido con la PC). */
class SignSpec(val id: String, val name: String, val category: String, val text: String, val source: String) {
    val isNothing get() = id == SignInfo.NOTHING_ID
    val number: Int? get() = if (category == SignInfo.CATEGORY_NUMBERS) name.toIntOrNull() else null

    /** Como grabarla (mismos textos que config.py en la PC). */
    val hint: String
        get() = when {
            isNothing -> text
            category == SignInfo.CATEGORY_LETTERS -> SignCatalog.LETTER_HINT
            category == SignInfo.CATEGORY_NUMBERS -> SignCatalog.NUMBER_HINT
            else -> SignCatalog.WORD_HINT
        }
}

/**
 * Las senas que reconoce el proyecto, en el mismo orden que config.SIGNS en la PC
 * (palabras, abecedario, numeros y al final "nada").
 */
class SignCatalog(val signs: List<SignSpec>) : SignMeta {
    private val byId = signs.associateBy { it.id }

    operator fun get(id: String): SignSpec? = byId[id]

    override fun categoryOf(id: String): String = byId[id]?.category ?: SignInfo.CATEGORY_WORDS

    override fun nameOf(id: String): String =
        byId[id]?.name ?: id.replace('_', ' ').replaceFirstChar { it.uppercase() }

    override fun numberOf(id: String): Int? = byId[id]?.number

    /** Senas de una categoria. "Nada" aparece en todas porque sirve para todas. */
    fun inCategory(category: String): List<SignSpec> =
        signs.filter { it.category == category && !it.isNothing } + listOfNotNull(byId[SignInfo.NOTHING_ID])

    companion object {
        const val WORD_HINT = "Haz la seña una sola vez, completa, y regresa las manos a reposo."
        const val LETTER_HINT = "Forma la letra y mantenla quieta hasta que se llene la barra. " +
            "Si la letra lleva movimiento, hazlo una vez."
        const val NUMBER_HINT = "Haz el número y mantenlo quieto hasta que se llene la barra. " +
            "Si lleva movimiento, hazlo una vez."
        val CATEGORIES = listOf(SignInfo.CATEGORY_WORDS, SignInfo.CATEGORY_LETTERS, SignInfo.CATEGORY_NUMBERS)
        val CATEGORY_NAMES = mapOf(
            SignInfo.CATEGORY_WORDS to "Palabras",
            SignInfo.CATEGORY_LETTERS to "Abecedario",
            SignInfo.CATEGORY_NUMBERS to "Números",
        )

        private val WORD_ORDER = listOf(
            "hola", "gracias", "por_favor", "si", "no", "ayuda", "agua", "comida", "bano", "doctor",
            "familia", "amigo", "disculpa", "te_quiero",
        )
        private val LETTER_ORDER = "ABCDEFGHIJKLMNÑOPQRSTUVWXYZ".map { if (it == 'Ñ') "letra_enie" else "letra_${it.lowercaseChar()}" }
        private val NUMBER_ORDER = ((0..19) + (20..90 step 10) + 100).map { "num_$it" }
        private val ORDER = (WORD_ORDER + LETTER_ORDER + NUMBER_ORDER + SignInfo.NOTHING_ID).withIndex()
            .associate { it.value to it.index }

        /** Lee senas_info.json. El orden es el de la PC aunque el JSON venga desordenado. */
        fun parse(infoJson: String): SignCatalog {
            val root = JSONObject(infoJson)
            val signs = root.getJSONObject("signs")
            val list = signs.keys().asSequence().map { id ->
                val s = signs.getJSONObject(id)
                SignSpec(
                    id = id,
                    name = s.optString("name", id),
                    category = s.optString("category", SignInfo.CATEGORY_WORDS),
                    text = s.optString("text"),
                    source = s.optString("source", "pendiente"),
                )
            }.toList()
            return SignCatalog(list.sortedBy { ORDER[it.id] ?: (ORDER.size + list.indexOf(it)) })
        }
    }
}
