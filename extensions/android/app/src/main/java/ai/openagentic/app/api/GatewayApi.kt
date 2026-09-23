package ai.openagentic.app.api

import com.google.gson.annotations.SerializedName
import retrofit2.http.Body
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path

data class LoginRequest(val username: String, val password: String)
data class TokenResponse(
    val token: String,
    @SerializedName("refresh_token") val refreshToken: String? = null,
    @SerializedName("expires_in") val expiresIn: Long = 0,
)
data class Session(val id: String, val title: String, val model: String? = null)
data class CreateSessionRequest(val title: String = "Android", val model: String? = null)
data class SendMessageRequest(val message: String, val model: String? = null, val stream: Boolean = false)
data class SessionMessage(val id: String, val role: String, val content: String, val model: String? = null)

interface GatewayApi {
    @POST("api/auth/login")
    suspend fun login(@Body request: LoginRequest): TokenResponse

    @POST("api/client/sessions")
    suspend fun createSession(@Header("Authorization") authorization: String, @Body request: CreateSessionRequest): Session

    @POST("api/client/sessions/{sessionId}/messages")
    suspend fun sendMessage(@Header("Authorization") authorization: String, @Path("sessionId") sessionId: String, @Body request: SendMessageRequest): SessionMessage
}
