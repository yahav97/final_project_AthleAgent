package com.yahav.athleagent.ui.athlete

import android.annotation.SuppressLint
import android.os.Bundle
import android.util.Log
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

import com.yahav.athleagent.network.ApiClient
import com.yahav.athleagent.network.ApiService
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response

class MealAnalysisActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMealAnalysisBinding

    private val targetCalories = 2500
    private val targetProtein = 150
    private val targetCarbs = 300

    @SuppressLint("SetTextI18n")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMealAnalysisBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val calories = intent.getIntExtra("CALORIES", 0)
        val protein = intent.getIntExtra("PROTEIN", 0)
        val carbs = intent.getIntExtra("CARBS", 0)
        val imageUriString = intent.getStringExtra("IMAGE_URI")

        if (imageUriString != null) {
            binding.mealIMGPhoto.setImageURI(imageUriString.toUri())
        }

        binding.mealLBLCalories.text = "$calories kcal"
        binding.mealLBLProtein.text = "${protein}g"
        binding.mealLBLCarbs.text = "${carbs}g"

        val calProgress = ((calories.toFloat() / targetCalories) * 100).toInt()
        val proProgress = ((protein.toFloat() / targetProtein) * 100).toInt()
        val carbProgress = ((carbs.toFloat() / targetCarbs) * 100).toInt()

        binding.mealPRGCalories.progress = calProgress.coerceAtMost(100)
        binding.mealPRGProtein.progress = proProgress.coerceAtMost(100)
        binding.mealPRGCarbs.progress = carbProgress.coerceAtMost(100)

        binding.mealBTNSave.setOnClickListener {
            binding.mealBTNSave.isEnabled = false
            saveMealToDatabase(calories, protein, carbs)
        }
    }

    private fun saveMealToDatabase(calories: Int, protein: Int, carbs: Int) {
        val db = FirebaseFirestore.getInstance()
        val userId = FirebaseAuth.getInstance().currentUser?.uid ?: "test_user_123"
        val today = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())

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

                        checkAndTriggerPredictionInBackground()

                        finish()
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

    private fun checkAndTriggerPredictionInBackground() {
        val userId = FirebaseAuth.getInstance().currentUser?.uid ?: return
        val today = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())
        val db = FirebaseFirestore.getInstance()

        val healthRef = db.collection("users").document(userId).collection("daily_health").document(today)
        val checkinRef = db.collection("users").document(userId).collection("daily_checkins").document(today)

        // התזונה נשמרה, נבדוק ששני תנאי החובה (שעון + סקר) קיימים לפני שנריץ חיזוי מעודכן
        healthRef.get().addOnSuccessListener { healthDoc ->
            checkinRef.get().addOnSuccessListener { checkinDoc ->

                val hasWatch = healthDoc.exists() && healthDoc.contains("steps")
                val hasSurvey = checkinDoc.exists() && checkinDoc.contains("energyLevel")

                if (hasWatch && hasSurvey) {
                    Log.d("ML_Trigger", "Nutrition added, and both Watch and Survey are present. Triggering full prediction.")

                    val requestData = ApiService.PredictionTriggerRequest(userId, today)
                    ApiClient.apiService.getDailyPrediction(requestData)
                        .enqueue(object : Callback<ApiService.PredictionResponse> {
                            override fun onResponse(call: Call<ApiService.PredictionResponse>, response: Response<ApiService.PredictionResponse>) {
                                if (response.isSuccessful) Log.d("ML_Trigger", "Full dynamic prediction updated successfully!")
                            }
                            override fun onFailure(call: Call<ApiService.PredictionResponse>, t: Throwable) {
                                Log.e("ML_Trigger", "Failed to trigger dynamic prediction", t)
                            }
                        })
                } else {
                    Log.d("ML_Trigger", "Nutrition saved, but core metrics (Watch/Survey) are missing. Skipping trigger.")
                }
            }
        }
    }
}