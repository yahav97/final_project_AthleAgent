package com.yahav.athleagent.observability

import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.auth.FirebaseUser
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runTest
import org.junit.Before
import org.junit.Test
import org.mockito.Mock
import org.mockito.MockedStatic
import org.mockito.Mockito
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.any
import org.mockito.kotlin.times
import org.mockito.kotlin.verify

@OptIn(ExperimentalCoroutinesApi::class)
class ClientEventReporterTest {

    @Mock
    private lateinit var mockApi: ObservabilityApi
    
    @Mock
    private lateinit var mockAuth: FirebaseAuth
    
    @Mock
    private lateinit var mockUser: FirebaseUser

    private lateinit var reporter: ClientEventReporter

    @Before
    fun setup() {
        MockitoAnnotations.openMocks(this)
    }

    @Test
    fun `reportEvent calls API with correct payload`() = runTest {
        // Mock FirebaseAuth static method
        val authStatic: MockedStatic<FirebaseAuth> = Mockito.mockStatic(FirebaseAuth::class.java)
        authStatic.`when`<FirebaseAuth> { FirebaseAuth.getInstance() }.thenReturn(mockAuth)
        Mockito.`when`(mockAuth.currentUser).thenReturn(mockUser)
        Mockito.`when`(mockUser.uid).thenReturn("test_uid")

        try {
            reporter = ClientEventReporter(mockApi, this)

            val eventType = "test_event"
            val message = "test message"
            val metadata = mapOf("key" to "value")

            reporter.reportEvent(eventType, message, metadata)
            
            advanceUntilIdle() 
            
            verify(mockApi, times(1)).reportEvent(any())
        } finally {
            authStatic.close()
        }
    }
}
