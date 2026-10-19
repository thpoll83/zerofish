package com.chesscoach.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.lifecycle.viewmodel.compose.viewModel
import com.chesscoach.app.ui.ChessCoachApp
import com.chesscoach.app.ui.ChessCoachTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // Edge to edge on every Android version (Android 15 enforces it anyway), with light
        // icons in both bars: the header behind the status bar is black, the body dark.
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
        )
        super.onCreate(savedInstanceState)
        setContent {
            ChessCoachTheme {
                val vm: GameViewModel = viewModel()
                ChessCoachApp(vm)
            }
        }
    }
}
