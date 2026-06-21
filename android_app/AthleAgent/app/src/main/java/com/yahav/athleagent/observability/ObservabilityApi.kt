package com.yahav.athleagent.observability

import retrofit2.http.Body
import retrofit2.http.POST

data class ClientEventPayload(
    val source: String = "android",
    val eventType: String,
    val message: String,
    val metadata: Map<String, String>? = null
)

interface ObservabilityApi {
    @POST("/api/v1/observability/client-events")
    suspend fun reportEvent(@Body payload: ClientEventPayload)
}