package com.yahav.athleagent.observability

import okhttp3.Interceptor
import okhttp3.Response

class CorrelationIdInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        val requestId = RequestIdHolder.getRequestId()

        // Clones the original request and adds the header requested by Tzuf
        val newRequest = originalRequest.newBuilder()
            .header("X-Request-ID", requestId)
            .build()

        return chain.proceed(newRequest)
    }
}