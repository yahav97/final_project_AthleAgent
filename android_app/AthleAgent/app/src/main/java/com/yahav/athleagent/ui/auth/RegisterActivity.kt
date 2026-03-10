package com.yahav.athleagent.ui.auth

import android.os.Bundle
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.yahav.athleagent.R
import com.yahav.athleagent.databinding.ActivityRegisterBinding
import com.yahav.athleagent.logic.LoginManager
import com.yahav.athleagent.utilities.SignalManager

class RegisterActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRegisterBinding
    private lateinit var loginManager: LoginManager

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        // Initialize ViewBinding
        binding = ActivityRegisterBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Handle system window insets
        ViewCompat.setOnApplyWindowInsetsListener(binding.root) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        loginManager = LoginManager()
        initViews()
    }

    private fun initViews() {
        binding.registerBTNRegister.setOnClickListener {
            val name = binding.registerETName.text.toString().trim()
            val email = binding.registerETEmail.text.toString().trim()
            val password = binding.registerETPassword.text.toString().trim()

            // Get selected role from the Toggle Group
            val role = if (binding.registerTOGGLERole.checkedButtonId == R.id.register_BTN_athlete_role) {
                "Athlete"
            } else {
                "Coach"
            }

            // Define the registration callback
            val callback = object : LoginManager.LoginCallback {
                override fun onSuccess(message: String) {
                    // Show success message using SignalManager
                    SignalManager.getInstance().toast(message)
                    finish()
                }

                override fun onFailure(error: String) {
                    // Show error message
                    SignalManager.getInstance().toast(error)
                }
            }

            // Execute the registration logic in LoginManager
            loginManager.register(email, password, name, role, callback)
        }
    }
}