package com.chesscoach.app.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.chesscoach.app.R

/**
 * One dark look on every phone. The header is part of the screen, not the system title bar, so
 * it looks the same everywhere; it pads itself by the status-bar inset because the app draws
 * edge to edge.
 */
object Palette {
    val header = Color(0xFF000000)
    val headerSub = Color(0xFFCBD5E1)
    val bg = Color(0xFF0B1220)
    val card = Color(0xFF16213A)
    val cardLine = Color(0xFF24324F)
    val text = Color(0xFFF1F5F9)
    val textDim = Color(0xFFA5B4CC)
    val accent = Color(0xFF4ADE80)
    val accentText = Color(0xFF86EFAC)
    val onAccent = Color(0xFF052E16)
    val control = Color(0xFF94A3B8)
    val disabledText = Color(0xFF64748B)
    val error = Color(0xFFF87171)
}

private val scheme = darkColorScheme(
    primary = Palette.accent,
    onPrimary = Palette.onAccent,
    primaryContainer = Palette.card,
    onPrimaryContainer = Palette.accentText,
    secondary = Palette.accentText,
    onSecondary = Palette.onAccent,
    secondaryContainer = Palette.card,
    onSecondaryContainer = Palette.accentText,
    background = Palette.bg,
    onBackground = Palette.text,
    surface = Palette.bg,
    onSurface = Palette.text,
    surfaceVariant = Palette.card,
    onSurfaceVariant = Palette.textDim,
    surfaceContainer = Palette.card,
    surfaceContainerHigh = Palette.card,
    surfaceContainerHighest = Palette.card,
    outline = Palette.cardLine,
    outlineVariant = Palette.cardLine,
    error = Palette.error,
    onError = Palette.onAccent,
)

@Composable
fun ChessCoachTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = scheme) {
        Surface(color = Palette.bg, contentColor = Palette.text, content = content)
    }
}

/** The black headline: logo, app name and a one-line state such as "Your move". */
@Composable
fun AppHeader(subtitle: String) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.fillMaxWidth().background(Palette.header).statusBarsPadding().padding(horizontal = 20.dp, vertical = 14.dp),
    ) {
        Image(painterResource(R.drawable.ic_logo), contentDescription = null, modifier = Modifier.size(40.dp))
        Spacer(Modifier.width(14.dp))
        Column(Modifier.fillMaxWidth()) {
            Text("Chess Coach", color = Color.White, fontSize = 22.sp, fontWeight = FontWeight.Bold)
            Text(subtitle, color = Palette.headerSub, fontSize = 14.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
    }
}
