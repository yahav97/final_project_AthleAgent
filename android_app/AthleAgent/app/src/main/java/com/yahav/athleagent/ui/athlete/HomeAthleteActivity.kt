package com.yahav.athleagent.ui.athlete

import android.annotation.SuppressLint
import android.content.ContentValues
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.MediaStore
import android.view.View
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.firebase.ui.auth.AuthUI
import com.google.android.gms.tasks.Tasks
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.tabs.TabLayoutMediator
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import com.yahav.athleagent.R
import com.yahav.athleagent.databinding.ActivityHomeAthleteBinding
import com.yahav.athleagent.model.AlertItem
import com.yahav.athleagent.ui.auth.LoginActivity
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class HomeAthleteActivity : AppCompatActivity() {

    private lateinit var binding: ActivityHomeAthleteBinding

    // Firebase references
    private val db = FirebaseFirestore.getInstance()
    private val userId by lazy { FirebaseAuth.getInstance().currentUser?.uid ?: "test_user_123" }

    private var imageUri: Uri? = null

    private val getContentLauncher = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) {
            openAnalyzingActivity(uri.toString())
        }
    }

    private val takePictureLauncher = registerForActivityResult(ActivityResultContracts.TakePicture()) { success ->
        if (success && imageUri != null) {
            openAnalyzingActivity(imageUri.toString())
        } else {
            Toast.makeText(this, "Camera capture failed or canceled", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        binding = ActivityHomeAthleteBinding.inflate(layoutInflater)
        setContentView(binding.root)

        ViewCompat.setOnApplyWindowInsetsListener(binding.root) { v, insets ->
            val systemBars = insets.getInsets(WindowInsetsCompat.Type.systemBars())
            v.setPadding(systemBars.left, systemBars.top, systemBars.right, systemBars.bottom)
            insets
        }

        initViews()
        fetchUserName()
    }

    override fun onResume() {
        super.onResume()
        checkDailyDataStatus()
    }

    private fun initViews() {
        binding.athleteHomeBTNDashboard.setOnClickListener {
            startActivity(Intent(this, AthleteDashboardActivity::class.java))
        }

        binding.athleteHomeBTNCheckIn.setOnClickListener {
            startActivity(Intent(this, DailyCheckInActivity::class.java))
        }

        binding.athleteHomeBTNNutrition.setOnClickListener {
            showImageSourceDialog()
        }

        binding.athleteHomeBTNSync.setOnClickListener {
            startActivity(Intent(this, WearableSyncActivity::class.java))
        }
        binding.btnJoinTeam.setOnClickListener {
            val intent = Intent(this, JoinTeamActivity::class.java)
            startActivity(intent)
        }
        binding.btnLogout.setOnClickListener {
            performLogout()
        }
    }

    private fun showImageSourceDialog() {
        val options = arrayOf("Take Photo", "Choose from Gallery")
        MaterialAlertDialogBuilder(this)
            .setTitle("AI Meal Analysis")
            .setItems(options) { _, which ->
                when (which) {
                    0 -> openCamera()
                    1 -> getContentLauncher.launch("image/*")
                }
            }
            .show()
    }

    private fun openCamera() {
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.TITLE, "New Meal")
            put(MediaStore.Images.Media.DESCRIPTION, "From Camera for AthleAgent")
        }
        imageUri = contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
        imageUri?.let { takePictureLauncher.launch(it) }
    }

    private fun openAnalyzingActivity(uriString: String) {
        val intent = Intent(this, AnalyzingMealActivity::class.java)
        intent.putExtra("IMAGE_URI", uriString)
        startActivity(intent)
    }

