package mx.miratek.senas.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.unit.dp

/** Bienvenida: explica la app y pide permiso para usar la camara. */
@Composable
fun PermissionScreen(denied: Boolean, onRequest: () -> Unit, onOpenSettings: () -> Unit) {
    StatusBarIcons(light = false)
    Box(
        Modifier.fillMaxSize().background(
            Brush.verticalGradient(listOf(Mira.Accent2.copy(alpha = 0.28f), Mira.Bg, Mira.Warm.copy(alpha = 0.16f)))
        ),
        contentAlignment = Alignment.Center,
    ) {
        // Con scroll: en pantallas chicas el boton nunca queda fuera de la vista
        Column(
            Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).statusBarsPadding().navigationBarsPadding()
                .padding(28.dp),
        ) {
            Logo(104.dp)
            VSpace(28.dp)
            Text("Mira&Tek", style = MaterialTheme.typography.displayLarge, color = Mira.Text)
            VSpace(8.dp)
            Text(
                "Traduce Lengua de Señas Mexicana con la cámara de tu celular.",
                style = MaterialTheme.typography.bodyLarge, color = Mira.Text2,
            )
            VSpace(36.dp)
            FeatureRow(MiraIcons.Hand, "Palabras, abecedario y números", "Arma frases y deletrea palabras.", Mira.Warm2)
            VSpace(16.dp)
            FeatureRow(MiraIcons.WifiOff, "Funciona sin internet", "Todo se procesa en el teléfono.")
            VSpace(16.dp)
            FeatureRow(MiraIcons.Lock, "Privada", "La cámara nunca sale del teléfono.", Mira.AccentDeep)
            VSpace(44.dp)
            PrimaryButton("Permitir cámara", onRequest, Modifier.fillMaxWidth())
            if (denied) {
                VSpace(10.dp)
                Text(
                    "Sin la cámara la app no puede ver tus manos.",
                    color = Mira.Amber, style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.align(Alignment.CenterHorizontally),
                )
                TextButton(onClick = onOpenSettings, modifier = Modifier.align(Alignment.CenterHorizontally)) {
                    Text("Abrir ajustes del teléfono", color = Mira.Text2)
                }
            }
        }
    }
}
