package mx.miratek.senas

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Snackbar
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LifecycleResumeEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import mx.miratek.senas.ui.BottomNav
import mx.miratek.senas.ui.LearnScreen
import mx.miratek.senas.ui.Mira
import mx.miratek.senas.ui.MiraTekTheme
import mx.miratek.senas.ui.PermissionScreen
import mx.miratek.senas.ui.PracticeScreen
import mx.miratek.senas.ui.ProfileScreen
import mx.miratek.senas.ui.SettingsScreen
import mx.miratek.senas.ui.SignDetailScreen
import mx.miratek.senas.ui.Tab
import mx.miratek.senas.ui.TranslatorScreen
import mx.miratek.senas.ui.learnList

class MainActivity : ComponentActivity() {
    private val vm: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(
            navigationBarStyle = SystemBarStyle.light(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT),
        )
        if (savedInstanceState == null) handleIntent(intent)
        setContent { MiraTekTheme { App(vm) } }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIntent(intent)
    }

    /** Si abren un archivo de modelo desde WhatsApp o Archivos, lo cargamos (una sola vez). */
    private fun handleIntent(intent: Intent?) {
        if (intent == null) return
        // Desde "Recientes" Android repite el intent con el que se abrio: ese archivo ya se cargo
        if ((intent.flags and Intent.FLAG_ACTIVITY_LAUNCHED_FROM_HISTORY) != 0) return
        val uri: Uri? = when (intent.action) {
            Intent.ACTION_VIEW -> intent.data
            Intent.ACTION_SEND -> if (android.os.Build.VERSION.SDK_INT >= 33) {
                intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
            } else {
                @Suppress("DEPRECATION") intent.getParcelableExtra(Intent.EXTRA_STREAM)
            }
            else -> null
        }
        if (uri != null) {
            vm.importModel(uri)
            setIntent(Intent(this, MainActivity::class.java).setAction(Intent.ACTION_MAIN))  // ya se uso
        }
    }
}

private fun hasCameraPermission(context: Context) =
    ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED

@Composable
private fun App(vm: MainViewModel) {
    val context = LocalContext.current
    var granted by remember { mutableStateOf(hasCameraPermission(context)) }
    // Si dan el permiso en los ajustes del telefono y regresan, se nota al volver
    LifecycleResumeEffect(Unit) {
        granted = hasCameraPermission(context)
        onPauseOrDispose { }
    }
    var denied by rememberSaveable { mutableStateOf(false) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        granted = ok
        denied = !ok
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) vm.importModel(uri)
    }
    val openPicker = { picker.launch(arrayOf("application/json", "application/zip", "application/octet-stream", "text/plain")) }

    val state by vm.state.collectAsStateWithLifecycle()
    var tab by rememberSaveable { mutableStateOf(Tab.TRANSLATE) }
    var detail by rememberSaveable { mutableStateOf<String?>(null) }   // sena abierta en "Aprender"
    val practicing = state.practiceTarget
    val snackbar = remember { SnackbarHostState() }
    // Cada pestana recuerda su scroll y lo que tenia elegido al ir y volver
    val saved = rememberSaveableStateHolder()
    LaunchedEffect(Unit) { vm.messages.collect { snackbar.showSnackbar(it) } }

    fun selectTab(new: Tab) {
        if (practicing != null) vm.stopPractice()
        tab = new
    }

    Box(Modifier.fillMaxSize()) {
        if (!granted) {
            PermissionScreen(
                denied = denied,
                onRequest = { permission.launch(Manifest.permission.CAMERA) },
                onOpenSettings = {
                    context.startActivity(
                        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", context.packageName, null))
                    )
                },
            )
        } else {
            Column(Modifier.fillMaxSize()) {
                Box(Modifier.weight(1f)) {
                    saved.SaveableStateProvider(tab.name) {
                        when (tab) {
                            Tab.TRANSLATE -> TranslatorScreen(vm, onLoadModel = openPicker)
                            Tab.LEARN -> when {
                                practicing != null -> PracticeScreen(
                                    vm, state, practicing,
                                    onExit = { vm.stopPractice() },
                                    onNext = nextSign(state, practicing)?.let { next -> { detail = next; vm.startPractice(next) } },
                                )
                                detail != null -> SignDetailScreen(
                                    state, detail!!, onBack = { detail = null },
                                    onPractice = { vm.startPractice(it) }, onOpen = { detail = it },
                                )
                                // La lista conserva la categoria y el scroll al abrir una sena y volver
                                else -> saved.SaveableStateProvider("learn-list") {
                                    LearnScreen(state, onOpen = { detail = it })
                                }
                            }
                            Tab.PROFILE -> ProfileScreen(state, onRename = vm::setProfileName)
                            Tab.SETTINGS -> SettingsScreen(vm, onBack = null, onLoadModel = openPicker)
                        }
                    }
                }
                if (practicing == null) BottomNav(tab, ::selectTab)
            }
            // En el Traductor (aunque haya una sena abierta en Aprender) Atras cierra la app
            BackHandler(enabled = practicing != null || tab != Tab.TRANSLATE) {
                when {
                    practicing != null -> vm.stopPractice()
                    tab == Tab.LEARN && detail != null -> detail = null
                    else -> selectTab(Tab.TRANSLATE)
                }
            }
        }
        SnackbarHost(snackbar, Modifier.align(Alignment.TopCenter).padding(top = 90.dp)) { data ->
            Snackbar(containerColor = Mira.Ink, contentColor = androidx.compose.ui.graphics.Color.White) {
                Text(data.visuals.message)
            }
        }
    }
}

/** La siguiente sena de la misma categoria que el modelo conoce (para practicar en serie). */
private fun nextSign(state: UiState, current: String): String? {
    val sign = state.learn.firstOrNull { it.id == current } ?: return null
    val list = state.learnList(sign.category).filter { state.modelKnows(it.id) }
    val index = list.indexOfFirst { it.id == current }
    return list.getOrNull(index + 1)?.id
}
