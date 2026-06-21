package com.yahav.athleagent.observability

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import timber.log.Timber

class ClientEventReporter(private val api: ObservabilityApi) {
    private val scope = CoroutineScope(Dispatchers.IO)

    fun reportEvent(eventType: String, message: String, metadata: Map<String, String>? = null) {
        Timber.tag("AthleAgentLogs").d("Event: $eventType | Message: $message")

        scope.launch {
            try {
                val payload = ClientEventPayload(
                    eventType = eventType,
                    message = message,
                    metadata = metadata
                )
                // Fire and forget
                api.reportEvent(payload)
            } catch (e: Exception) {
                Timber.e(e, "Failed to send client event to backend")
            }
        }
    }
}