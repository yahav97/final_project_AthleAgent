package com.yahav.athleagent.observability

import java.util.UUID

object RequestIdHolder {
    private var currentRequestId: String = UUID.randomUUID().toString()

    fun getRequestId(): String {
        return currentRequestId
    }

    // אפשר לקרוא לפונקציה הזו כשמתחילים סשן חדש (למשל בכניסה לאפליקציה)
    fun generateNewId(): String {
        currentRequestId = UUID.randomUUID().toString()
        return currentRequestId
    }
}