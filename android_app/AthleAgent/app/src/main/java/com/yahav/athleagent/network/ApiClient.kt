package com.yahav.athleagent.network

import com.yahav.athleagent.observability.CorrelationIdInterceptor
import com.yahav.athleagent.observability.ObservabilityApi
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

object ApiClient {
    private const val BASE_URL = "http://10.0.2.2:8000/"

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(CorrelationIdInterceptor())
        .addInterceptor { chain ->
            val request = chain.request()
            var response = chain.proceed(request)
            var tryCount = 0
            val maxLimit = 3

            while (!response.isSuccessful && response.code == 503 && tryCount < maxLimit) {
                tryCount++
                // Wait 2 seconds before retrying
                Thread.sleep(2000)
                response.close()
                response = chain.proceed(request)
            }
            response
        }
        .build()

    private val retrofit: Retrofit by lazy {
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }

    val apiService: ApiService by lazy {
        retrofit.create(ApiService::class.java)
    }

    // We added the new API exposure here!
    val observabilityApi: ObservabilityApi by lazy {
        retrofit.create(ObservabilityApi::class.java)
    }
}