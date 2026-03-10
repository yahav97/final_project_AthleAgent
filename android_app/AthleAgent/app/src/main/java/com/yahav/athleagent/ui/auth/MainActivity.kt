package com.yahav.athleagent.ui.auth

import android.content.Intent
import android.os.Bundle
import android.util.Log
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import com.yahav.athleagent.ui.athlete.HomeAthleteActivity
import com.yahav.athleagent.ui.coach.HomeCoachActivity
import com.yahav.athleagent.databinding.ActivityMainBinding

// Entry point of the application responsible for routing users based on their auth state and role
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private val auth = FirebaseAuth.getInstance()
    private val db = FirebaseFirestore.getInstance()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Apply window insets for edge-to-edge UI support
        ViewCompat.setOnApplyWindowInsetsListener(binding.root) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        // Determine where the user should be navigated
        routeUser()
    }

    private fun routeUser() {
        val currentUser = auth.currentUser

        // If no user is authenticated, redirect to the login screen
        if (currentUser == null) {
            startActivity(Intent(this, LoginActivity::class.java))
            finish()
            return
        }

        Log.d("Router", "Fetching user role from Firestore...")

        // Fetch the authenticated user's profile from Firestore
        db.collection("users").document(currentUser.uid).get()
            .addOnSuccessListener { document ->
                if (document != null && document.exists()) {
                    // Retrieve the role, defaulting to "Athlete" if not specified
                    val role = document.getString("role") ?: "Athlete"
                    Log.d("Router", "User role is: $role")

                    // Route to the appropriate dashboard based on the role
                    if (role == "Coach") {
                        startActivity(Intent(this, HomeCoachActivity::class.java))
                    } else {
                        startActivity(Intent(this, HomeAthleteActivity::class.java))
                    }
                    finish()

                } else {
                    // User document is missing, redirect to login as a fallback
                    Log.e("Router", "User document not found!")
                    startActivity(Intent(this, LoginActivity::class.java))
                    finish()
                }
            }
            .addOnFailureListener { exception ->
                Log.e("Router", "Error fetching document", exception)
            }
    }
}