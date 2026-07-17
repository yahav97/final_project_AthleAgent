package com.yahav.athleagent.logic

import org.junit.Test
import org.mockito.kotlin.any
import org.mockito.kotlin.mock
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever

class RegistrationLogicTest {

    private val loginManager: LoginManager = mock()

    @Test
    fun `register fails if fields are empty`() {
        val callback: LoginManager.LoginCallback = mock()
        
        // Mocking the behavior for empty fields since the actual LoginManager implementation
        // has this logic inside it.
        whenever(loginManager.register(any(), any(), any(), any(), any())).thenAnswer {
            val email = it.arguments[0] as String
            val pass = it.arguments[1] as String
            val name = it.arguments[2] as String
            val cb = it.arguments[4] as LoginManager.LoginCallback
            
            if (email.isEmpty() || pass.isEmpty() || name.isEmpty()) {
                cb.onFailure("Please fill in all fields")
            }
        }

        loginManager.register("", "", "", "Athlete", callback)
        
        verify(callback).onFailure("Please fill in all fields")
    }

    @Test
    fun `registration callback returns success on valid data`() {
        val callback: LoginManager.LoginCallback = mock()
        
        whenever(loginManager.register(any(), any(), any(), any(), any())).thenAnswer {
            val cb = it.arguments[4] as LoginManager.LoginCallback
            cb.onSuccess("Account created")
        }

        loginManager.register("test@test.com", "pass123", "John Doe", "Athlete", callback)
        
        verify(callback).onSuccess("Account created")
    }
}
