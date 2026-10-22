package mx.miratek.senas.trainer.train

import mx.miratek.senas.core.Features
import mx.miratek.senas.data.SignCatalog
import mx.miratek.senas.data.SignMeta
import mx.miratek.senas.trainer.data.Clip
import mx.miratek.senas.trainer.data.ClipStore
import mx.miratek.senas.trainer.data.Npy
import mx.miratek.senas.trainer.data.Npz
import org.json.JSONArray
import org.json.JSONObject
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Base64
import java.util.Random
import java.util.concurrent.atomic.AtomicInteger
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt
import kotlin.math.sqrt

/** Opciones del entrenamiento (mismos valores que TrainConfig en la PC, algo mas ligeros). */
class TrainConfig(
    val windowS: Double = 2.0,
    val augCopies: Int = 8,            // variaciones por clip para el modelo final
    val evalAugCopies: Int = 4,        // menos variaciones en el examen (para que sea rapido)
    val maxEpochs: Int = 50,
    val evalMaxEpochs: Int = 30,
    val hidden: IntArray = intArrayOf(256, 128),
    val dropout: FloatArray = floatArrayOf(0.3f, 0.2f),
    val lr: Double = 1e-3,
    val weightDecay: Double = 1e-4,
    val batchSize: Int = 128,
    val smoothing: Double = 0.05,
    val patience: Int = 10,
    val valFraction: Double = 0.15,
    val testFraction: Double = 0.2,
    val maxSignerFolds: Int = 4,
    val seed: Long = 42,
    val evaluate: Boolean = true,      // examen con personas nuevas (tarda mas)
    val maxRows: Int = 40_000,         // tope de memoria: menos variaciones si hay muchos clips
    val inputNoise: Double = 0.05,     // ruido sobre las caracteristicas normalizadas al entrenar
    val transitionFraction: Double = 0.3,  // copias que empiezan con la cola de otra sena
)

class ClassStats(val recall: Double?, val precision: Double?, val support: Int)

/** Resumen del examen (mismos campos que TrainReport en la PC). */
class TrainReport(
    val classes: List<String>,
    val evalMode: String,              // "personas" o "grabaciones"
    val accuracy: Double,
    val perClass: Map<String, ClassStats>,
    val confusion: Array<IntArray>,
    val topConfusions: List<Triple<String, String, Int>>,
    val perSigner: Map<String, Double>,
    val perCategory: Map<String, Double>,
    val nClips: Int,
    val nSigners: Int,
    val clipsPerClass: Map<String, Int>,
    val trainedAt: String,
    val seconds: Double,
    val warnings: List<String>,
) {
    fun toJson(): JSONObject {
        val perClassJson = JSONObject()
        for ((c, s) in perClass) {
            perClassJson.put(c, JSONObject()
                .put("recall", s.recall ?: JSONObject.NULL)
                .put("precision", s.precision ?: JSONObject.NULL)
                .put("support", s.support))
        }
        return JSONObject()
            .put("classes", JSONArray(classes))
            .put("eval_mode", evalMode)
            .put("accuracy", accuracy)
            .put("per_class", perClassJson)
            .put("confusion", JSONArray(confusion.map { JSONArray(it.toList()) }))
            .put("top_confusions", JSONArray(topConfusions.map { JSONArray(listOf(it.first, it.second, it.third)) }))
            .put("per_signer", JSONObject(perSigner))
            .put("per_category", JSONObject(perCategory))
            .put("n_clips", nClips)
            .put("n_signers", nSigners)
            .put("clips_per_class", JSONObject(clipsPerClass))
            .put("trained_at", trainedAt)
            .put("seconds", seconds)
            .put("warnings", JSONArray(warnings))
    }
}

