package ai.openagentic.app.api

import com.google.gson.annotations.SerializedName
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST

data class LoginRequest(
    val username: String,
    val password: String,
)

data class LoginResponse(
    val token: String,
    @SerializedName("expires_in") val expiresIn: Long,
    @SerializedName("token_type") val tokenType: String,
)

// Ollama native API format
data class OllamaChatRequest(
    val model: String,
    val messages: List<OllamaChatMessage>,
    val stream: Boolean = false,
)

data class OllamaChatMessage(
    val role: String,
    val content: String,
)

data class OllamaChatResponse(
    val model: String? = null,
    val message: OllamaChatMessage? = null,
    @SerializedName("done") val done: Boolean = true,
    val error: String? = null,
)

// Legacy types kept for compatibility
data class ChatRequest(
    val message: String,
    val model: String? = null,
)

data class ChatResponse(
    val response: String? = null,
    val error: String? = null,
)

data class HealthResponse(
    val status: String? = null,
    val version: String? = null,
)

interface GatewayApi {

    @POST("api/auth/login")
    suspend fun login(@Body request: LoginRequest): LoginResponse

    @GET("api/tags")
    suspend fun ollamaHealth(): Any

    @POST("api/chat")
    suspend fun ollamaChat(@Body request: OllamaChatRequest): OllamaChatResponse
}
