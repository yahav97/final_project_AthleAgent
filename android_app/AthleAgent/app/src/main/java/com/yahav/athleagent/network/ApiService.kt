package com.yahav.athleagent.network

import retrofit2.Call
import retrofit2.http.Body
import retrofit2.http.POST

interface ApiService {

    data class PredictionTriggerRequest(
        val userId: String,
        val date: String
    )

    data class PredictionResponse(
        val risk_level: String,
        val risk_score: Float,
        val prediction_confidence: Float
    )

    @POST("/predict/daily")
    fun getDailyPrediction(@Body data: PredictionTriggerRequest): Call<PredictionResponse>
}