/** Modelo listo para usar: red + normalizacion + lista de senas. */
class TrainedModel(
    val mlp: Mlp,
    val mean: FloatArray,
    val std: FloatArray,
    val classes: List<String>,
    val temperature: Double,
    val windowS: Double,
    var report: TrainReport? = null,
) {
    private fun normalized(x: FloatArray, n: Int): FloatArray {
        val f = mean.size
        return FloatArray(n * f) { i -> (x[i] - mean[i % f]) / std[i % f] }
    }

    /** Logits (antes del softmax) de n filas de caracteristicas sin normalizar. */
    fun logits(x: FloatArray, n: Int): FloatArray = mlp.logits(normalized(x, n), n)

    fun predictBatch(x: FloatArray, n: Int): Array<DoubleArray> {
        val logits = logits(x, n)
        val c = classes.size
        return Array(n) { Loss.softmaxRow(logits, it * c, c, temperature) }
    }

    fun withTemperature(t: Double) = TrainedModel(mlp, mean, std, classes, t, windowS, report)

    fun predictProba(features: FloatArray): DoubleArray = predictBatch(features, 1)[0]

    /** El archivo que lee la app de traduccion (mismo formato que export_android.py). */
    fun toAndroidJson(meta: SignMeta, appVersion: String): String {
        val signs = JSONArray()
        for (c in classes) {
            signs.put(JSONObject().put("id", c).put("name", meta.nameOf(c)).put("category", meta.categoryOf(c))
                .put("number", meta.numberOf(c) ?: JSONObject.NULL))
        }
        val layers = JSONArray()
        for (l in 0 until mlp.layers) {
            layers.put(JSONObject().put("in", mlp.sizes[l]).put("out", mlp.sizes[l + 1])
                .put("w", b64(mlp.weights[l])).put("b", b64(mlp.biases[l])))
        }
        val r = report
        val reportJson = if (r == null) JSONObject.NULL else JSONObject()
            .put("accuracy", r.accuracy).put("eval_mode", r.evalMode).put("n_signers", r.nSigners)
            .put("n_clips", r.nClips).put("trained_at", r.trainedAt).put("per_category", JSONObject(r.perCategory))
        return JSONObject()
            .put("format", 1)
            .put("feature_version", Features.FEATURE_VERSION)
            .put("feature_size", Features.FEATURE_SIZE)
            .put("app_version", appVersion)
            .put("exported", ClipStore.isoNow())
            .put("window_s", windowS)
            .put("temperature", temperature)
            .put("signs", signs)
            .put("mean", b64(mean))
            .put("std", b64(std))
            .put("layers", layers)
            .put("report", reportJson)
            .toString()
    }

    /** El mismo modelo en el formato de la PC (modelo.npz), para seguir entrenando alla. */
    fun toNpz(appVersion: String): ByteArray {
        val meta = JSONObject()
            .put("format", 1)
            .put("feature_version", Features.FEATURE_VERSION)
            .put("app_version", appVersion)
            .put("classes", JSONArray(classes))
            .put("temperature", temperature)
            .put("window_s", windowS)
            .put("dropout", JSONArray(mlp.dropout.map { it.toDouble() }))
            .put("report", report?.toJson() ?: JSONObject.NULL)
        val arrays = linkedMapOf<String, Npy>(
            "mean" to Npy.Floats(intArrayOf(mean.size), mean),
            "std" to Npy.Floats(intArrayOf(std.size), std),
            "meta" to Npy.Text(meta.toString()),
        )
        for (l in 0 until mlp.layers) {
            arrays["w$l"] = Npy.Floats(intArrayOf(mlp.sizes[l], mlp.sizes[l + 1]), mlp.weights[l])
            arrays["b$l"] = Npy.Floats(intArrayOf(mlp.sizes[l + 1]), mlp.biases[l])
        }
        return Npz.toBytes(arrays)
    }

    private fun b64(values: FloatArray): String {
        val buf = ByteBuffer.allocate(values.size * 4).order(ByteOrder.LITTLE_ENDIAN)
        buf.asFloatBuffer().put(values)
        return Base64.getEncoder().encodeToString(buf.array())
    }
}

/**
 * Entrenamiento completo con UN solo boton, copia de miratek/training.py:
 *  1. Examen honesto: con 2 o mas personas se entrena SIN una y se le hace el
 *     examen a esa (asi medimos como le ira a alguien que el modelo nunca vio).
 *     Con 1 persona se apartan clips completos.
 *  2. Modelo final con todos los datos.
 */
object Trainer {
    const val MIN_CLIPS_PER_CLASS = 3
    const val NOTHING_ID = "nada"
    private const val F = Features.FEATURE_SIZE

    class TrainingException(message: String) : Exception(message)

    private class Fold(val signer: String?, val train: List<Clip>, val test: List<Clip>, val classes: List<String>)

    private class FeatureSet(val x: FloatArray, val y: IntArray, val n: Int)

