package com.yahav.athleagent.ui.auth

import android.content.Intent
import android.os.Bundle
import android.view.View
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.firebase.ui.auth.AuthUI
import com.firebase.ui.auth.FirebaseAuthUIActivityResultContract
import com.firebase.ui.auth.data.model.FirebaseAuthUIAuthenticationResult
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.firebase.auth.FirebaseUser
import com.yahav.athleagent.ui.athlete.HomeAthleteActivity
import com.yahav.athleagent.ui.coach.HomeCoachActivity
import com.yahav.athleagent.databinding.ActivityLoginBinding
import com.yahav.athleagent.logic.LoginManager
import com.yahav.athleagent.utilities.SignalManager

class LoginActivity : AppCompatActivity() {

    private lateinit var binding: ActivityLoginBinding
    private lateinit var loginManager: LoginManager

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

        ViewCompat.setOnApplyWindowInsetsListener(binding.loginRoot) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        loginManager = LoginManager()

        // Check if the user is already logged in when the screen loads
        val currentUser = FirebaseAuth.getInstance().currentUser
        if (currentUser != null) {
            // User is logged in!
            // Hide the login inputs and show the central loading screen
            binding.loginLayoutContent.visibility = View.GONE
            binding.loginLayoutLoading.visibility = View.VISIBLE

            checkUserRoleAndNavigate(currentUser.uid)
        } else {
            // User is not logged in - show the standard login inputs
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
                    // Show loading screen and hide buttons while transitioning to home screen
                    binding.loginLayoutContent.visibility = View.GONE
                    binding.loginLayoutLoading.visibility = View.VISIBLE
                    checkUserRoleAndNavigate(uid)
                }
            }

            override fun onFailure(error: String) {
                SignalManager.getInstance().snackbar(binding.root, error)
                // In case of error - restore the normal view
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
            // Show loading screen while login requests are sent to Firebase
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
        // Start Google sign-in process, show loading UI
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
                        // If it's a new user and needs to select a role, restore the normal view (so the dialog pops up over it)
                        binding.loginLayoutLoading.visibility = View.GONE
                        binding.loginLayoutContent.visibility = View.VISIBLE
                        showRoleSelectionDialog(user)
                    } else {
                        // Retrieve the stored role and navigate accordingly
                        val role = document.getString("role") ?: "Athlete"
                        navigateToDashboard(role)
                    }
                }.addOnFailureListener {
                    // In case of a database error
                    binding.loginLayoutLoading.visibility = View.GONE
                    binding.loginLayoutContent.visibility = View.VISIBLE
                    SignalManager.getInstance().snackbar(binding.root, "Failed to load user profile")
                }
            }
        } else {
            // Google sign-in failed  - restore the normal view
            binding.loginLayoutLoading.visibility = View.GONE
            binding.loginLayoutContent.visibility = View.VISIBLE
            // Intentionally not showing a snackbar if the user simply closed the Google window voluntarily
        }
    }

    private fun showRoleSelectionDialog(user: FirebaseUser) {
        val roles = arrayOf("Athlete", "Coach")
        MaterialAlertDialogBuilder(this)
            .setTitle("Select Your Role")
            .setMessage("Are you a Coach or an Athlete?")
            .setCancelable(false)
            .setItems(roles) { _, which ->
                val selectedRole = roles[which]
                // User made a selection, show loading UI while data is being saved
                binding.loginLayoutContent.visibility = View.GONE
                binding.loginLayoutLoading.visibility = View.VISIBLE
                saveUserToFirestore(user, selectedRole)
            }
            .show()
    }

    private fun saveUserToFirestore(user: FirebaseUser, role: String) {
        val userData = hashMapOf(
            "fullName" to (user.displayName ?: "User"),
            "email" to (user.email ?: ""),
            "role" to role,
            "teamId" to ""
        )

        FirebaseFirestore.getInstance().collection("users").document(user.uid)
            .set(userData)
            .addOnSuccessListener {
                SignalManager.getInstance().snackbar(binding.root, "Welcome ${user.displayName}!")
                navigateToDashboard(role)
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