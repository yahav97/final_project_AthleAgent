package com.yahav.athleagent.ui.athlete

import android.annotation.SuppressLint
import android.os.Bundle
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FieldValue
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import com.yahav.athleagent.databinding.ActivityMealAnalysisBinding
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import androidx.core.net.toUri

class MealAnalysisActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMealAnalysisBinding

    // Daily nutritional targets
    private val targetCalories = 2500
    private val targetProtein = 150
    private val targetCarbs = 300

    @SuppressLint("SetTextI18n")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMealAnalysisBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Retrieve data passed from the Gemini API analysis
        val calories = intent.getIntExtra("CALORIES", 0)
        val protein = intent.getIntExtra("PROTEIN", 0)
        val carbs = intent.getIntExtra("CARBS", 0)
        val imageUriString = intent.getStringExtra("IMAGE_URI")

        // Display the captured or selected image
        if (imageUriString != null) {
            binding.mealIMGPhoto.setImageURI(imageUriString.toUri())
        }

        // Display the extracted nutritional values
        binding.mealLBLCalories.text = "$calories kcal"
        binding.mealLBLProtein.text = "${protein}g"
        binding.mealLBLCarbs.text = "${carbs}g"

        // Calculate progress percentages based on daily targets
        val calProgress = ((calories.toFloat() / targetCalories) * 100).toInt()
        val proProgress = ((protein.toFloat() / targetProtein) * 100).toInt()
        val carbProgress = ((carbs.toFloat() / targetCarbs) * 100).toInt()

        binding.mealPRGCalories.progress = calProgress.coerceAtMost(100)
        binding.mealPRGProtein.progress = proProgress.coerceAtMost(100)
        binding.mealPRGCarbs.progress = carbProgress.coerceAtMost(100)

        // Handle the save button click to persist the meal data
        binding.mealBTNSave.setOnClickListener {
            // Disable the button to prevent multiple submissions
            binding.mealBTNSave.isEnabled = false
            saveMealToDatabase(calories, protein, carbs)
        }
    }

    private fun saveMealToDatabase(calories: Int, protein: Int, carbs: Int) {
        val db = FirebaseFirestore.getInstance()
        val userId = FirebaseAuth.getInstance().currentUser?.uid ?: "test_user_123"
        val today = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())

        // 1. Save the specific meal entry as a new document
        val mealData = hashMapOf(
            "calories" to calories,
            "protein" to protein,
            "carbs" to carbs,
            "timestamp" to FieldValue.serverTimestamp()
        )

        db.collection("users").document(userId)
            .collection("daily_nutrition").document(today)
            .collection("meals").add(mealData)
            .addOnSuccessListener {

                // 2. Upon successful save, update the daily aggregated totals
                val dailyNutritionUpdates = hashMapOf(
                    "totalCalories" to FieldValue.increment(calories.toDouble()),
                    "totalProtein" to FieldValue.increment(protein.toDouble()),
                    "totalCarbs" to FieldValue.increment(carbs.toDouble()),
                    "mealsLoggedCount" to FieldValue.increment(1.0),
                    "lastMealAddedAt" to FieldValue.serverTimestamp()
                )

                db.collection("users").document(userId)
                    .collection("daily_nutrition").document(today)
                    .set(dailyNutritionUpdates, SetOptions.merge())
                    .addOnSuccessListener {
                        Toast.makeText(this, "Meal saved successfully!", Toast.LENGTH_SHORT).show()
                        finish() // Close the screen and return to the dashboard
                    }
                    .addOnFailureListener {
                        Toast.makeText(this, "Error updating daily total", Toast.LENGTH_SHORT).show()
                        binding.mealBTNSave.isEnabled = true
                    }
            }
            .addOnFailureListener { e ->
                Toast.makeText(this, "Error saving meal: ${e.message}", Toast.LENGTH_SHORT).show()
                binding.mealBTNSave.isEnabled = true
            }
    }
}