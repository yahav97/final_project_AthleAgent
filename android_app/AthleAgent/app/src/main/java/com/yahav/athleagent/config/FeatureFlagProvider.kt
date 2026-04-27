package com.yahav.athleagent.config

interface FeatureFlagProvider {
    fun isPredictV2Enabled(): Boolean
}

class LocalFeatureFlagProvider : FeatureFlagProvider {
    override fun isPredictV2Enabled(): Boolean = false
}