    fun train(
        clips: List<Clip>,
        meta: SignMeta,
        cfg: TrainConfig = TrainConfig(),
        progress: (fraction: Double, message: String) -> Unit = { _, _ -> },
        shouldCancel: () -> Boolean = { false },
    ): TrainedModel {
        val started = System.currentTimeMillis()
        val rng = Random(cfg.seed)
        val warnings = ArrayList<String>()

        // ---------- 1. Clips utilizables ----------
        progress(0.0, "Leyendo las grabaciones…")
        val counts = clips.groupingBy { it.signId }.eachCount()
        val classes = counts.filter { it.value >= MIN_CLIPS_PER_CLASS }.keys.sorted()
        val excluded = counts.filter { it.value < MIN_CLIPS_PER_CLASS }.keys.sorted()
        if (classes.size < 2) {
            throw TrainingException(
                "Todavía no hay suficientes grabaciones. Graba al menos 2 señas con $MIN_CLIPS_PER_CLASS clips o más cada una."
            )
        }
        if (excluded.isNotEmpty()) {
            warnings += "No se usaron " + excluded.joinToString(", ") { meta.nameOf(it) } +
                ": necesitan al menos $MIN_CLIPS_PER_CLASS grabaciones."
        }
        if (NOTHING_ID !in classes) {
            warnings += "Graba la seña «Nada» para que el modelo sepa cuándo no estás haciendo ninguna seña."
        }
        val usable = clips.filter { it.signId in classes && it.frames >= 2 }
        val classIndex = classes.withIndex().associate { it.value to it.index }
        val signers = usable.map { it.signerId }.toSortedSet().toList()

        // ---------- 2. Examen honesto ----------
        // Cualquier persona con 2 o mas senas sirve de examen: si grabo solo una parte,
        // se le examina en lo que grabo (antes se pedia la mitad y el examen caia en silencio
        // al reparto por grabaciones, que sale inflado).
        val perSignerClasses = signers.associateWith { s -> usable.filter { it.signerId == s }.map { it.signId }.toSet() }
        val eligible = signers.filter { perSignerClasses[it]!!.size >= 2 }
            .sortedByDescending { s -> usable.count { it.signerId == s } }
        val folds = ArrayList<Fold>()
        var evalMode = "grabaciones"
        if (cfg.evaluate && eligible.size >= 2) {
            evalMode = "personas"
            for (s in eligible.take(cfg.maxSignerFolds)) {
                val train = usable.filter { it.signerId != s }
                val foldClasses = train.map { it.signId }.toSortedSet().toList()
                val test = usable.filter { it.signerId == s && it.signId in foldClasses }
                if (foldClasses.size >= 2 && test.isNotEmpty()) folds += Fold(s, train, test, foldClasses)
            }
        }
        if (folds.isEmpty()) {
            evalMode = "grabaciones"
            val labels = IntArray(usable.size) { classIndex[usable[it].signId]!! }
            val held = stratifiedSplit(labels, cfg.testFraction, rng)
            val train = usable.filterIndexed { i, _ -> !held[i] }
            val test = usable.filterIndexed { i, _ -> held[i] }
            folds += Fold(null, train, test, train.map { it.signId }.toSortedSet().toList())
            if (signers.size == 1) {
                warnings += "Solo hay grabaciones de 1 persona. Con otras personas puede fallar más: pide a más gente que grabe."
            }
        }

        val n = classes.size
        val confusion = Array(n) { IntArray(n) }
        val perSigner = LinkedHashMap<String, Double>()
        val examRows = ArrayList<Pair<FloatArray, Int>>()  // logits del examen: calibran la confianza
        val evalSpan = 0.57 / folds.size
        for ((k, fold) in folds.withIndex()) {
            val base = 0.08 + k * evalSpan
            val label = if (evalMode == "personas") "Examen con personas nuevas (${k + 1} de ${folds.size})…"
            else "Haciendo el examen…"
            val model = fit(fold.train, fold.classes, cfg, cfg.evalAugCopies, cfg.evalMaxEpochs, rng,
                { f -> progress(base + evalSpan * f, label) }, shouldCancel)
            val exam = predictClips(model, fold.test, meta)
            var hits = 0
            val foldIndex = fold.classes.withIndex().associate { it.value to it.index }
            for ((i, clip) in fold.test.withIndex()) {
                val t = classIndex[clip.signId]!!
                val p = classIndex[fold.classes[exam.predictions[i]]]!!
                confusion[t][p]++
                if (t == p) hits++
                examRows += exam.logits[i] to foldIndex[clip.signId]!!
            }
            if (fold.signer != null && fold.test.isNotEmpty()) perSigner[fold.signer] = hits.toDouble() / fold.test.size
        }

        // ---------- 3. Modelo final con todos los datos ----------
        var final = fit(usable, classes, cfg, cfg.augCopies, cfg.maxEpochs, rng,
            { f -> progress(0.65 + 0.33 * f, "Entrenando el modelo final…") }, shouldCancel)
        if (evalMode == "personas" && examRows.isNotEmpty()) {
            // La temperatura se ajusta con personas que el modelo NO vio: asi "80% seguro"
            // significa 80% tambien con gente nueva, no solo con quien grabo.
            final = final.withTemperature(Loss.fitTemperatureRows(examRows))
        }
        progress(0.99, "Guardando…")

        val total = confusion.sumOf { it.sum() }
        val perClass = LinkedHashMap<String, ClassStats>()
        for ((i, c) in classes.withIndex()) {
            val support = confusion[i].sum()
            val predicted = confusion.sumOf { it[i] }
            perClass[c] = ClassStats(
                if (support > 0) confusion[i][i].toDouble() / support else null,
                if (predicted > 0) confusion[i][i].toDouble() / predicted else null,
                support,
            )
        }
        val off = ArrayList<Triple<String, String, Int>>()
        for (i in 0 until n) for (j in 0 until n) if (i != j && confusion[i][j] > 0) off += Triple(classes[i], classes[j], confusion[i][j])
        off.sortByDescending { it.third }
        val perCategory = LinkedHashMap<String, Double>()
        for (cat in SignCatalog.CATEGORIES) {
            val rows = classes.indices.filter { meta.categoryOf(classes[it]) == cat && classes[it] != NOTHING_ID }
            val support = rows.sumOf { confusion[it].sum() }
            if (support > 0) perCategory[cat] = rows.sumOf { confusion[it][it] }.toDouble() / support
        }
        var trace = 0
        for (i in 0 until n) trace += confusion[i][i]
        final.report = TrainReport(
            classes = classes,
            evalMode = evalMode,
            accuracy = if (total > 0) trace.toDouble() / total else 0.0,
            perClass = perClass,
            confusion = confusion,
            topConfusions = off.take(3),
            perSigner = perSigner,
            perCategory = perCategory,
            nClips = usable.size,
            nSigners = signers.size,
            clipsPerClass = classes.associateWith { counts[it]!! },
            trainedAt = ClipStore.isoNow(),
            seconds = (System.currentTimeMillis() - started) / 1000.0,
            warnings = warnings,
        )
        progress(1.0, "¡Listo!")
        return final
    }

