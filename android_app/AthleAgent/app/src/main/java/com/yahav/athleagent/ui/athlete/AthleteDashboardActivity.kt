package com.yahav.athleagent.ui.athlete

import android.annotation.SuppressLint
import android.os.Bundle
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.google.ai.client.generativeai.GenerativeModel
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import com.yahav.athleagent.databinding.ActivityAthleteDashboardBinding
import com.yahav.athleagent.network.ApiClient
import com.yahav.athleagent.network.ApiService
import com.yahav.athleagent.model.PredictionResponse
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await
import kotlinx.coroutines.withContext
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import androidx.core.graphics.toColorInt
import androidx.core.content.ContextCompat
import com.yahav.athleagent.BuildConfig
import com.yahav.athleagent.R


class AthleteDashboardActivity : AppCompatActivity() {

    private lateinit var binding: ActivityAthleteDashboardBinding
    private val db = FirebaseFirestore.getInstance()
    private val userId by lazy { FirebaseAuth.getInstance().currentUser?.uid ?: "test_user_123" }

    private val GEMINI_API_KEY = BuildConfig.GEMINI_API_KEY

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityAthleteDashboardBinding.inflate(layoutInflater)
        setContentView(binding.root)

        //  Load existing historical data for the chart
        loadHistoricalData()

