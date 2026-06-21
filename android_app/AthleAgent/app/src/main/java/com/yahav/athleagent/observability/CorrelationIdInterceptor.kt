package com.yahav.athleagent.observability

import okhttp3.Interceptor
import okhttp3.Response

class CorrelationIdInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        val requestId = RequestIdHolder.getRequestId()

        // משכפלים את הבקשה המקורית ומוסיפים לה את ההדר שצוף ביקשה
        val newRequest = originalRequest.newBuilder()
            .header("X-Request-ID", requestId)
            .build()

        return chain.proceed(newRequest)
    }
}