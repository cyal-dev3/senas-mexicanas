package mx.miratek.senas.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Las 4 secciones de la app (como en el diseno original del equipo). */
enum class Tab(val label: String, val icon: ImageVector) {
    TRANSLATE("Traductor", MiraIcons.Translate),
    LEARN("Aprender", MiraIcons.School),
    PROFILE("Perfil", MiraIcons.Person),
    SETTINGS("Ajustes", MiraIcons.Tune),
}

@Composable
fun BottomNav(selected: Tab, onSelect: (Tab) -> Unit) {
    Surface(color = Mira.Surface, shadowElevation = 14.dp) {
        Row(
            Modifier.fillMaxWidth().navigationBarsPadding().height(66.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            for (tab in Tab.entries) NavItem(tab, tab == selected) { onSelect(tab) }
        }
    }
}

@Composable
private fun RowScope.NavItem(tab: Tab, selected: Boolean, onClick: () -> Unit) {
    val tint by animateColorAsState(if (selected) Mira.AccentDeep else Mira.Text3, label = "nav")
    val pill by animateColorAsState(if (selected) Mira.Accent2.copy(alpha = 0.18f) else Color.Transparent, label = "pill")
    Column(
        Modifier.weight(1f).fillMaxHeight().clickable(onClickLabel = tab.label, onClick = onClick),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(Modifier.clip(RoundedCornerShape(14.dp)).background(pill).padding(horizontal = 18.dp, vertical = 5.dp)) {
            Icon(tab.icon, contentDescription = tab.label, tint = tint, modifier = Modifier.size(24.dp))
        }
        AnimatedVisibility(selected) {
            Text(tab.label, color = Mira.AccentDeep, fontSize = 12.sp, fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(top = 2.dp))
        }
    }
}
