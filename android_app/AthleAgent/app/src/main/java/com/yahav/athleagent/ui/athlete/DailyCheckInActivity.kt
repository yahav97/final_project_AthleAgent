package com.yahav.athleagent.ui.athlete

import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.google.android.material.snackbar.Snackbar
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FieldValue
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import com.yahav.athleagent.R
import com.yahav.athleagent.databinding.ActivityDailyCheckInBinding
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import androidx.core.graphics.toColorInt

class DailyCheckInActivity : AppCompatActivity() {
    private lateinit var binding: ActivityDailyCheckInBinding

    // Variables to store the user's selected data
    private var selectedSoreness: Int = 3
    private var energyLevel: Float = 60f
    private var stressLevel: Float = 30f

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityDailyCheckInBinding.inflate(layoutInflater)
        setContentView(binding.root)

        initListeners()
    }

    private fun initListeners() {
        //  Set click listeners for each soreness button separately
        binding.checkinBTN1.setOnClickListener { updateSorenessSelection(1) }
        binding.checkinBTN2.setOnClickListener { updateSorenessSelection(2) }
        binding.checkinBTN3.setOnClickListener { updateSorenessSelection(3) }
        binding.checkinBTN4.setOnClickListener { updateSorenessSelection(4) }
        binding.checkinBTN5.setOnClickListener { updateSorenessSelection(5) }

        //  Save data to Firebase when clicking Submit
        binding.dailyCheckInBTNSubmit.setOnClickListener {
            energyLevel = binding.checkinSLDEnergy.value
            stressLevel = binding.checkinSLDStress.value

            saveCheckInToFirebase()
        }
    }

    // Updates the selected value and properly redraws the button backgrounds
    private fun updateSorenessSelection(score: Int) {
        selectedSoreness = score

        val buttons = listOf(
            binding.checkinBTN1,
            binding.checkinBTN2,
            binding.checkinBTN3,
            binding.checkinBTN4,
            binding.checkinBTN5
        )

        // Create an outlined design (transparent with a colored stroke) for unselected buttons
        val strokeWidthPx = (2 * resources.displayMetrics.density).toInt() // Stroke width
        val cornerRadiusPx = 8f * resources.displayMetrics.density // 8dp as in XML
        val strokeColor = ContextCompat.getColor(this, R.color.brand_button_dark_muted)

        val unselectedBackground = GradientDrawable().apply {
            shape = GradientDrawable.RECTANGLE
            cornerRadius = cornerRadiusPx
            setStroke(strokeWidthPx, strokeColor)
            setColor(Color.TRANSPARENT) // Transparent background
        }

        buttons.forEachIndexed { index, button ->
            if (index + 1 == score) {
                // Selected button: apply gradient background and white text
                button.backgroundTintList = null
                button.setBackgroundResource(R.drawable.btn_gradient)
                button.setTextColor(ContextCompat.getColor(this, R.color.white))
            } else {
                // Unselected button: apply the outlined design created above
                button.backgroundTintList = null
                button.background = unselectedBackground
                button.setTextColor(ContextCompat.getColor(this, R.color.brand_button_dark_muted))
            }
        }
    }

    private fun saveCheckInToFirebase() {
        Snackbar.make(binding.root, "Saving your check-in...", Snackbar.LENGTH_SHORT).show()

        // Prepare the data map
        val userId = FirebaseAuth.getInstance().currentUser?.uid ?: "test_user_123"
        val today = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())

        val checkInData = hashMapOf(
            "energyLevel" to energyLevel.toInt(),
            "muscleSoreness" to selectedSoreness,
            "stressLevel" to stressLevel.toInt(),
            "lastCheckInTime" to FieldValue.serverTimestamp()
        )

        // Save to Firestore
        val db = FirebaseFirestore.getInstance()
        db.collection("users").document(userId)
            .collection("daily_checkins").document(today) // <-- Separate collection here
            .set(checkInData, SetOptions.merge())
            .addOnSuccessListener {
                Snackbar.make(binding.root, "Check-in Saved Successfully!", Snackbar.LENGTH_LONG)
                    .setBackgroundTint("#3A6578".toColorInt())
                    .show()

                // Close the screen shortly after showing the message
                binding.root.postDelayed({ finish() }, 1500)
            }
            .addOnFailureListener { e ->
                Log.e("DailyCheckIn", "Error saving check-in", e)
                Snackbar.make(binding.root, "Failed to save: ${e.message}", Snackbar.LENGTH_LONG)
                    .setBackgroundTint(Color.RED)
                    .show()
            }
    }
}