// Fetches the user's name from Firebase
    @SuppressLint("SetTextI18n")
    private fun fetchUserName() {
    val currentUser = FirebaseAuth.getInstance().currentUser
    var displayName = currentUser?.displayName

    db.collection("users").document(userId).get()
        .addOnSuccessListener { document ->
            if (document.exists()) {
                val dbName = document.getString("fullName") ?: document.getString("firstName")
                if (!dbName.isNullOrEmpty()) {
                    displayName = dbName
                }

                val teamId = document.getString("teamId")
                if (!teamId.isNullOrEmpty()) {
                    db.collection("teams").document(teamId).get().addOnSuccessListener { teamDoc ->
                        val teamName = teamDoc.getString("TeamName") ?: "Unknown Team"
                        binding.athleteHomeLBLTeamName.text = teamName

                        binding.athleteHomeLBLTeamName.setCompoundDrawablesRelative(null, null, null, null)
                        binding.athleteHomeLBLTeamName.setOnClickListener(null)
                    }
                } else {
                    binding.athleteHomeLBLTeamName.setOnClickListener {
                        startActivity(Intent(this@HomeAthleteActivity, JoinTeamActivity::class.java))
                    }
                }
            }
            binding.athleteHomeLBLName.text = displayName ?: "Athlete"
        }
        .addOnFailureListener {
            binding.athleteHomeLBLName.text = displayName ?: "Athlete"
        }
}

    private fun checkDailyDataStatus() {
        val today = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())

        var hasWearableSync = false
        var hasCheckIn = false
        var hasMeal = false

        val wearableTask = db.collection("users").document(userId)
            .collection("daily_health").document(today).get()

        val checkinTask = db.collection("users").document(userId)
            .collection("daily_checkins").document(today).get()

        val mealTask = db.collection("users").document(userId)
            .collection("daily_nutrition").document(today).get()

        Tasks.whenAllComplete(wearableTask, checkinTask, mealTask)
            .addOnCompleteListener { task ->
                if (task.isSuccessful) {
                    if (wearableTask.isSuccessful && wearableTask.result.exists()) hasWearableSync = true
                    if (checkinTask.isSuccessful && checkinTask.result.exists()) hasCheckIn = true
                    if (mealTask.isSuccessful && mealTask.result.exists()) hasMeal = true

                    updateAlertUI(hasWearableSync, hasCheckIn, hasMeal)
                } else {
                    updateAlertUI(false, false, false)
                }
            }
    }

    @SuppressLint("SetTextI18n")
    private fun updateAlertUI(hasWearableSync: Boolean, hasCheckIn: Boolean, hasMeal: Boolean) {
        val alertItems = mutableListOf<AlertItem>()

        if (!hasWearableSync) {
            alertItems.add(AlertItem(
                "Missing Wearable Sync.\nTap to sync now.",
                android.R.drawable.ic_popup_sync,
                "#FFF3E0", "#FFB74D", "#E65100", "#F57C00"
            ) { startActivity(Intent(this@HomeAthleteActivity, WearableSyncActivity::class.java)) })
        }

        if (!hasCheckIn) {
            alertItems.add(AlertItem(
                "Missing Stress Survey.\nTap to complete.",
                R.drawable.rounded_assignment_add_24,
                "#FFF3E0", "#FFB74D", "#E65100", "#F57C00"
            ) { startActivity(Intent(this@HomeAthleteActivity, DailyCheckInActivity::class.java)) })
        }

        if (!hasMeal) {
            alertItems.add(AlertItem(
                "Missing Meal Analysis.\nTap to upload.",
                R.drawable.baseline_add_a_photo_24,
                "#FFF3E0", "#FFB74D", "#E65100", "#F57C00"
            ) { showImageSourceDialog() })
        }

        if (alertItems.isEmpty()) {
            alertItems.add(AlertItem(
                "You're all set for today!\nYour Risk Score is up to date.",
                R.drawable.twotone_space_dashboard_24,
                "#E8F5E9", "#4CAF50", "#2E7D32", "#4CAF50"
            ) { startActivity(Intent(this@HomeAthleteActivity, AthleteDashboardActivity::class.java)) })
        }

        val adapter = AlertsAdapter(alertItems)
        binding.athleteHomeVPAlerts.adapter = adapter
        binding.athleteHomeVPAlerts.setPageTransformer(androidx.viewpager2.widget.MarginPageTransformer(50))

        TabLayoutMediator(binding.athleteHomeTABAlerts, binding.athleteHomeVPAlerts) { _, _ -> }.attach()

        if (alertItems.size <= 1) {
            binding.athleteHomeTABAlerts.visibility = View.GONE
        } else {
            binding.athleteHomeTABAlerts.visibility = View.VISIBLE
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