package com.yahav.athleagent.utilities

import android.content.Context
import android.view.LayoutInflater
import android.view.View
import android.widget.ImageView
import android.widget.TextView
import androidx.core.content.ContextCompat
import com.google.android.material.snackbar.Snackbar
import com.yahav.athleagent.R
import java.lang.ref.WeakReference

// Singleton utility class for managing professional UI feedback
class SignalManager private constructor(context: Context) {

    private val contextRef = WeakReference(context)

    enum class SignalType {
        SUCCESS, ERROR, INFO
    }

    companion object {
        @Volatile
        private var instance: SignalManager? = null

        fun init(context: Context): SignalManager {
            return instance ?: synchronized(this) {
                instance ?: SignalManager(context).also { instance = it }
            }
        }

        fun getInstance(): SignalManager {
            return instance ?: throw IllegalStateException(
                "SignalManager must be initialized before use."
            )
        }
    }

    /**
     * Displays a professional, custom-styled Snackbar.
     * Replaces standard Snackbars and Toasts for a unified look.
     */
    fun showSignal(view: View, message: String, type: SignalType = SignalType.INFO) {
        val snackbar = Snackbar.make(view, "", Snackbar.LENGTH_LONG)
        val context = view.context
        val snackbarLayout = snackbar.view as Snackbar.SnackbarLayout
        val customView = LayoutInflater.from(context).inflate(R.layout.layout_custom_snackbar, snackbarLayout, false)
        
        // Setup background
        snackbar.view.setBackgroundColor(android.graphics.Color.TRANSPARENT)
        snackbarLayout.setPadding(0, 0, 0, 0)
        
        val textLabel = customView.findViewById<TextView>(R.id.snackbar_text)
        val iconImage = customView.findViewById<ImageView>(R.id.snackbar_icon)
        
        textLabel.text = message
        
        // Apply type-specific styling
        when (type) {
            SignalType.SUCCESS -> {
                iconImage.setImageResource(R.drawable.baseline_done_outline_24)
                iconImage.setColorFilter(ContextCompat.getColor(context, R.color.green))
            }
            SignalType.ERROR -> {
                iconImage.setImageResource(android.R.drawable.ic_dialog_alert)
                iconImage.setColorFilter(ContextCompat.getColor(context, R.color.red))
            }
            SignalType.INFO -> {
                iconImage.setImageResource(android.R.drawable.ic_dialog_info)
                iconImage.setColorFilter(ContextCompat.getColor(context, R.color.brand_button_light_muted))
            }
        }
        
        snackbarLayout.addView(customView, 0)
        snackbar.show()
    }
}