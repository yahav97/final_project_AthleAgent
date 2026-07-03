package com.yahav.athleagent.observability

import com.google.firebase.auth.FirebaseAuth
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
                val normalizedType = when (eventType) {
                    "ml_trigger_success", "ml_performance_warning" -> "ml_trigger"
                    else -> eventType
                }
                val level = if (eventType == "error") "ERROR" else "INFO"
                val tag = screenTagFromMessage(message)
                val body = if (metadata.isNullOrEmpty()) message else "$message | $metadata"

                api.reportEvent(
                    ClientEventPayload(
                        eventType = normalizedType,
                        level = level,
                        tag = tag,
                        message = body,
                        userId = FirebaseAuth.getInstance().currentUser?.uid,
                        screen = tag,
                    )
                )
            } catch (e: Exception) {
                Timber.e(e, "Failed to send client event to backend")
            }
        }
    }

    /** e.g. "HomeAthleteActivity opened" → HomeAthleteActivity */
    private fun screenTagFromMessage(message: String): String {
        val suffix = " opened"
        return if (message.endsWith(suffix)) {
            message.removeSuffix(suffix).trim().ifEmpty { "AthleAgent" }
        } else {
            "AthleAgent"
        }
    }
}
