package com.yahav.athleagent.config

object FeatureFlags {
    // remote_config_ready: swap provider implementation later, keep call-sites unchanged.
    private val provider: FeatureFlagProvider = LocalFeatureFlagProvider()

    fun isPredictV2Enabled(): Boolean = provider.isPredictV2Enabled()
}
