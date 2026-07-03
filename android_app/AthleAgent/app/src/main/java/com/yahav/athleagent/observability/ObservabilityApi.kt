package com.yahav.athleagent.observability

import com.google.gson.annotations.SerializedName
import retrofit2.http.Body
import retrofit2.http.POST

data class ClientEventPayload(
    @SerializedName("event_type") val eventType: String,
    val level: String,
    val tag: String,
    val message: String,
    @SerializedName("user_id") val userId: String? = null,
    val screen: String? = null,
)

interface ObservabilityApi {
    @POST("/api/v1/observability/client-events")
    suspend fun reportEvent(@Body payload: ClientEventPayload)
}
