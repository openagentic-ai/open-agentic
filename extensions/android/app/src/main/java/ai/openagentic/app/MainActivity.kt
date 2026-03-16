package ai.openagentic.app

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import ai.openagentic.app.ui.ChatScreen

class MainActivity : ComponentActivity() {

    override fun attachBaseContext(newBase: Context) {
        super.attachBaseContext(LocaleHelper.applyLocale(newBase))
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        setContent {
            MaterialTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
                    val viewModel: ChatViewModel = viewModel()
                    val uiState by viewModel.uiState.collectAsState()

                    ChatScreen(
                        uiState = uiState,
                        onSendMessage = { viewModel.sendMessage(it) },
                        onUpdateSettings = { url, user, pass ->
                            viewModel.updateSettings(url, user, pass)
                        },
                        onConnect = { viewModel.connect() },
                        onDismissError = { viewModel.dismissError() },
                        onLanguageChange = { lang ->
                            viewModel.setLanguage(lang)
                            recreate()
                        },
                        currentLanguage = viewModel.currentLanguage,
                    )
                }
            }
        }
    }
}