        //  Calculate today's score from the server
        fetchDataAndSendToBackend()
    }

    private fun fetchDataAndSendToBackend() {
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val today = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())

                val healthDoc = db.collection("users").document(userId)
                    .collection("daily_health").document(today).get().await()
                val checkinDoc = db.collection("users").document(userId)
                    .collection("daily_checkins").document(today).get().await()

                val sleepMinutes = healthDoc.getLong("sleepMinutes") ?: 480L
                val steps = healthDoc.getLong("steps") ?: 5000L
                val soreness = checkinDoc.getLong("muscleSoreness")?.toInt() ?: 1
                val stress = checkinDoc.getLong("stressLevel")?.toInt() ?: 20

                val sleepHours = sleepMinutes / 60.0f
                val distanceKm = (steps * 0.0008).toFloat()

                val athleteDataForServer = ApiService.AthleteData(
                    age = 25, bmi = 22.5f, history_injury_count = 0, vo2_max = 50,
                    daily_distance_km = distanceKm, workout_intensity_minutes = 60,
                    avg_cadence = 160, sleep_hours = sleepHours, hrv_score = 60,
                    resting_hr = 55, daily_calories = 2500, total_calories_burned = 2800,
                    calorie_balance = -300, stress_level = stress, muscle_soreness = soreness,
                    acute_load_7d = 1500f, chronic_load_21d = 1400f, acwr_ratio = 1.07f,
                    sleep_debt_3d = 0.0f, hrv_drop = 0.0f
                )

                sendToPythonBackend(athleteDataForServer, sleepMinutes, soreness, stress)

            } catch (e: Exception) {
                Log.e("Dashboard", "Error loading data", e)
            }
        }
    }

    private fun sendToPythonBackend(data: ApiService.AthleteData, sleepMins: Long, soreness: Int, stress: Int) {
        ApiClient.apiService.getDemoPrediction(data).enqueue(object : Callback<PredictionResponse> {
            override fun onResponse(call: Call<PredictionResponse>, response: Response<PredictionResponse>) {
                if (response.isSuccessful) {
                    val riskScore = response.body()?.risk_percentage?.toInt() ?: 0
                    updateUIWithScore(riskScore)

                    // Save the new score to DB and refresh the chart
                    saveRiskScoreToFirestore(riskScore)

                    lifecycleScope.launch(Dispatchers.IO) {
                        fetchAIRecommendation(riskScore, sleepMins, soreness, stress)
                    }
                }
            }
            override fun onFailure(call: Call<PredictionResponse>, t: Throwable) {
                updateUIWithError("Backend Connection Failed")
            }
        })
    }

    private fun saveRiskScoreToFirestore(score: Int) {
        val today = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())
        val data = mapOf("finalRiskScore" to score)

        db.collection("users").document(userId)
            .collection("daily_health").document(today)
            .set(data, SetOptions.merge())
            .addOnSuccessListener {
                // After saving the new score, reload the chart to see the new point
                loadHistoricalData()
            }
    }

    private fun loadHistoricalData() {
        db.collection("users").document(userId)
            .collection("daily_health")
            .get() // Fetch everything and sort in code to prevent Firebase indexing issues
            .addOnSuccessListener { documents ->
                val entries = ArrayList<Entry>()

                // Convert documents to a list and sort by document name (date)
                val sortedDocs = documents.documents.sortedBy { it.id }

                // Take only the last 7 days
                val lastSevenDocs = if (sortedDocs.size > 7) {
                    sortedDocs.takeLast(7)
                } else {
                    sortedDocs
                }

                var xIndex = 0f
                for (doc in lastSevenDocs) {
                    val score = doc.getDouble("finalRiskScore")?.toFloat()

                    if (score != null) {
                        Log.d("ChartDebug", "Adding entry: Date=${doc.id}, Score=$score at index $xIndex")
                        entries.add(Entry(xIndex, score))
                        xIndex++
                    } else {
                        Log.e("ChartDebug", "Document ${doc.id} found but 'finalRiskScore' is missing or not a number")
                    }
                }

                if (entries.isNotEmpty()) {
                    updateChart(entries)
                } else {
                    Log.w("ChartDebug", "No entries created for the chart. Documents size: ${documents.size()}")
                }
            }
            .addOnFailureListener { e ->
                Log.e("ChartDebug", "Error fetching historical data", e)
            }
    }

    private fun updateChart(entries: List<Entry>) {
        val dataSet = LineDataSet(entries, "Risk Score")
        dataSet.color = "#E65100".toColorInt()
        dataSet.lineWidth = 3f
        dataSet.setDrawCircles(true)
        dataSet.circleRadius = 5f
        dataSet.setCircleColor("#FFA726".toColorInt())
        dataSet.mode = LineDataSet.Mode.CUBIC_BEZIER
        dataSet.setDrawFilled(true)
        dataSet.fillColor = "#FFF3E0".toColorInt()
        dataSet.setDrawValues(false)

        val chart = binding.dashboardCHARTHistory
        chart.description.isEnabled = false
        chart.legend.isEnabled = false
        chart.axisRight.isEnabled = false
        chart.xAxis.position = XAxis.XAxisPosition.BOTTOM
        chart.xAxis.setDrawGridLines(false)
        chart.axisLeft.setDrawGridLines(true)
        chart.axisLeft.axisMinimum = 0f
        chart.axisLeft.axisMaximum = 100f

        chart.data = LineData(dataSet)
        chart.animateX(1000)
        chart.invalidate()
    }

    @SuppressLint("SetTextI18n")
    private fun updateUIWithScore(riskScore: Int) {
        runOnUiThread {
            //  select colors and design based on the score
            val (drawableResId, textColorHex) = when {
                riskScore <= 20 -> Pair(R.drawable.progress_drawable_green, "#388E3C") // Dark green
                riskScore <= 50 -> Pair(R.drawable.progress_drawable_yellow, "#E6B300") // Yellow
                riskScore <= 70 -> Pair(R.drawable.progress_drawable_orange, "#F57C00") // Orange
                else -> Pair(R.drawable.progress_drawable_red, "#B71C1C") // Red
            }

            //  Replace the ProgressBar design!
            binding.dashboardPRGRiskScore.progressDrawable = ContextCompat.getDrawable(this, drawableResId)

            //  *Only now* update the percentage (so the system knows to fill the new design)
            binding.dashboardPRGRiskScore.progress = riskScore

            //  Update the text and its color
            binding.dashboardTXTScore.text = "$riskScore%"
            binding.dashboardTXTScore.setTextColor(textColorHex.toColorInt())
        }
    }

    @SuppressLint("SetTextI18n")
    private fun updateUIWithError(message: String) {
        runOnUiThread {
            binding.dashboardTXTScore.text = "Err"
            binding.dashboardTXTAiRecommendation.text = message
        }
    }


    @SuppressLint("SetTextI18n")
    private suspend fun fetchAIRecommendation(riskScore: Int, sleepMins: Long, soreness: Int, stress: Int) {
        try {
            val generativeModel = GenerativeModel(modelName = "gemini-2.5-flash", apiKey = GEMINI_API_KEY)
            val prompt = """
                You are a senior sports medicine doctor. 
                ML Injury Risk Score: $riskScore%.
                Sleep: ${sleepMins / 60}h ${sleepMins % 60}m, Soreness: $soreness/5, Stress: $stress/100.
                Provide a short 1-sentence recommendation for training today.
                be realistic they are pro athletes who wants to play as much as they can.
            """.trimIndent()

            val response = generativeModel.generateContent(prompt)
            val aiText = response.text ?: "No recommendation available."

            //  Update the athlete's screen
            withContext(Dispatchers.Main) {
                binding.dashboardTXTAiRecommendation.text = aiText
            }

            //  Save the recommendation in the database so the coach can read it!
            val today = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())
            db.collection("users").document(userId)
                .collection("daily_health").document(today)
                .set(mapOf("aiRecommendation" to aiText), SetOptions.merge())

        } catch (e: Exception) {
            withContext(Dispatchers.Main) {
                binding.dashboardTXTAiRecommendation.text = "AI Doctor is offline."
            }
            Log.e("Dashboard", "Error fetching/saving AI recommendation", e)
        }
    }
}