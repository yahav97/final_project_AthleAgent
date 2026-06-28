package com.yahav.athleagent.ui.auth

import android.content.Intent
import android.os.Bundle
import android.view.View
import android.view.animation.AnimationUtils
import androidx.appcompat.widget.LinearLayoutCompat
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.firebase.ui.auth.AuthUI
import com.firebase.ui.auth.FirebaseAuthUIActivityResultContract
import com.firebase.ui.auth.data.model.FirebaseAuthUIAuthenticationResult
import com.google.android.material.datepicker.MaterialDatePicker
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.firebase.auth.FirebaseUser
import com.yahav.athleagent.R
import com.yahav.athleagent.ui.athlete.HomeAthleteActivity
import com.yahav.athleagent.ui.coach.HomeCoachActivity
import com.yahav.athleagent.databinding.ActivityLoginBinding
import com.yahav.athleagent.logic.LoginManager
import com.yahav.athleagent.utilities.SignalManager
import java.text.SimpleDateFormat
import java.util.*

class LoginActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLoginBinding
    private lateinit var loginManager: LoginManager
    private var googleSelectedBirthDate: String = "1995-01-01"

    private val signInLauncher = registerForActivityResult(
        FirebaseAuthUIActivityResultContract(),
    ) { res ->
        this.onSignInResult(res)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        binding = ActivityLoginBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val entranceAnim = AnimationUtils.loadAnimation(this, R.anim.anim_auth_entrance)
        findViewById<LinearLayoutCompat>(R.id.login_form_container).startAnimation(entranceAnim)

        ViewCompat.setOnApplyWindowInsetsListener(binding.loginRoot) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        loginManager = LoginManager()

        val currentUser = FirebaseAuth.getInstance().currentUser
        if (currentUser != null) {
            binding.loginLayoutContent.visibility = View.GONE
            binding.loginLayoutLoading.visibility = View.VISIBLE
            checkUserRoleAndNavigate(currentUser.uid)
        } else {
            initViews()
        }
    }

    private fun initViews() {
        binding.loginBTNGoogle.setOnClickListener {
            signInWithGoogle()
        }

        val callback = object : LoginManager.LoginCallback {
            override fun onSuccess(message: String) {
                SignalManager.getInstance().snackbar(binding.root, message)
                val uid = FirebaseAuth.getInstance().currentUser?.uid
                if (uid != null) {
                    binding.loginLayoutContent.visibility = View.GONE
                    binding.loginLayoutLoading.visibility = View.VISIBLE
                    checkUserRoleAndNavigate(uid)
                }
            }

            override fun onFailure(error: String) {
                SignalManager.getInstance().snackbar(binding.root, error)
                binding.loginLayoutContent.visibility = View.VISIBLE
                binding.loginLayoutLoading.visibility = View.GONE
            }
        }

        binding.loginBTNLogin.setOnClickListener {
            val email = binding.loginETUsername.text.toString().trim()
            val password = binding.loginETPassword.text.toString().trim()
            if (email.isEmpty() || password.isEmpty()) {
                SignalManager.getInstance().snackbar(binding.root, "Please enter email and password")
                return@setOnClickListener
            }
            binding.loginLayoutContent.visibility = View.GONE
            binding.loginLayoutLoading.visibility = View.VISIBLE
            loginManager.login(email, password, callback)
        }

        binding.loginLBLCreateAccount.setOnClickListener {
            startActivity(Intent(this, RegisterActivity::class.java))
        }

        binding.loginLBLForgotPassword.setOnClickListener {
            val email = binding.loginETUsername.text.toString().trim()
            if (email.isEmpty()) {
                SignalManager.getInstance().snackbar(binding.root, "Please enter your email first")
            } else {
                loginManager.forgotPassword(email, callback)
            }
        }
    }

    private fun signInWithGoogle() {
        binding.loginLayoutContent.visibility = View.GONE
        binding.loginLayoutLoading.visibility = View.VISIBLE

        val providers = arrayListOf(AuthUI.IdpConfig.GoogleBuilder().build())
        val signInIntent = AuthUI.getInstance()
            .createSignInIntentBuilder()
            .setAvailableProviders(providers)
            .build()
        signInLauncher.launch(signInIntent)
    }

    private fun onSignInResult(result: FirebaseAuthUIAuthenticationResult) {
        if (result.resultCode == RESULT_OK) {
            val user = FirebaseAuth.getInstance().currentUser
            if (user != null) {
                val db = FirebaseFirestore.getInstance()
                db.collection("users").document(user.uid).get().addOnSuccessListener { document ->
                    if (!document.exists()) {
                        binding.loginLayoutLoading.visibility = View.GONE
                        binding.loginLayoutContent.visibility = View.VISIBLE
                        showRoleSelectionDialog(user)
                    } else {
                        val role = document.getString("role") ?: "Athlete"
                        navigateToDashboard(role)
                    }
                }.addOnFailureListener {
                    binding.loginLayoutLoading.visibility = View.GONE
                    binding.loginLayoutContent.visibility = View.VISIBLE
                    SignalManager.getInstance().snackbar(binding.root, "Failed to load user profile")
                }
            }
        } else {
            binding.loginLayoutLoading.visibility = View.GONE
            binding.loginLayoutContent.visibility = View.VISIBLE
        }
    }

    private fun showRoleSelectionDialog(user: FirebaseUser) {
        val dialogView = layoutInflater.inflate(R.layout.dialog_google_profile, null)

        val toggleGroup = dialogView.findViewById<com.google.android.material.button.MaterialButtonToggleGroup>(R.id.google_TOGGLE_role)
        val tilBirthDate = dialogView.findViewById<com.google.android.material.textfield.TextInputLayout>(R.id.google_TIL_birthDate)
        val etBirthDate = dialogView.findViewById<com.google.android.material.textfield.TextInputEditText>(R.id.google_ET_birthDate)
        val tilInjury = dialogView.findViewById<com.google.android.material.textfield.TextInputLayout>(R.id.google_TIL_injury_history)
        val etInjury = dialogView.findViewById<com.google.android.material.textfield.TextInputEditText>(R.id.google_ET_injury_history)
        val btnSave = dialogView.findViewById<com.google.android.material.button.MaterialButton>(R.id.google_BTN_save)

        toggleGroup.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (isChecked) {
                if (checkedId == R.id.google_BTN_coach_role) {
                    tilBirthDate.visibility = View.GONE
                    tilInjury.visibility = View.GONE
                } else {
                    tilBirthDate.visibility = View.VISIBLE
                    tilInjury.visibility = View.VISIBLE
                }
            }
        }

        val dialog = MaterialAlertDialogBuilder(this)
            .setView(dialogView)
            .setCancelable(false)
            .create()

        val openPickerListener = View.OnClickListener {
            val datePicker = MaterialDatePicker.Builder.datePicker()
                .setTitleText("Select Birth Date")
                .setSelection(MaterialDatePicker.todayInUtcMilliseconds())
                .build()

            datePicker.addOnPositiveButtonClickListener { selection ->
                val calendar = Calendar.getInstance(TimeZone.getTimeZone("UTC"))
                calendar.timeInMillis = selection
                val format = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())
                googleSelectedBirthDate = format.format(calendar.time)
                etBirthDate.setText(googleSelectedBirthDate)
            }
            datePicker.show(supportFragmentManager, "GOOGLE_BIRTH_DATE_PICKER")
        }

        tilBirthDate.setEndIconOnClickListener(openPickerListener)
        etBirthDate.setOnClickListener(openPickerListener)

        btnSave.setOnClickListener {
            val isAthlete = toggleGroup.checkedButtonId == R.id.google_BTN_athlete_role
            val selectedRole = if (isAthlete) "Athlete" else "Coach"

            val injuryStr = etInjury.text.toString().trim()
            val injuries = if (injuryStr.isNotEmpty()) injuryStr.toInt() else 0
            val birthDate = if (googleSelectedBirthDate.isNotEmpty()) googleSelectedBirthDate else "1995-01-01"

            dialog.dismiss()
            binding.loginLayoutContent.visibility = View.GONE
            binding.loginLayoutLoading.visibility = View.VISIBLE

            saveUserToFirestore(user, selectedRole, birthDate, injuries)
        }

        dialog.show()

        dialog.window?.setLayout(
            android.view.ViewGroup.LayoutParams.MATCH_PARENT,
            android.view.ViewGroup.LayoutParams.MATCH_PARENT
        )
        dialog.window?.setBackgroundDrawableResource(android.R.color.transparent)
    }

    private fun saveUserToFirestore(user: FirebaseUser, role: String, birthDate: String = "1995-01-01", injuries: Int = 0) {
        val userData = hashMapOf<String, Any>(
            "fullName" to (user.displayName ?: "User"),
            "email" to (user.email ?: ""),
            "role" to role,
            "teamId" to ""
        )

        if (role == "Athlete") {
            userData["birth_date"] = birthDate
            userData["historyInjuryCount"] = injuries
        }

        FirebaseFirestore.getInstance().collection("users").document(user.uid)
            .set(userData)
            .addOnSuccessListener {
                SignalManager.getInstance().snackbar(binding.root, "Welcome ${user.displayName}!")
                navigateToDashboard(role)
            }
            .addOnFailureListener {
                binding.loginLayoutLoading.visibility = View.GONE
                binding.loginLayoutContent.visibility = View.VISIBLE
                SignalManager.getInstance().snackbar(binding.root, "Error saving profile")
            }
    }

    private fun checkUserRoleAndNavigate(uid: String) {
        FirebaseFirestore.getInstance().collection("users").document(uid).get()
            .addOnSuccessListener { doc ->
                val role = doc.getString("role") ?: "Athlete"
                navigateToDashboard(role)
            }
            .addOnFailureListener {
                binding.loginLayoutLoading.visibility = View.GONE
                binding.loginLayoutContent.visibility = View.VISIBLE
                SignalManager.getInstance().snackbar(binding.root, "Failed to check user role")
            }
    }

    private fun navigateToDashboard(role: String) {
        val intent = if (role == "Coach") {
            Intent(this, HomeCoachActivity::class.java)
        } else {
            Intent(this, HomeAthleteActivity::class.java)
        }
        startActivity(intent)
        finish()
    }
}