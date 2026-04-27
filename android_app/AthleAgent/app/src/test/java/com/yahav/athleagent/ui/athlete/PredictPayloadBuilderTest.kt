package com.yahav.athleagent.ui.athlete

import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PredictPayloadBuilderTest {
    @Test
    fun build_generates_predict_json_keys_matching_backend_schema() {
        val payload = PredictPayloadBuilder.build(
            userId = "athlete_123",
            date = "2026-04-27",
            profile = mapOf(
                "age" to 24,
                "vo2Max" to 57,
                "historyInjuryCount" to 1,
            ),
            health = mapOf(
                "sleepMinutes" to 420,
                "steps" to 9000,
                "distanceMeters" to 7100,
                "activeCalories" to 560,
                "totalCalories" to 2650,
                "heartRateAvg" to 58,
                "heartRateMax" to 171,
                "heartRateMin" to 44,
                "weightKg" to 72.4,
                "bmrCalories" to 1650,
            ),
            checkin = mapOf(
                "energyLevel" to 66,
                "muscleSoreness" to 3,
                "stressLevel" to 40,
            ),
            nutrition = mapOf(
                "totalProtein" to 140,
                "totalCarbs" to 280,
                "mealsLoggedCount" to 3,
            ),
        )

        val jsonMap = Gson().fromJson(
            Gson().toJson(payload.predictRequest),
            Map::class.java
        )

        val expectedKeys = setOf(
            "userId",
            "date",
            "age",
            "vo2Max",
            "historyInjuryCount",
            "sleepMinutes",
            "steps",
            "distanceMeters",
            "activeCalories",
            "totalCalories",
            "heartRateAvg",
            "heartRateMax",
            "heartRateMin",
            "weightKg",
            "bmrCalories",
            "energyLevel",
            "muscleSoreness",
            "stressLevel",
            "totalProtein",
            "totalCarbs",
            "mealsLoggedCount",
        )
        assertEquals(expectedKeys, jsonMap.keys)
        assertTrue((jsonMap["userId"] as String).isNotBlank())
        assertEquals("2026-04-27", jsonMap["date"])
    }
}
