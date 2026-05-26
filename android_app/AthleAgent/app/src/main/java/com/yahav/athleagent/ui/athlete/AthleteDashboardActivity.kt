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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
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

    private val geminiApiKey = BuildConfig.GEMINI_API_KEY

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityAthleteDashboardBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // הגרף ההיסטורי נטען פעם אחת ביצירת המסך
        loadHistoricalData()
    }

    override fun onResume() {
        super.onResume()
        // בכל פעם שהמשתמש חוזר למסך הזה, נבדוק אם יש חיזוי חדש בפיירבייס
        loadTodayPredictionFromFirestore()
    }

    private fun loadTodayPredictionFromFirestore() {
        val today = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())

        val healthRef = db.collection("users").document(userId).collection("daily_health").document(today)
        val checkinRef = db.collection("users").document(userId).collection("daily_checkins").document(today)

        healthRef.get().addOnSuccessListener { healthDoc ->
            checkinRef.get().addOnSuccessListener { checkInDoc ->

                // האם המודל ברקע כבר רץ ושמר את התוצאה?
                if (healthDoc.exists() && healthDoc.contains("finalRiskScore")) {

                    // 1. חילוץ התוצאות שהמודל השאיר לנו
                    val riskScore = healthDoc.getDouble("finalRiskScore")?.toInt() ?: 0
                    val riskLevel = healthDoc.getString("riskLevel") ?: "Low"
                    val confidence = healthDoc.getDouble("predictionConfidence")?.toFloat() ?: 0f

                    // 2. עדכון חוגת האחוזים ב-UI
                    updateUIWithScore(riskScore)

                    // 3. חילוץ נתונים קיימים כדי לתת קונטקסט ל-Gemini
                    val sleepMinutes = healthDoc.getLong("sleepMinutes") ?: 480L
                    val soreness = checkInDoc.getLong("muscleSoreness")?.toInt() ?: 1
                    val stress = checkInDoc.getLong("stressLevel")?.toInt() ?: 20

                    // 4. קריאה לג'מיני לייצור המלצה מילולית
                    lifecycleScope.launch(Dispatchers.IO) {
                        fetchAIRecommendation(
                            riskScore,
                            riskLevel,
                            confidence,
                            sleepMinutes,
                            soreness,
                            stress
                        )
                    }
                } else {
                    // המשתמש עדיין לא ביצע סנכרון שעון או סקר היום
                    updateUIWithMissingDataState()
                }
            }
        }.addOnFailureListener { e ->
            Log.e("Dashboard", "Error fetching prediction from DB", e)
            updateUIWithError("Failed to load dashboard data.")
        }
    }

    private fun loadHistoricalData() {
        db.collection("users").document(userId)
            .collection("daily_health")
            .get()
            .addOnSuccessListener { documents ->
                val entries = ArrayList<Entry>()
                val sortedDocs = documents.documents.sortedBy { it.id }

                val lastSevenDocs = if (sortedDocs.size > 7) {
                    sortedDocs.takeLast(7)
                } else {
                    sortedDocs
                }

                var xIndex = 0f
                for (doc in lastSevenDocs) {
                    val score = doc.getDouble("finalRiskScore")?.toFloat()
                    if (score != null) {
                        entries.add(Entry(xIndex, score))
                        xIndex++
                    }
                }

                if (entries.isNotEmpty()) {
                    updateChart(entries)
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
            val (drawableResId, textColorHex) = when {
                riskScore <= 20 -> Pair(R.drawable.progress_drawable_green, "#388E3C")
                riskScore <= 50 -> Pair(R.drawable.progress_drawable_yellow, "#E6B300")
                riskScore <= 70 -> Pair(R.drawable.progress_drawable_orange, "#F57C00")
                else -> Pair(R.drawable.progress_drawable_red, "#B71C1C")
            }

            binding.dashboardPRGRiskScore.progressDrawable = ContextCompat.getDrawable(this, drawableResId)
            binding.dashboardPRGRiskScore.progress = riskScore
            binding.dashboardTXTScore.text = "$riskScore%"
            binding.dashboardTXTScore.setTextColor(textColorHex.toColorInt())
        }
    }

    @SuppressLint("SetTextI18n")
    private fun updateUIWithMissingDataState() {
        runOnUiThread {
            binding.dashboardPRGRiskScore.progressDrawable = ContextCompat.getDrawable(this, R.drawable.progress_drawable_green)
            binding.dashboardPRGRiskScore.progress = 0
            binding.dashboardTXTScore.text = "--%"
            binding.dashboardTXTScore.setTextColor("#9E9E9E".toColorInt()) // Gray color

            binding.dashboardTXTAiRecommendation.text = "Pending: Please complete today's Stress Survey and Watch Sync to generate your Injury Risk Score."
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
    private suspend fun fetchAIRecommendation(
        riskScore: Int,
        riskLevel: String,
        confidence: Float,
        sleepMins: Long,
        soreness: Int,
        stress: Int
    ) {
        try {
            val generativeModel = GenerativeModel(modelName = "gemini-2.5-flash", apiKey = geminiApiKey)

            val prompt = """
                You are a senior sports medicine doctor. 
                ML Injury Risk Score: $riskScore% (Risk Level: $riskLevel, AI Confidence: $confidence%).
                Sleep: ${sleepMins / 60}h ${sleepMins % 60}m, Soreness: $soreness/5, Stress: $stress/100.
                Provide a short 1-sentence recommendation for training today.
                be realistic they are pro athletes who wants to play as much as they can.
            """.trimIndent()

            val response = generativeModel.generateContent(prompt)
            val aiText = response.text ?: "No recommendation available."

            withContext(Dispatchers.Main) {
                binding.dashboardTXTAiRecommendation.text = aiText
            }

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