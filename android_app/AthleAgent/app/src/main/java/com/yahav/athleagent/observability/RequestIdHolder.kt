package com.yahav.athleagent.observability

import java.util.UUID

object RequestIdHolder {
    private var currentRequestId: String = UUID.randomUUID().toString()

    fun getRequestId(): String {
        return currentRequestId
    }

    // This function can be called when starting a new session (e.g., when entering the app)
    fun generateNewId(): String {
        currentRequestId = UUID.randomUUID().toString()
        return currentRequestId
    }
}