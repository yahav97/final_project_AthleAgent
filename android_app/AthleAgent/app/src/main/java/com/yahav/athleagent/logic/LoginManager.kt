package com.yahav.athleagent.logic

import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore

class LoginManager {

    private val auth: FirebaseAuth = FirebaseAuth.getInstance()
    private val db: FirebaseFirestore = FirebaseFirestore.getInstance()

    interface LoginCallback {
        fun onSuccess(message: String)
        fun onFailure(error: String)
    }


     // Standard email/password login

    fun login(email: String, pass: String, callback: LoginCallback) {
        if (email.isEmpty() || pass.isEmpty()) {
            callback.onFailure("Please fill in all fields")
            return
        }

        auth.signInWithEmailAndPassword(email, pass)
            .addOnCompleteListener { task ->
                if (task.isSuccessful) {
                    callback.onSuccess("Login Successful!")
                } else {
                    callback.onFailure(task.exception?.message ?: "Login failed")
                }
            }
    }


     // Full registration process

    fun register(email: String, pass: String, fullName: String, role: String, callback: LoginCallback) {
        if (email.isEmpty() || pass.isEmpty() || fullName.isEmpty()) {
            callback.onFailure("Please fill in all fields")
            return
        }

        // Step 1: Create the Auth account
        auth.createUserWithEmailAndPassword(email, pass)
            .addOnCompleteListener { task ->
                if (task.isSuccessful) {
                    val userId = auth.currentUser?.uid ?: ""
                    // Step 2: Create the profile document in Firestore
                    createProfile(userId, fullName, email, role, callback)
                } else {
                    callback.onFailure(task.exception?.message ?: "Registration failed")
                }
            }
    }

     // Saves user data to Firestore under the 'users' collection

    private fun createProfile(userId: String, fullName: String, email: String, role: String, callback: LoginCallback) {
        val userProfile = hashMapOf(
            "uid" to userId,
            "fullName" to fullName,
            "email" to email,
            "role" to role // "Athlete" or "Coach"
        )

        db.collection("users").document(userId)
            .set(userProfile)
            .addOnSuccessListener {
                callback.onSuccess("Account and Profile created successfully!")
            }
            .addOnFailureListener { e ->
                callback.onFailure("Failed to create profile: ${e.message}")
            }
    }


     // Sends a password reset link to the provided email

    fun forgotPassword(email: String, callback: LoginCallback) {
        if (email.isEmpty()) {
            callback.onFailure("Please enter your email first to reset password")
            return
        }

        auth.sendPasswordResetEmail(email)
            .addOnCompleteListener { task ->
                if (task.isSuccessful) {
                    callback.onSuccess("Password reset email sent!")
                } else {
                    callback.onFailure(task.exception?.message ?: "Failed to send reset email")
                }
            }
    }
}