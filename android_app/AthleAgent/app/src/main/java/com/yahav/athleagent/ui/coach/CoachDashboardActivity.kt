package com.yahav.athleagent.ui.coach

import android.annotation.SuppressLint
import android.os.Bundle
import android.view.View
import com.yahav.athleagent.utilities.SignalManager
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.google.ai.client.generativeai.GenerativeModel
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import com.yahav.athleagent.databinding.ActivityCoachDashboardBinding
import com.yahav.athleagent.ui.athlete.AthleteAdapter
import androidx.core.content.ContextCompat
import com.yahav.athleagent.R
import androidx.core.graphics.toColorInt
import com.yahav.athleagent.BuildConfig
import com.yahav.athleagent.model.AthleteItem
import android.view.animation.AnimationUtils
import android.widget.TextView
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

import com.yahav.athleagent.network.ApiClient
import com.yahav.athleagent.observability.ClientEventReporter

class CoachDashboardActivity : AppCompatActivity() {

    private lateinit var binding: ActivityCoachDashboardBinding
    private val db = FirebaseFirestore.getInstance()
    private val auth = FirebaseAuth.getInstance()

    private val athleteList = mutableListOf<AthleteItem>()
    private lateinit var adapter: AthleteAdapter

    private val eventReporter = ClientEventReporter(ApiClient.observabilityApi)
    private val geminiApiKey = BuildConfig.GEMINI_API_KEY

    private var typingJob: Job? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityCoachDashboardBinding.inflate(layoutInflater)
        setContentView(binding.root)

        eventReporter.reportEvent("screen_view", "CoachDashboardActivity opened")

