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

    // הוספנו את החשיפה של ה-API החדש כאן!
    val observabilityApi: ObservabilityApi by lazy {
        retrofit.create(ObservabilityApi::class.java)
    }
}