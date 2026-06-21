package com.yahav.athleagent.ui.coach

import android.annotation.SuppressLint
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.github.mikephil.charting.components.XAxis
import com.github.mikephil.charting.data.Entry
import com.github.mikephil.charting.data.LineData
import com.github.mikephil.charting.data.LineDataSet
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import com.yahav.athleagent.databinding.ActivityCoachDashboardBinding
import com.yahav.athleagent.ui.athlete.AthleteAdapter
import androidx.core.content.ContextCompat
import com.yahav.athleagent.R
import androidx.core.graphics.toColorInt
import com.yahav.athleagent.model.AthleteItem
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
                    Toast.makeText(this, "You don't have a team yet.", Toast.LENGTH_SHORT).show()
                    return@addOnSuccessListener
                }

                val myTeam = teams.documents[0]
                val athleteUids = myTeam.get("athletes") as? List<String> ?: emptyList()

                if (athleteUids.isEmpty()) {
                    Toast.makeText(this, "No athletes in your team.", Toast.LENGTH_SHORT).show()
                    return@addOnSuccessListener
                }

                athleteList.clear()
                athleteUids.forEach { uid ->
                    db.collection("users").document(uid).get()
                        .addOnSuccessListener { userDoc ->
                            val name = userDoc.getString("fullName") ?: "Unknown Athlete"
                            athleteList.add(AthleteItem(uid, name))
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
        binding.coachDashTXTAiRecommendation.text = "Loading data..."

        loadAthleteHealthData(athlete.uid)
    }

    @SuppressLint("SetTextI18n")
    private fun loadAthleteHealthData(athleteUid: String) {
        // Find today's specific document first to ensure the coach sees the latest ML prediction
        val today = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())

        db.collection("users").document(athleteUid)
            .collection("daily_health").document(today)
            .get()
            .addOnSuccessListener { todayDoc ->
                if (todayDoc.exists() && todayDoc.contains("finalRiskScore")) {
                    val currentRisk = todayDoc.getDouble("finalRiskScore")?.toInt() ?: 0
                    val aiRec = todayDoc.getString("aiRecommendation") ?: "Recommendation generated today."
                    updateRiskUI(currentRisk, aiRec)
                } else {
                    // fallback to latest available if today is not synced yet
                    binding.coachDashTXTAiRecommendation.text = "Athlete has not synced data for today yet."
                }

                // Then load history for the chart
                loadHistoricalChartData(athleteUid)
            }
            .addOnFailureListener {
                binding.coachDashTXTAiRecommendation.text = "Error loading data."
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
    private fun updateRiskUI(riskScore: Int, aiRecommendation: String) {
        val (drawableResId, textColorHex) = when (riskScore) {
            in 0..20 -> Pair(R.drawable.progress_drawable_green, "#388E3C")
            in 21..50 -> Pair(R.drawable.progress_drawable_yellow, "#E6B300")
            in 51..70 -> Pair(R.drawable.progress_drawable_orange, "#F57C00")
            else -> Pair(R.drawable.progress_drawable_red, "#B71C1C")
        }

        binding.coachDashPRGRiskScore.progressDrawable = ContextCompat.getDrawable(this, drawableResId)
        binding.coachDashPRGRiskScore.progress = riskScore

        binding.coachDashTXTScore.text = "$riskScore%"
        binding.coachDashTXTScore.setTextColor(textColorHex.toColorInt())
        binding.coachDashTXTAiRecommendation.text = " $aiRecommendation"
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