package com.yahav.athleagent.model


// What we receive from the server
data class PredictionResponse(
    val user_id: String,
    val risk_percentage: Double,
    val risk_level: String,
    val message: String
)