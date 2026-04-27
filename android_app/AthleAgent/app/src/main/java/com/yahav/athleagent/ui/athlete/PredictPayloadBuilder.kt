package com.yahav.athleagent.ui.athlete

import com.yahav.athleagent.network.ApiService

data class BuiltPredictionPayload(
    val legacyData: ApiService.AthleteData,
    val predictRequest: ApiService.PredictRequest,
    val sleepMinutes: Long,
    val soreness: Int,
    val stress: Int,
)

object PredictPayloadBuilder {
    fun build(
        userId: String,
        date: String,
        profile: Map<String, Any?>,
        health: Map<String, Any?>,
        checkin: Map<String, Any?>,
        nutrition: Map<String, Any?>,
    ): BuiltPredictionPayload {
        val sleepMinutes = (health["sleepMinutes"] as? Number)?.toLong() ?: 480L
        val steps = (health["steps"] as? Number)?.toLong() ?: 5000L
        val soreness = (checkin["muscleSoreness"] as? Number)?.toInt() ?: 1
        val stress = (checkin["stressLevel"] as? Number)?.toInt() ?: 20
        val energy = (checkin["energyLevel"] as? Number)?.toInt() ?: 60

        val age = (profile["age"] as? Number)?.toInt() ?: 25
        val vo2Max = (profile["vo2Max"] as? Number)?.toInt()
            ?: (profile["vo2_max"] as? Number)?.toInt()
            ?: 50
        val historyInjuryCount = (profile["historyInjuryCount"] as? Number)?.toInt()
            ?: (profile["history_injury_count"] as? Number)?.toInt()
            ?: 0

        val sleepHours = sleepMinutes / 60.0f
        val distanceKm = (steps * 0.0008).toFloat()

        val legacy = ApiService.AthleteData(
            age = age,
            bmi = 22.5f,
            history_injury_count = historyInjuryCount,
            vo2_max = vo2Max,
            daily_distance_km = distanceKm,
            workout_intensity_minutes = 60,
            avg_cadence = 160,
            sleep_hours = sleepHours,
            hrv_score = 60,
            resting_hr = 55,
            daily_calories = 2500,
            total_calories_burned = 2800,
            calorie_balance = -300,
            stress_level = stress,
            muscle_soreness = soreness,
            acute_load_7d = 1500f,
            chronic_load_21d = 1400f,
            acwr_ratio = 1.07f,
            sleep_debt_3d = 0.0f,
            hrv_drop = 0.0f
        )

        val predict = ApiService.PredictRequest(
            userId = userId,
            date = date,
            age = age,
            vo2Max = vo2Max,
            historyInjuryCount = historyInjuryCount,
            sleepMinutes = sleepMinutes.toInt(),
            steps = steps.toInt(),
            distanceMeters = (health["distanceMeters"] as? Number)?.toInt() ?: (steps * 0.8).toInt(),
            activeCalories = (health["activeCalories"] as? Number)?.toInt() ?: 0,
            totalCalories = (health["totalCalories"] as? Number)?.toInt() ?: 0,
            heartRateAvg = (health["heartRateAvg"] as? Number)?.toInt() ?: 0,
            heartRateMax = (health["heartRateMax"] as? Number)?.toInt() ?: 0,
            heartRateMin = (health["heartRateMin"] as? Number)?.toInt() ?: 0,
            weightKg = (health["weightKg"] as? Number)?.toDouble() ?: 0.0,
            bmrCalories = (health["bmrCalories"] as? Number)?.toInt() ?: 0,
            energyLevel = energy,
            muscleSoreness = soreness,
            stressLevel = stress,
            totalProtein = (nutrition["totalProtein"] as? Number)?.toInt() ?: 0,
            totalCarbs = (nutrition["totalCarbs"] as? Number)?.toInt() ?: 0,
            mealsLoggedCount = (nutrition["mealsLoggedCount"] as? Number)?.toInt() ?: 0
        )

        return BuiltPredictionPayload(
            legacyData = legacy,
            predictRequest = predict,
            sleepMinutes = sleepMinutes,
            soreness = soreness,
            stress = stress,
        )
    }
}
