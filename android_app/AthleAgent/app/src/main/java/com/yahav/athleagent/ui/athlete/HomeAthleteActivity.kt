package com.yahav.athleagent.ui.athlete

//noinspection SuspiciousImport
import android.R
import android.annotation.SuppressLint
import android.content.ContentValues
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.MediaStore
import android.widget.Toast
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import com.yahav.athleagent.databinding.ActivityHomeAthleteBinding
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import androidx.core.graphics.toColorInt
import com.firebase.ui.auth.AuthUI
import com.google.android.gms.tasks.Tasks // Required for Tasks.whenAllComplete
import com.yahav.athleagent.ui.auth.LoginActivity

class HomeAthleteActivity : AppCompatActivity() {

    private lateinit var binding: ActivityHomeAthleteBinding

    // Firebase references
    private val db = FirebaseFirestore.getInstance()
    private val userId by lazy { FirebaseAuth.getInstance().currentUser?.uid ?: "test_user_123" }

    // Variable to store the image path when taking a photo
    private var imageUri: Uri? = null

    // 1. Launcher for picking an image from the gallery
    private val getContentLauncher = registerForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) {
            openAnalyzingActivity(uri.toString())
        } else {
            Toast.makeText(this, "No image selected", Toast.LENGTH_SHORT).show()
        }
    }

    // 2. Launcher for capturing an image with the camera
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
        fetchUserName() // Fetch username when the screen loads
    }

    override fun onResume() {
        super.onResume()
        // Check daily status every time the user returns to the home screen
        checkDailyDataStatus()
    }

    private fun initViews() {
        binding.athleteHomeBTNDashboard.setOnClickListener {
            startActivity(Intent(this, AthleteDashboardActivity::class.java))
        }

        binding.athleteHomeBTNCheckIn.setOnClickListener {
            startActivity(Intent(this, DailyCheckInActivity::class.java))
        }

        // Open image source selection dialog on click
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

    // Shows a dialog to choose between Camera or Gallery
    private fun showImageSourceDialog() {
        val options = arrayOf("Take Photo", "Choose from Gallery")
        MaterialAlertDialogBuilder(this)
            .setTitle("AI Meal Analysis")
            .setItems(options) { _, which ->
                when (which) {
                    0 -> openCamera() // Camera selected
                    1 -> getContentLauncher.launch("image/*") // Gallery selected
                }
            }
            .show()
    }

    // Prepares a temporary file and launches the camera
    private fun openCamera() {
        val values = ContentValues().apply {
            put(MediaStore.Images.Media.TITLE, "New Meal")
            put(MediaStore.Images.Media.DESCRIPTION, "From Camera for AthleAgent")
        }
        imageUri = contentResolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values)
        imageUri?.let { takePictureLauncher.launch(it) }
    }

    // Helper function to navigate to the analysis screen
    private fun openAnalyzingActivity(uriString: String) {
        val intent = Intent(this, AnalyzingMealActivity::class.java)
        intent.putExtra("IMAGE_URI", uriString)
        startActivity(intent)
    }

    // Fetches the user's name from Firebase
    private fun fetchUserName() {
        val currentUser = FirebaseAuth.getInstance().currentUser
        // Attempt to get the display name from Firebase Auth first
        var displayName = currentUser?.displayName

        // Check Firestore for a saved name in the users collection
        db.collection("users").document(userId).get()
            .addOnSuccessListener { document ->
                if (document.exists()) {
                    // Attempt to fetch 'fullName' or 'firstName'
                    val dbName = document.getString("fullName") ?: document.getString("firstName")
                    if (!dbName.isNullOrEmpty()) {
                        displayName = dbName
                    }
                }
                val teamId = document.getString("teamId")
                if (!teamId.isNullOrEmpty()) {
                    db.collection("teams").document(teamId).get().addOnSuccessListener { teamDoc ->
                        val teamName = teamDoc.getString("TeamName") ?: "Unknown Team"
                        binding.athleteHomeLBLTeamName.text = teamName
                    }
                }

                // Update UI: Show the name if found, otherwise default to "Athlete"
                binding.athleteHomeLBLName.text = displayName ?: "Athlete"
            }
            .addOnFailureListener {
                // Fallback to default in case of an error (e.g., no internet)
                binding.athleteHomeLBLName.text = displayName ?: "Athlete"
            }
    }

    // Checks the user's daily data status concurrently
    private fun checkDailyDataStatus() {
        val today = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())

        var hasWearableSync = false
        var hasCheckIn = false
        var hasMeal = false

        // Prepare Firebase queries
        val wearableTask = db.collection("users").document(userId)
            .collection("daily_health").document(today).get()

        val checkinTask = db.collection("users").document(userId)
            .collection("daily_checkins").document(today).get()

        // Note: Ensure the meal collection path matches your database structure
        val mealTask = db.collection("users").document(userId)
            .collection("daily_nutrition").document(today).get()

        // Execute all queries concurrently
        Tasks.whenAllComplete(wearableTask, checkinTask, mealTask)
            .addOnCompleteListener { task ->
                if (task.isSuccessful) {
                    // Check wearable sync result
                    if (wearableTask.isSuccessful && wearableTask.result.exists()) {
                        hasWearableSync = true
                    }
                    // Check daily check-in result
                    if (checkinTask.isSuccessful && checkinTask.result.exists()) {
                        hasCheckIn = true
                    }
                    // Check meal result
                    if (mealTask.isSuccessful && mealTask.result.exists()) {
                        hasMeal = true
                    }

                    // Update the UI only after all data is retrieved
                    updateAlertUI(hasWearableSync, hasCheckIn, hasMeal)
                } else {
                    // On general error (e.g., network issues), default to false
                    updateAlertUI(false, false, false)
                }
            }
    }

    // Updates the UI of the alert card based on missing data
    @SuppressLint("SetTextI18n")
    private fun updateAlertUI(hasWearableSync: Boolean, hasCheckIn: Boolean, hasMeal: Boolean) {
        val missingItems = mutableListOf<String>()

        if (!hasWearableSync) missingItems.add("Wearable Sync")
        if (!hasCheckIn) missingItems.add("Stress Survey")
        if (!hasMeal) missingItems.add("Meal Analysis")

        if (missingItems.isEmpty()) {
            binding.athleteHomeCARDAlert.setCardBackgroundColor("#E8F5E9".toColorInt())
            binding.athleteHomeCARDAlert.strokeColor = "#4CAF50".toColorInt()
            binding.athleteHomeTXTAlertMessage.text = "You're all set for today! Your Risk Score is up to date."
            binding.athleteHomeTXTAlertMessage.setTextColor("#2E7D32".toColorInt())
            binding.athleteHomeIMGAlertIcon.setColorFilter("#4CAF50".toColorInt())
            binding.athleteHomeIMGAlertIcon.setImageResource(R.drawable.ic_dialog_info)
        } else {
            // Missing data - change styling to alert (orange)
            binding.athleteHomeCARDAlert.setCardBackgroundColor("#FFF3E0".toColorInt())
            binding.athleteHomeCARDAlert.strokeColor = "#FFB74D".toColorInt()
            binding.athleteHomeTXTAlertMessage.setTextColor("#E65100".toColorInt())
            binding.athleteHomeIMGAlertIcon.setColorFilter("#F57C00".toColorInt())
            binding.athleteHomeIMGAlertIcon.setImageResource(R.drawable.ic_dialog_alert)

            // Format the missing items text nicely with commas and 'and'
            val missingText = when (missingItems.size) {
                1 -> missingItems[0]
                2 -> "${missingItems[0]} and ${missingItems[1]}"
                else -> "${missingItems[0]}, ${missingItems[1]} and ${missingItems[2]}"
            }

            binding.athleteHomeTXTAlertMessage.text = "Missing data today!\nPlease complete your $missingText."
        }
    }

    private fun performLogout() {
        // 1. Sign out from Firebase Auth (email/password)
        FirebaseAuth.getInstance().signOut()

        // 2. Sign out from Google Auth (allows choosing a different account next time)
        AuthUI.getInstance().signOut(this).addOnCompleteListener {
            // 3. Navigate back to Login and clear the back stack
            val intent = Intent(this, LoginActivity::class.java)
            intent.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK
            startActivity(intent)
            finish()
        }
    }
}