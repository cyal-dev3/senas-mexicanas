package mx.miratek.senas.trainer

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.lifecycleScope
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.launch
import mx.miratek.senas.trainer.ui.HomeScreen
import mx.miratek.senas.trainer.ui.LoadingScreen
import mx.miratek.senas.trainer.ui.RecordScreen
import mx.miratek.senas.trainer.ui.SetupScreen
import mx.miratek.senas.trainer.ui.ShareScreen
import mx.miratek.senas.trainer.ui.TrainScreen
import mx.miratek.senas.trainer.ui.TrainerNav
import mx.miratek.senas.trainer.ui.TrainerTab
import mx.miratek.senas.trainer.ui.TrainerWelcome
import mx.miratek.senas.ui.Logo
import mx.miratek.senas.ui.Mira
import mx.miratek.senas.ui.MiraTekTheme

class TrainerActivity : ComponentActivity() {
    private val vm: TrainerViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge(
            navigationBarStyle = SystemBarStyle.light(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT),
        )
        if (savedInstanceState == null) handleIntent(intent)
        lifecycleScope.launch {
            repeatOnLifecycle(Lifecycle.State.STARTED) { vm.shares.collect { share(it) } }
        }
        setContent { MiraTekTheme { TrainerApp(vm) } }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIntent(intent)
    }

    /** Si abren un .zip de grabaciones desde WhatsApp o Archivos, lo juntamos con las nuestras. */
    private fun handleIntent(intent: Intent?) {
        val uri: Uri? = when (intent?.action) {
            Intent.ACTION_VIEW -> intent.data
            Intent.ACTION_SEND -> if (Build.VERSION.SDK_INT >= 33) {
                intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
            } else {
                @Suppress("DEPRECATION") intent.getParcelableExtra(Intent.EXTRA_STREAM)
            }
            else -> null
        }
        if (uri != null) vm.importPackage(uri)
    }

    private fun share(request: ShareRequest) {
        val uri = FileProvider.getUriForFile(this, "$packageName.files", request.file)
        if (request.toTranslator) {
            // Directo a la app de traduccion si esta instalada
            val view = Intent(Intent.ACTION_VIEW)
                .setDataAndType(uri, request.mime)
                .setPackage(TRANSLATOR_PACKAGE)
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            if (view.resolveActivity(packageManager) != null) {
                startActivity(view)
                return
            }
        }
        val send = Intent(Intent.ACTION_SEND)
            .setType(request.mime)
            .putExtra(Intent.EXTRA_STREAM, uri)
            .putExtra(Intent.EXTRA_SUBJECT, request.title)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        startActivity(Intent.createChooser(send, request.title))
    }

    companion object {
        const val TRANSLATOR_PACKAGE = "mx.miratek.senas"
    }
}

@Composable
private fun TrainerApp(vm: TrainerViewModel) {
    val context = LocalContext.current
    var granted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        )
    }
    var denied by rememberSaveable { mutableStateOf(false) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        granted = ok
        denied = !ok
    }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) vm.importPackage(uri)
    }
    val openPicker = { picker.launch(arrayOf("application/zip", "application/octet-stream", "application/x-zip-compressed")) }

    val state by vm.state.collectAsStateWithLifecycle()
    var tab by rememberSaveable { mutableStateOf(TrainerTab.RECORD) }
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(Unit) { vm.messages.collect { snackbar.showSnackbar(it) } }

    Box(Modifier.fillMaxSize()) {
        val session = state.session
        when {
            state.loading -> LoadingScreen()
            !granted -> TrainerWelcome(
                denied = denied,
                onRequest = { permission.launch(Manifest.permission.CAMERA) },
                onOpenSettings = {
                    context.startActivity(
                        Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.fromParts("package", context.packageName, null))
                    )
                },
            )
            !state.setupDone -> SetupScreen(onDone = vm::createSigner)
            session != null -> {
                RecordScreen(vm, state, session)
                BackHandler { vm.stopSession() }
            }
            else -> {
                Column(Modifier.fillMaxSize()) {
                    Box(Modifier.weight(1f)) {
                        when (tab) {
                            TrainerTab.RECORD -> HomeScreen(state, vm)
                            TrainerTab.TRAIN -> TrainScreen(state, vm)
                            TrainerTab.SHARE -> ShareScreen(state, vm, onPickFile = openPicker)
                        }
                    }
                    TrainerNav(tab) { tab = it }
                }
                BackHandler(enabled = tab != TrainerTab.RECORD) { tab = TrainerTab.RECORD }
            }
        }
        SnackbarHost(snackbar, Modifier.align(Alignment.TopCenter).padding(top = 90.dp)) { data ->
            Snackbar(containerColor = Mira.Ink, contentColor = Color.White) { Text(data.visuals.message) }
        }
    }
}
