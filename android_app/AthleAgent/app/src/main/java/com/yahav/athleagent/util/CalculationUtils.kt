package com.yahav.athleagent.util

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

object CalculationUtils {

    /**
     * Maps a risk score (0-100) to a qualitative risk level.
     */
    fun getRiskLevel(score: Int): String {
        return when {
            score <= 20 -> "Low"
            score <= 50 -> "Medium"
            score <= 70 -> "High"
            else -> "Critical"
        }
    }

    /**
     * Formats a date to the standard key format used in Firestore (yyyy-MM-dd).
     */
    fun formatDateToKey(date: Date): String {
        val sdf = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())
        return sdf.format(date)
    }

    /**
     * Validates if a team code is in the correct format (e.g., alphanumeric, 6 characters).
     */
    fun isTeamCodeValid(code: String): Boolean {
        val regex = Regex("^[A-Z0-9]{6}$")
        return regex.matches(code)
    }

    /**
     * Calculates sleep hours from total minutes.
     */
    fun getSleepHours(minutes: Long): String {
        val hours = minutes / 60
        val remainingMinutes = minutes % 60
        return "${hours}h ${remainingMinutes}m"
    }
}