    /** Entrena un modelo con esos clips (separa una parte para validacion). */
    private fun fit(
        trainClips: List<Clip>, classes: List<String>, cfg: TrainConfig, copies: Int, epochs: Int, rng: Random,
        progress: (Double) -> Unit, shouldCancel: () -> Boolean,
    ): TrainedModel {
        val classIndex = classes.withIndex().associate { it.value to it.index }
        val labels = IntArray(trainClips.size) { classIndex[trainClips[it].signId]!! }
        val held = stratifiedSplit(labels, cfg.valFraction, rng)
        val tr = trainClips.filterIndexed { i, _ -> !held[i] }
        val va = trainClips.filterIndexed { i, _ -> held[i] }
        val effectiveCopies = min(copies, max(1, cfg.maxRows / max(1, tr.size) - 1))
        val trSet = buildSet(tr, classIndex, cfg.windowS, effectiveCopies, rng, cfg.transitionFraction) { f ->
            progress(0.4 * f)
            if (shouldCancel()) throw TrainingCancelled()
        }
        val vaSet = buildSet(va, classIndex, cfg.windowS, 2, rng) { }

        // Normalizacion: cada numero con promedio 0 y desviacion 1
        val mean = FloatArray(F)
        val std = FloatArray(F)
        if (trSet.n > 0) {
            val sum = DoubleArray(F)
            for (r in 0 until trSet.n) for (i in 0 until F) sum[i] += trSet.x[r * F + i]
            for (i in 0 until F) mean[i] = (sum[i] / trSet.n).toFloat()
            val sq = DoubleArray(F)
            for (r in 0 until trSet.n) for (i in 0 until F) {
                val d = trSet.x[r * F + i] - mean[i]
                sq[i] += d * d
            }
            val raw = DoubleArray(F) { sqrt(sq[it] / trSet.n) }
            // Piso: un numero casi constante al grabar no debe disparar la red con gente nueva
            val varying = raw.filter { it >= 1e-3 }.sorted()
            val floor = if (varying.isEmpty()) 0.0 else 0.05 * varying[varying.size / 2]
            for (i in 0 until F) std[i] = if (raw[i] < 1e-3) 1f else max(raw[i], floor).toFloat()
        } else {
            std.fill(1f)
        }
        normalize(trSet, mean, std)
        normalize(vaSet, mean, std)

        val mlp = trainMlp(
            trSet.x, trSet.y, trSet.n, vaSet.x, vaSet.y, vaSet.n, F, classes.size, cfg, epochs, rng.nextLong(),
            onEpoch = { epoch, total, _ -> progress(0.4 + 0.6 * (epoch + 1) / total) },
            shouldCancel = shouldCancel,
        )
        val temperature = if (vaSet.n > 0) {
            Loss.fitTemperature(mlp.logits(vaSet.x, vaSet.n), vaSet.n, classes.size, vaSet.y)
        } else 1.0
        return TrainedModel(mlp, mean, std, classes, temperature, cfg.windowS)
    }

