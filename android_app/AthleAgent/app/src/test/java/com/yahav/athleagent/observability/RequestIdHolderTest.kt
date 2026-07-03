package com.yahav.athleagent.observability

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class RequestIdHolderTest {

    @Test
    fun `getRequestId returns a non-null UUID`() {
        val requestId = RequestIdHolder.getRequestId()
        assertNotNull(requestId)
        assertTrue(requestId.isNotEmpty())
    }

    @Test
    fun `generateNewId creates a different unique ID`() {
        val firstId = RequestIdHolder.getRequestId()
        val newId = RequestIdHolder.generateNewId()
        
        assertNotEquals(firstId, newId)
        assertEquals(newId, RequestIdHolder.getRequestId())
    }

    private fun assertTrue(condition: Boolean) {
        if (!condition) throw AssertionError()
    }
}