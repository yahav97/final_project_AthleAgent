package com.yahav.athleagent.utilities

import android.content.Context
import android.view.View
import android.widget.Toast
import com.google.android.material.snackbar.Snackbar
import java.lang.ref.WeakReference

// Singleton utility class for managing UI feedback mechanisms like Toasts and Snackbars
class SignalManager private constructor(context: Context) {

    // Use a WeakReference to prevent memory leaks associated with holding a Context
    private val contextRef = WeakReference(context)

    enum class ToastLength(val length: Int) {
        SHORT(Toast.LENGTH_SHORT),
        LONG(Toast.LENGTH_LONG)
    }

    companion object {
        @Volatile
        private var instance: SignalManager? = null

        // Initializes the singleton instance (should be called once, typically in the Application class)
        fun init(context: Context): SignalManager {
            return instance ?: synchronized(this) {
                instance ?: SignalManager(context).also { instance = it }
            }
        }

        // Returns the initialized singleton instance, throwing an exception if not initialized
        fun getInstance(): SignalManager {
            return instance ?: throw IllegalStateException(
                "SignalManager must be initialized by calling init(context) before use."
            )
        }
    }

    // Displays a standard Android Toast message
    fun toast(text: String, duration: ToastLength = ToastLength.SHORT) {
        contextRef.get()?.let { context ->
            Toast.makeText(context, text, duration.ordinal).show()
        }
    }

    // Displays a custom, styled Material Snackbar
    fun snackbar(view: View, text: String) {
        Snackbar.make(view, text, Snackbar.LENGTH_LONG)
            // Set the desired background color
            .setBackgroundTint(view.context.getColor(com.yahav.athleagent.R.color.text))
            .setTextColor(view.context.getColor(com.yahav.athleagent.R.color.background_white_ghost))
            .show()
    }
}