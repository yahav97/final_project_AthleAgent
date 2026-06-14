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
    }

    override fun onResume() {
        super.onResume()
        // מרעננים נתונים כשחוזרים ממסך יצירת הקבוצה
        loadCoachData()
        listenForPendingRequests()
    }

    private fun setupClickListeners() {
        binding.coachHomeCARDNotifications.setOnClickListener {
            startActivity(Intent(this, CoachRequestsActivity::class.java))
        }
        binding.coachHomeBTNManageTeam.setOnClickListener {
            startActivity(Intent(this, CoachRequestsActivity::class.java))
        }
        binding.coachHomeBTNDashboard.setOnClickListener {
            startActivity(Intent(this, CoachDashboardActivity::class.java))
        }
        // המעבר למסך יצירת הקבוצה החדש!
        binding.coachHomeCARDCreateTeamAction.setOnClickListener {
            startActivity(Intent(this, CreateTeamActivity::class.java))
        }
        binding.btnLogout.setOnClickListener {
            performLogout()
        }
    }

    private fun loadCoachData() {
        val uid = auth.currentUser?.uid ?: return

        // טעינת שם המאמן
        db.collection("users").document(uid).get()
            .addOnSuccessListener { document ->
                if (document.exists()) {
                    val coachName = document.getString("fullName") ?: "Coach"
                    binding.coachHomeLBLName.text = coachName
                }
            }

        // בדיקה האם יש קבוצה ועדכון התצוגה של הכרטיסיות
        db.collection("teams").whereEqualTo("coachId", uid).get()
            .addOnSuccessListener { teams ->
                if (!teams.isEmpty) {
                    val teamName = teams.documents[0].getString("TeamName") ?: "Unknown Team"
                    binding.coachHomeLBLTeamName.text = teamName
                    binding.coachHomeLBLTeamName.visibility = View.VISIBLE

                    // יש קבוצה: מציגים דאשבורד וניהול, מסתירים את יצירת הקבוצה
                    binding.coachHomeLAYOUTExistingTeamActions.visibility = View.VISIBLE
                    binding.coachHomeCARDCreateTeamAction.visibility = View.GONE
                } else {
                    // אין קבוצה: מסתירים את שם הקבוצה, דאשבורד וניהול, מציגים את כרטיסיית היצירה
                    binding.coachHomeLBLTeamName.visibility = View.GONE
                    binding.coachHomeLAYOUTExistingTeamActions.visibility = View.GONE
                    binding.coachHomeCARDCreateTeamAction.visibility = View.VISIBLE
                }
            }
    }

    @SuppressLint("SetTextI18n")
    private fun listenForPendingRequests() {
        val uid = auth.currentUser?.uid ?: return

        db.collection("teams").whereEqualTo("coachId", uid).get()
            .addOnSuccessListener { teams ->
                if (!teams.isEmpty) {
                    val teamId = teams.documents[0].id

                    db.collection("teams").document(teamId)
                        .collection("requests")
                        .whereEqualTo("status", "pending")
                        .addSnapshotListener { snapshot, error ->
                            if (error != null) return@addSnapshotListener

                            if (snapshot != null) {
                                val pendingCount = snapshot.size()
                                if (pendingCount > 0) {
                                    binding.coachHomeCARDNotifications.visibility = View.VISIBLE
                                    binding.coachHomeLBLNotifText.text = "You have $pendingCount new athlete join requests!"
                                } else {
                                    binding.coachHomeCARDNotifications.visibility = View.VISIBLE
                                    binding.coachHomeLBLNotifText.text = "No pending requests at the moment."
                                }
                            }
                        }
                } else {
                    binding.coachHomeCARDNotifications.visibility = View.GONE
                }
            }
    }

    private fun performLogout() {
        FirebaseAuth.getInstance().signOut()
        AuthUI.getInstance().signOut(this).addOnCompleteListener {
            val intent = Intent(this, LoginActivity::class.java)
            intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            startActivity(intent)
            finish()
        }
    }
}