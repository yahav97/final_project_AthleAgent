package com.yahav.athleagent.ui.coach

import android.annotation.SuppressLint
import android.content.Intent
import android.os.Bundle
import android.util.Log
import android.view.View
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.firebase.ui.auth.AuthUI
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import com.yahav.athleagent.databinding.ActivityHomeCoachBinding
import com.yahav.athleagent.ui.auth.LoginActivity

class HomeCoachActivity : AppCompatActivity() {

    private lateinit var binding: ActivityHomeCoachBinding
    private val db = FirebaseFirestore.getInstance()
    private val auth = FirebaseAuth.getInstance()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        binding = ActivityHomeCoachBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ViewCompat.setOnApplyWindowInsetsListener(binding.root) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        setupClickListeners()
        loadCoachData()
        listenForPendingRequests()
    }

    private fun setupClickListeners() {
        // Navigate to the requests screen when clicking the notification
        binding.coachHomeCARDNotifications.setOnClickListener {
            val intent = Intent(this, CoachRequestsActivity::class.java)
            startActivity(intent)
        }
        binding.coachHomeBTNManageTeam.setOnClickListener {
            val intent = Intent(this, CoachRequestsActivity::class.java)
            startActivity(intent)
        }
        // Navigate to the dashboard screen
        binding.coachHomeBTNDashboard.setOnClickListener {
            val intent = Intent(this, CoachDashboardActivity::class.java)
            startActivity(intent)
        }
        binding.btnLogout.setOnClickListener {
            performLogout()
        }
    }

    private fun loadCoachData() {
        val uid = auth.currentUser?.uid ?: return

        // coach name
        db.collection("users").document(uid).get()
            .addOnSuccessListener { document ->
                if (document.exists()) {
                    val coachName = document.getString("fullName") ?: "Coach"
                    binding.coachHomeLBLName.text = coachName
                }
            }
            .addOnFailureListener {
                Log.e("HomeCoach", "Failed to load coach data")
            }

        // Team Name
        db.collection("teams").whereEqualTo("coachId", uid).get()
            .addOnSuccessListener { teams ->
                if (!teams.isEmpty) {
                    val teamName = teams.documents[0].getString("TeamName") ?: "Unknown Team"
                    binding.coachHomeLBLTeamName.text = teamName
                }
            }
            .addOnFailureListener {
                Log.e("HomeCoach", "Failed to load team data")
            }
    }

    @SuppressLint("SetTextI18n")
    private fun listenForPendingRequests() {
        val uid = auth.currentUser?.uid ?: return

        // First, locate the coach's team
        db.collection("teams").whereEqualTo("coachId", uid).get()
            .addOnSuccessListener { teams ->
                if (!teams.isEmpty) {
                    val teamId = teams.documents[0].id

                    // Listen in real-time (SnapshotListener) for pending join requests
                    db.collection("teams").document(teamId)
                        .collection("requests")
                        .whereEqualTo("status", "pending")
                        .addSnapshotListener { snapshot, error ->
                            if (error != null) {
                                Log.e("HomeCoach", "Listen failed.", error)
                                return@addSnapshotListener
                            }

                            if (snapshot != null) {
                                val pendingCount = snapshot.size()
                                if (pendingCount > 0) {
                                    binding.coachHomeCARDNotifications.visibility = View.VISIBLE
                                    binding.coachHomeLBLNotifText.text = "You have $pendingCount new athlete join requests!"
                                } else {
                                    // If there are no requests, update the text (or optionally hide the notification)
                                    binding.coachHomeLBLNotifText.text = "No new requests at the moment."
                                    // Optional: Hide the card entirely when there are no requests
                                    // binding.coachHomeCARDNotifications.visibility = View.GONE
                                }
                            }
                        }
                }
            }
    }
    private fun performLogout() {
        // 1. Sign out from Firebase Auth (email/password)
        FirebaseAuth.getInstance().signOut()

        // 2. Sign out from Google Auth to allow account selection on next login
        AuthUI.getInstance().signOut(this).addOnCompleteListener {
            // 3. Navigate back to the login screen and clear the activity back stack
            val intent = Intent(this, LoginActivity::class.java)
            intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            startActivity(intent)
            finish()
        }
    }
}