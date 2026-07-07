package com.yahav.athleagent.ui.athlete

import android.annotation.SuppressLint
import android.os.Bundle
import com.yahav.athleagent.utilities.SignalManager
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
import java.util.Calendar
import com.yahav.athleagent.network.ApiClient
import com.yahav.athleagent.observability.ClientEventReporter

class MealAnalysisActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMealAnalysisBinding

    private val targetCalories = 2500
    private val targetProtein = 150
    private val targetCarbs = 300

    private val eventReporter = ClientEventReporter(ApiClient.observabilityApi)

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
        val user = FirebaseAuth.getInstance().currentUser
        val userId = user?.uid ?: "test_user_123"

        val dateFormat = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())
        val todayStr = dateFormat.format(Date()) // שומרים להיום בשביל ה-UI!

        val mealData = hashMapOf(
            "calories" to calories,
            "protein" to protein,
            "carbs" to carbs,
            "timestamp" to FieldValue.serverTimestamp()
        )

        // שומרים את הארוחה במסמך של היום
        db.collection("users").document(userId)
            .collection("daily_nutrition").document(todayStr)
            .collection("meals").add(mealData)
            .addOnSuccessListener {

                val dailyNutritionUpdates = hashMapOf(
                    // שדות מקוריים בשביל ה-UI שלך
                    "totalCalories" to FieldValue.increment(calories.toDouble()),
                    "totalProtein" to FieldValue.increment(protein.toDouble()),
                    "totalCarbs" to FieldValue.increment(carbs.toDouble()),

                    // שדות למודל
                    "calories" to FieldValue.increment(calories.toDouble()),
                    "protein" to FieldValue.increment(protein.toDouble()),
                    "carbs" to FieldValue.increment(carbs.toDouble()),
                    "imputed" to false,
                    "mealsLoggedCount" to FieldValue.increment(1.0),
                    "lastMealAddedAt" to FieldValue.serverTimestamp()
                )

                db.collection("users").document(userId)
                    .collection("daily_nutrition").document(todayStr)
                    .set(dailyNutritionUpdates, SetOptions.merge())
                    .addOnSuccessListener {

                        val creationTime = user?.metadata?.creationTimestamp ?: 0L
                        val isNewUser = (System.currentTimeMillis() - creationTime) < (24 * 60 * 60 * 1000)

                        if (isNewUser) {
                            val cal = Calendar.getInstance()
                            cal.add(Calendar.DATE, -1)
                            val yesterdayStr = dateFormat.format(cal.time)

                            db.collection("users").document(userId)
                                .collection("daily_nutrition").document(yesterdayStr)
                                .set(dailyNutritionUpdates, SetOptions.merge())
                        }

                        eventReporter.reportEvent("user_action", "Meal saved")

                        SignalManager.getInstance().showSignal(binding.root, "Meal saved successfully!", SignalManager.SignalType.SUCCESS)
                        finish()
                    }
                    .addOnFailureListener {
                        SignalManager.getInstance().showSignal(binding.root, "Error updating daily total", SignalManager.SignalType.ERROR)
                        binding.mealBTNSave.isEnabled = true
                    }
            }
            .addOnFailureListener { e ->
                SignalManager.getInstance().showSignal(binding.root, "Error saving meal: ${e.message}", SignalManager.SignalType.ERROR)
                binding.mealBTNSave.isEnabled = true
            }
    }
}