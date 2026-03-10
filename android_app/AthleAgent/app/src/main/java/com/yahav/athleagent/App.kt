package com.yahav.athleagent

import android.app.Application
import com.yahav.athleagent.utilities.SignalManager

class App : Application() {
    override fun onCreate() {
        super.onCreate()

        SignalManager.init(this)

    }
}