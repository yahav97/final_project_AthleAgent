package com.yahav.athleagent

import android.app.Application
import com.yahav.athleagent.utilities.SignalManager
import timber.log.Timber
class App : Application() {
    override fun onCreate() {
        super.onCreate()

        SignalManager.init(this)
        if (BuildConfig.DEBUG) {
            Timber.plant(Timber.DebugTree())
        }

    }
}