    private fun normalize(set: FeatureSet, mean: FloatArray, std: FloatArray) {
        for (r in 0 until set.n) for (i in 0 until F) {
            val k = r * F + i
            set.x[k] = (set.x[k] - mean[i]) / std[i]
        }
    }

    /** Caracteristicas de cada clip y de sus variaciones (en paralelo, pero determinista). */
    private fun buildSet(
        clips: List<Clip>, classIndex: Map<String, Int>, windowS: Double, copies: Int, rng: Random,
        transitionFraction: Double = 0.0, tick: (Double) -> Unit,
    ): FeatureSet {
        val per = 1 + copies
        val n = clips.size * per
        val x = FloatArray(n * F)
        val y = IntArray(n)
        val seeds = LongArray(clips.size) { rng.nextLong() }
        val done = AtomicInteger()
        Par.forRange(clips.size) { from, to ->
            for (c in from until to) {
                val clip = clips[c]
                val label = classIndex[clip.signId]!!
                val local = Random(seeds[c])
                val base = c * per
                val f0 = Features.windowFeatures(clip.times, clip.image, clip.world, clip.aspect, windowS, mirror = clip.mirror)
                System.arraycopy(f0, 0, x, base * F, F)
                y[base] = label
                for (k in 1 until per) {
                    val a = if (clips.size > 1 && local.nextDouble() < transitionFraction) {
                        var other = local.nextInt(clips.size - 1)
                        if (other >= c) other++
                        Augment.transition(clip, clips[other], local, windowS)
                    } else {
                        Augment.clip(clip, local, windowS)
                    }
                    val f = Features.windowFeatures(a.times, a.image, a.world, clip.aspect, windowS, a.tEnd, clip.mirror)
                    System.arraycopy(f, 0, x, (base + k) * F, F)
                    y[base + k] = label
                }
                val d = done.incrementAndGet()
                if (d % 8 == 0 || d == clips.size) tick(d.toDouble() / clips.size)
            }
        }
        return FeatureSet(x, y, n)
    }

    /**
     * Predicciones del examen, igual que en la app: cada modo solo compite con su
     * categoria (una letra O nunca se confunde con el numero 0). "Nada" compite contra todo.
     */
    private class Exam(val predictions: IntArray, val logits: List<FloatArray>)

    private fun predictClips(model: TrainedModel, clips: List<Clip>, meta: SignMeta): Exam {
        if (clips.isEmpty()) return Exam(IntArray(0), emptyList())
        val x = FloatArray(clips.size * F)
        Par.forRange(clips.size) { from, to ->
            for (i in from until to) {
                val c = clips[i]
                System.arraycopy(
                    Features.windowFeatures(c.times, c.image, c.world, c.aspect, model.windowS, mirror = c.mirror),
                    0, x, i * F, F,
                )
            }
        }
        val c = model.classes.size
        val logits = model.logits(x, clips.size)
        val cats = model.classes.map { meta.categoryOf(it) }
        val isNothing = model.classes.map { it == NOTHING_ID }
        val predictions = IntArray(clips.size) { i ->
            val cat = meta.categoryOf(clips[i].signId)
            var best = -1
            for (j in 0 until c) {
                val allowed = clips[i].signId == NOTHING_ID || cats[j] == cat || isNothing[j]
                if (allowed && (best < 0 || logits[i * c + j] > logits[i * c + best])) best = j
            }
            if (best < 0) 0 else best
        }
        return Exam(predictions, List(clips.size) { logits.copyOfRange(it * c, (it + 1) * c) })
    }

    /** Aparta 'fraction' de los clips de cada sena (al menos 1 si hay 3 o mas). */
    private fun stratifiedSplit(labels: IntArray, fraction: Double, rng: Random): BooleanArray {
        val held = BooleanArray(labels.size)
        for (c in labels.toSet()) {
            val idx = labels.indices.filter { labels[it] == c }.toMutableList()
            idx.shuffle(rng)
            var k = (idx.size * fraction).roundToInt()
            k = if (idx.size >= 3) max(1, k) else 0
            k = min(k, idx.size - 1)
            for (i in 0 until k) held[idx[i]] = true
        }
        return held
    }
}
