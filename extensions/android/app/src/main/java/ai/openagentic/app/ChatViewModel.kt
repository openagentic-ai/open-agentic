package ai.openagentic.app

import android.app.Application
import android.content.SharedPreferences
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import ai.openagentic.app.api.ApiClient
import ai.openagentic.app.api.OllamaChatRequest
import ai.openagentic.app.api.OllamaChatMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ChatMessage(
    val content: String,
    val isUser: Boolean,
    val isStreaming: Boolean = false,
)

data class ChatUiState(
    val messages: List<ChatMessage> = emptyList(),
    val isLoading: Boolean = false,
    val isConnected: Boolean = false,
    val errorMessage: String? = null,
    val gatewayUrl: String = "",
    val username: String = "",
    val password: String = "",
    val token: String? = null,
)

class ChatViewModel(application: Application) : AndroidViewModel(application) {

    private val _uiState = MutableStateFlow(ChatUiState())
    val uiState: StateFlow<ChatUiState> = _uiState.asStateFlow()

    private var apiClient: ApiClient? = null
    private val prefs: SharedPreferences =
        application.getSharedPreferences("openagentic", Application.MODE_PRIVATE)

    private val model: String
        get() = prefs.getString("model", "qwen3:14b") ?: "qwen3:14b"

    // Keep conversation history for context
    private val conversationHistory = mutableListOf<OllamaChatMessage>()

    val currentLanguage: String
        get() = LocaleHelper.getSavedLanguage(getApplication())

    private fun str(resId: Int): String = getApplication<Application>().getString(resId)
    private fun str(resId: Int, vararg args: Any): String = getApplication<Application>().getString(resId, *args)

    fun setLanguage(language: String) {
        LocaleHelper.saveLanguage(getApplication(), language)
    }

    init {
        _uiState.value = _uiState.value.copy(
            gatewayUrl = prefs.getString("gateway_url", "http://192.168.0.15:11434") ?: "",
            username = prefs.getString("username", "") ?: "",
            password = prefs.getString("password", "") ?: "",
        )
        if (_uiState.value.gatewayUrl.isNotEmpty()) {
            connect()
        }
    }

    fun updateSettings(gatewayUrl: String, username: String, password: String) {
        _uiState.value = _uiState.value.copy(
            gatewayUrl = gatewayUrl,
            username = username,
            password = password,
        )
        prefs.edit()
            .putString("gateway_url", gatewayUrl)
            .putString("username", username)
            .putString("password", password)
            .apply()
    }

    fun connect() {
        val url = _uiState.value.gatewayUrl
        if (url.isBlank()) {
            _uiState.value = _uiState.value.copy(errorMessage = str(R.string.error_configure_url))
            return
        }

        apiClient = ApiClient(url)
        _uiState.value = _uiState.value.copy(isLoading = true, errorMessage = null)

        viewModelScope.launch {
            try {
                // Check Ollama is reachable by listing models
                apiClient!!.api.ollamaHealth()
                _uiState.value = _uiState.value.copy(
                    isConnected = true,
                    isLoading = false,
                    token = "ollama", // placeholder, Ollama doesn't need auth
                    errorMessage = null,
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(
                    isConnected = false,
                    isLoading = false,
                    errorMessage = str(R.string.error_connection_failed, e.message ?: ""),
                )
            }
        }
    }

    fun sendMessage(text: String) {
        if (text.isBlank()) return

        val client = apiClient ?: return

        // Add user message to history
        conversationHistory.add(OllamaChatMessage(role = "user", content = text))

        val userMsg = ChatMessage(content = text, isUser = true)
        _uiState.value = _uiState.value.copy(
            messages = _uiState.value.messages + userMsg,
            isLoading = true,
        )

        viewModelScope.launch {
            try {
                val request = OllamaChatRequest(
                    model = model,
                    messages = conversationHistory.toList(),
                    stream = false,
                )
                val response = client.api.ollamaChat(request)

                val content = response.message?.content
                    ?: response.error
                    ?: str(R.string.error_no_response)

                // Add assistant reply to history
                conversationHistory.add(OllamaChatMessage(role = "assistant", content = content))

                val aiMsg = ChatMessage(content = content, isUser = false)
                _uiState.value = _uiState.value.copy(
                    messages = _uiState.value.messages + aiMsg,
                )
            } catch (e: Exception) {
                val errMsg = ChatMessage(
                    content = str(R.string.error_prefix, e.message ?: ""),
                    isUser = false,
                )
                _uiState.value = _uiState.value.copy(
                    messages = _uiState.value.messages + errMsg,
                )
            } finally {
                _uiState.value = _uiState.value.copy(isLoading = false)
            }
        }
    }

    fun clearMessages() {
        _uiState.value = _uiState.value.copy(messages = emptyList())
        conversationHistory.clear()
    }

    fun dismissError() {
        _uiState.value = _uiState.value.copy(errorMessage = null)
    }
}
