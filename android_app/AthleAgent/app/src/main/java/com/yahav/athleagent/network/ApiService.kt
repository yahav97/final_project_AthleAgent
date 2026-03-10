package com.yahav.athleagent.network

import com.yahav.athleagent.model.PredictionResponse
import retrofit2.Call
import retrofit2.http.Body
import retrofit2.http.POST

interface ApiService {
    data class AthleteData(
        val age: Int,
        val bmi: Float,
        val history_injury_count: Int,
        val vo2_max: Int,
        val daily_distance_km: Float,
        val workout_intensity_minutes: Int,
        val avg_cadence: Int,
        val sleep_hours: Float,
        val hrv_score: Int,
        val resting_hr: Int,
        val daily_calories: Int,
        val total_calories_burned: Int,
        val calorie_balance: Int,
        val stress_level: Int,
        val muscle_soreness: Int,
        val acute_load_7d: Float,
        val chronic_load_21d: Float,
        val acwr_ratio: Float,
        val sleep_debt_3d: Float,
        val hrv_drop: Float
    )

    @POST("/demo_predict")
    fun getDemoPrediction(@Body data: AthleteData): Call<PredictionResponse>
}
