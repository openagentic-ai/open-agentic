package ai.openagentic.app

import android.app.Application
import android.content.SharedPreferences
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import ai.openagentic.app.api.ApiClient
import ai.openagentic.app.api.LoginRequest
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.catch
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

    val currentLanguage: String
        get() = LocaleHelper.getSavedLanguage(getApplication())

    private fun str(resId: Int): String = getApplication<Application>().getString(resId)
    private fun str(resId: Int, vararg args: Any): String = getApplication<Application>().getString(resId, *args)

    fun setLanguage(language: String) {
        LocaleHelper.saveLanguage(getApplication(), language)
    }

    init {
        _uiState.value = _uiState.value.copy(
            gatewayUrl = prefs.getString("gateway_url", "http://192.168.0.15:18789") ?: "",
            username = prefs.getString("username", "admin") ?: "",
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
                apiClient!!.api.health()

                val user = _uiState.value.username
                val pass = _uiState.value.password
                if (user.isNotBlank() && pass.isNotBlank()) {
                    val loginResp = apiClient!!.api.login(LoginRequest(user, pass))
                    _uiState.value = _uiState.value.copy(
                        isConnected = true,
                        isLoading = false,
                        token = loginResp.token,
                        errorMessage = null,
                    )
                } else {
                    _uiState.value = _uiState.value.copy(
                        isConnected = true,
                        isLoading = false,
                        errorMessage = null,
                    )
                }
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
        val token = _uiState.value.token

        val userMsg = ChatMessage(content = text, isUser = true)
        _uiState.value = _uiState.value.copy(
            messages = _uiState.value.messages + userMsg,
            isLoading = true,
        )

        viewModelScope.launch {
            try {
                if (token != null) {
                    val aiMsg = ChatMessage(content = "", isUser = false, isStreaming = true)
                    _uiState.value = _uiState.value.copy(
                        messages = _uiState.value.messages + aiMsg,
                    )

                    val sb = StringBuilder()
                    client.chatStream(_uiState.value.gatewayUrl, token, text)
                        .catch {
                            val resp = client.chat(token, text)
                            val content = resp.response ?: resp.error ?: str(R.string.error_no_response)
                            updateLastAiMessage(content, streaming = false)
                        }
                        .collect { chunk ->
                            sb.append(chunk)
                            updateLastAiMessage(sb.toString(), streaming = true)
                        }
                    updateLastAiMessage(sb.toString(), streaming = false)
                } else {
                    val resp = client.chat("", text)
                    val content = resp.response ?: resp.error ?: str(R.string.error_no_response)
                    val aiMsg = ChatMessage(content = content, isUser = false)
                    _uiState.value = _uiState.value.copy(
                        messages = _uiState.value.messages + aiMsg,
                    )
                }
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

    private fun updateLastAiMessage(content: String, streaming: Boolean) {
        val msgs = _uiState.value.messages.toMutableList()
        if (msgs.isNotEmpty() && !msgs.last().isUser) {
            msgs[msgs.lastIndex] = msgs.last().copy(content = content, isStreaming = streaming)
            _uiState.value = _uiState.value.copy(messages = msgs)
        }
    }

    fun clearMessages() {
        _uiState.value = _uiState.value.copy(messages = emptyList())
    }

    fun dismissError() {
        _uiState.value = _uiState.value.copy(errorMessage = null)
    }
}
