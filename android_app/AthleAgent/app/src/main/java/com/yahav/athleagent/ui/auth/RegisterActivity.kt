package com.yahav.athleagent.ui.auth

import android.os.Bundle
import android.view.View
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
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

        binding = ActivityRegisterBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ViewCompat.setOnApplyWindowInsetsListener(binding.root) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        loginManager = LoginManager()
        initViews()
    }

    private fun initViews() {
        // Toggle visibility of ML fields based on selected role
        binding.registerTOGGLERole.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (isChecked) {
                if (checkedId == R.id.register_BTN_coach_role) {
                    binding.registerTILAge.visibility = View.GONE
                    binding.registerTILInjuryHistory.visibility = View.GONE
                } else {
                    binding.registerTILAge.visibility = View.VISIBLE
                    binding.registerTILInjuryHistory.visibility = View.VISIBLE
                }
            }
        }

        binding.registerBTNRegister.setOnClickListener {
            val name = binding.registerETName.text.toString().trim()
            val email = binding.registerETEmail.text.toString().trim()
            val password = binding.registerETPassword.text.toString().trim()

            val role = if (binding.registerTOGGLERole.checkedButtonId == R.id.register_BTN_athlete_role) {
                "Athlete"
            } else {
                "Coach"
            }

            // Fetch ML inputs with sensible fallbacks (relevant for Athletes)
            val ageStr = binding.registerETAge.text.toString().trim()
            val historyStr = binding.registerETInjuryHistory.text.toString().trim()
            val age = if (ageStr.isNotEmpty()) ageStr.toInt() else 25
            val historyInjuryCount = if (historyStr.isNotEmpty()) historyStr.toInt() else 0

            val callback = object : LoginManager.LoginCallback {
                override fun onSuccess(message: String) {
                    val userId = FirebaseAuth.getInstance().currentUser?.uid

                    // Only save ML fields for Athletes, not for Coaches
                    if (userId != null && role == "Athlete") {
                        val mlData = hashMapOf(
                            "age" to age,
                            "historyInjuryCount" to historyInjuryCount
                        )

                        FirebaseFirestore.getInstance().collection("users").document(userId)
                            .set(mlData, SetOptions.merge())
                            .addOnCompleteListener {
                                SignalManager.getInstance().toast(message)
                                finish()
                            }
                    } else {
                        SignalManager.getInstance().toast(message)
                        finish()
                    }
                }

                override fun onFailure(error: String) {
                    SignalManager.getInstance().toast(error)
                }
            }

            loginManager.register(email, password, name, role, callback)
        }
    }
}