        setupRecyclerView()
        loadTeamAthletes()
    }

    private fun setupRecyclerView() {
        adapter = AthleteAdapter(athleteList) { selectedAthlete ->
            showAthleteDetails(selectedAthlete)
        }
        binding.coachDashRVAthletes.layoutManager = LinearLayoutManager(this)
        binding.coachDashRVAthletes.adapter = adapter
    }

    @SuppressLint("NotifyDataSetChanged")
    private fun loadTeamAthletes() {
        val coachUid = auth.currentUser?.uid ?: return

        db.collection("teams").whereEqualTo("coachId", coachUid).get()
            .addOnSuccessListener { teams ->
                if (teams.isEmpty) {
                    SignalManager.getInstance().showSignal(binding.root, "You don't have a team yet.", SignalManager.SignalType.INFO)
                    return@addOnSuccessListener
                }

                val myTeam = teams.documents[0]
                val athleteUids = myTeam.get("athletes") as? List<String> ?: emptyList()

                if (athleteUids.isEmpty()) {
                    SignalManager.getInstance().showSignal(binding.root, "No athletes in your team.", SignalManager.SignalType.INFO)
                    return@addOnSuccessListener
                }

                athleteList.clear()
                athleteUids.forEach { uid ->
                    db.collection("users").document(uid).get()
                        .addOnSuccessListener { userDoc ->
                            val fullName = userDoc.getString("fullName") ?: "Unknown"
                            val firstName = fullName.split(" ").firstOrNull() ?: fullName
                            athleteList.add(AthleteItem(uid, firstName))
                            adapter.notifyDataSetChanged()
                        }
                }
            }
    }

    @SuppressLint("SetTextI18n")
    private fun showAthleteDetails(athlete: AthleteItem) {
        eventReporter.reportEvent("user_action", "Coach viewed athlete details", mapOf("athlete_id" to athlete.uid))

        binding.coachDashLayoutDetails.visibility = View.VISIBLE
        binding.coachDashTXTAthleteName.text = athlete.name

        binding.coachDashPRGRiskScore.progress = 0
        binding.coachDashTXTScore.text = "--%"
        binding.coachDashTXTConfidence.text = "Confidence: --%"
        binding.coachDashTXTAiRecommendation.text = "Loading data..."

        val animation = AnimationUtils.loadAnimation(this, R.anim.anim_card_entrance)
        binding.coachDashCARDHistory.startAnimation(animation)
        binding.coachDashCARDRisk.startAnimation(animation)

        loadAthleteHealthData(athlete.uid)
    }

    @SuppressLint("SetTextI18n")
    private fun loadAthleteHealthData(athleteUid: String) {
        val today = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())

        db.collection("users").document(athleteUid)
            .collection("daily_health").document(today)
            .get()
            .addOnSuccessListener { todayDoc ->
                if (todayDoc.exists() && todayDoc.contains("finalRiskScore")) {
                    val currentRisk = todayDoc.getDouble("finalRiskScore")?.toInt() ?: 0
                    val confidence = todayDoc.getDouble("predictionConfidence")?.toFloat() ?: 0f
                    val aiRec = todayDoc.getString("aiRecommendation")

                    if (!aiRec.isNullOrEmpty()) {
                        updateRiskUI(currentRisk, confidence, aiRec)
                    } else {
                        // aiRecommendation gap solution: generating it dynamically via the coach
                        binding.coachDashTXTAiRecommendation.text = "Generating AI Recommendation..."
                        db.collection("users").document(athleteUid).collection("daily_checkins").document(today).get()
                            .addOnSuccessListener { checkInDoc ->
                                val riskLevel = todayDoc.getString("riskLevel") ?: "Low"
                                val sleepMinutes = todayDoc.getLong("sleepMinutes") ?: 480L
                                val soreness = checkInDoc.getLong("muscleSoreness")?.toInt() ?: 1
                                val stress = checkInDoc.getLong("stressLevel")?.toInt() ?: 20

                                lifecycleScope.launch(Dispatchers.IO) {
                                    fetchAIRecommendationForCoach(
                                        athleteUid, today, currentRisk, confidence, riskLevel, sleepMinutes, soreness, stress
                                    )
                                }
                            }
                    }
                } else {
                    binding.coachDashTXTScore.text = "--%"
                    binding.coachDashTXTConfidence.text = "Confidence: --%"
                    binding.coachDashTXTAiRecommendation.text = "Athlete has not synced data for today yet."
                }
                loadHistoricalChartData(athleteUid)
            }
            .addOnFailureListener {
                binding.coachDashTXTAiRecommendation.text = "Error loading data."
            }
    }

    private suspend fun fetchAIRecommendationForCoach(
        athleteUid: String,
        dateKey: String,
        riskScore: Int,
        confidence: Float,
        riskLevel: String,
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
                updateRiskUI(riskScore, confidence, aiText)
            }

            // Save the recommendation back into the athlete's document
            db.collection("users").document(athleteUid)
                .collection("daily_health").document(dateKey)
                .set(mapOf("aiRecommendation" to aiText), SetOptions.merge())

        } catch (e: Exception) {
            withContext(Dispatchers.Main) {
                binding.coachDashTXTAiRecommendation.text = "AI Doctor is offline."
            }

        }
    }

    private fun loadHistoricalChartData(athleteUid: String) {
        db.collection("users").document(athleteUid)
            .collection("daily_health")
            .get()
            .addOnSuccessListener { documents ->
                if (documents.isEmpty) {
                    binding.coachDashCHARTHistory.clear()
                    return@addOnSuccessListener
                }

                val sortedDocs = documents.documents.sortedBy { it.id }
                val lastSevenDocs = if (sortedDocs.size > 7) {
                    sortedDocs.takeLast(7)
                } else {
                    sortedDocs
                }

                val entries = ArrayList<Entry>()
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
    }

    @SuppressLint("SetTextI18n")
    private fun updateRiskUI(riskScore: Int, confidence: Float, aiRecommendation: String) {
        val (drawableResId, textColorHex) = when (riskScore) {
            in 0..35 -> Pair(R.drawable.progress_drawable_green, "#00F59B")
            in 36..55 -> Pair(R.drawable.progress_drawable_yellow, "#FEEB3B")
            in 56..75 -> Pair(R.drawable.progress_drawable_orange, "#FF9800")
            else -> Pair(R.drawable.progress_drawable_red, "#FF1744")
        }

        binding.coachDashPRGRiskScore.progressDrawable = ContextCompat.getDrawable(this, drawableResId)
        binding.coachDashPRGRiskScore.progress = riskScore

        binding.coachDashTXTScore.text = "$riskScore%"
        binding.coachDashTXTScore.setTextColor(textColorHex.toColorInt())
        binding.coachDashTXTConfidence.text = "Confidence: ${confidence.toInt()}%"

        typeText(binding.coachDashTXTAiRecommendation, aiRecommendation)
    }

    private fun typeText(textView: TextView, fullText: String) {
        typingJob?.cancel()
        textView.text = ""
        typingJob = lifecycleScope.launch {
            for (char in fullText) {
                textView.append(char.toString())
                delay(30)
            }
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

        val chart = binding.coachDashCHARTHistory
        chart.description.isEnabled = false
        chart.legend.isEnabled = false
        chart.axisRight.isEnabled = false
        chart.xAxis.position = XAxis.XAxisPosition.BOTTOM
        chart.xAxis.setDrawGridLines(false)
        chart.axisLeft.setDrawGridLines(true)
        chart.axisLeft.axisMinimum = 0f
        chart.axisLeft.axisMaximum = 100f

        chart.data = LineData(dataSet)
        chart.animateX(800)
        chart.invalidate()
    }
}