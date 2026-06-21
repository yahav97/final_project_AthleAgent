package com.yahav.athleagent.ui.auth

import android.os.Bundle
import android.view.View
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.google.android.material.datepicker.MaterialDatePicker
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import com.yahav.athleagent.R
import com.yahav.athleagent.databinding.ActivityRegisterBinding
import com.yahav.athleagent.logic.LoginManager
import com.yahav.athleagent.utilities.SignalManager
import java.text.SimpleDateFormat
import java.util.*

class RegisterActivity : AppCompatActivity() {

    private lateinit var binding: ActivityRegisterBinding
    private lateinit var loginManager: LoginManager
    private var selectedBirthDate: String = "1995-01-01"

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
        binding.registerTOGGLERole.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (isChecked) {
                if (checkedId == R.id.register_BTN_coach_role) {
                    binding.registerTILBirthDate.visibility = View.GONE
                    binding.registerTILInjuryHistory.visibility = View.GONE
                } else {
                    binding.registerTILBirthDate.visibility = View.VISIBLE
                    binding.registerTILInjuryHistory.visibility = View.VISIBLE
                }
            }
        }

        binding.registerTILBirthDate.setEndIconOnClickListener {
            showDatePicker()
        }

        binding.registerETBirthDate.setOnClickListener {
            showDatePicker()
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

            val historyStr = binding.registerETInjuryHistory.text.toString().trim()
            val historyInjuryCount = if (historyStr.isNotEmpty()) historyStr.toInt() else 0

            val callback = object : LoginManager.LoginCallback {
                override fun onSuccess(message: String) {
                    val userId = FirebaseAuth.getInstance().currentUser?.uid

                    if (userId != null && role == "Athlete") {
                        val mlData = hashMapOf(
                            "birth_date" to selectedBirthDate,
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

    private fun showDatePicker() {
        val datePicker = MaterialDatePicker.Builder.datePicker()
            .setTitleText("Select Birth Date")
            .setSelection(MaterialDatePicker.todayInUtcMilliseconds())
            .build()

        datePicker.addOnPositiveButtonClickListener { selection ->
            val calendar = Calendar.getInstance(TimeZone.getTimeZone("UTC"))
            calendar.timeInMillis = selection
            val format = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())
            selectedBirthDate = format.format(calendar.time)
            binding.registerETBirthDate.setText(selectedBirthDate)
        }
        datePicker.show(supportFragmentManager, "BIRTH_DATE_PICKER")
    }
}