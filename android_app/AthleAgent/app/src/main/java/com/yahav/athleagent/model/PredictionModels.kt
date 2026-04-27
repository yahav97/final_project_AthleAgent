package com.yahav.athleagent.model

import com.google.gson.annotations.SerializedName

// What we receive from the server
data class PredictionResponse(
    @SerializedName("user_id")
    val userIdLegacy: String? = null,
    @SerializedName("risk_percentage")
    val riskPercentageLegacy: Double? = null,
    @SerializedName("risk_level")
    val riskLevel: String? = null,
    @SerializedName("message")
    val messageLegacy: String? = null,
    @SerializedName("risk_score")
    val riskScore: Double? = null,
    @SerializedName("recommendation")
    val recommendation: String? = null
)