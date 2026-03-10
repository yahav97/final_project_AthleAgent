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


class CoachDashboardActivity : AppCompatActivity() {

    private lateinit var binding: ActivityCoachDashboardBinding
    private val db = FirebaseFirestore.getInstance()
    private val auth = FirebaseAuth.getInstance()

    private val athleteList = mutableListOf<AthleteItem>()
    private lateinit var adapter: AthleteAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityCoachDashboardBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupRecyclerView()
        loadTeamAthletes()
    }

    private fun setupRecyclerView() {
        adapter = AthleteAdapter(athleteList) { selectedAthlete ->
            // Handle athlete selection from the list
            showAthleteDetails(selectedAthlete)
        }
        binding.coachDashRVAthletes.layoutManager = LinearLayoutManager(this)
        binding.coachDashRVAthletes.adapter = adapter
    }

    @SuppressLint("NotifyDataSetChanged")
    private fun loadTeamAthletes() {
        val coachUid = auth.currentUser?.uid ?: return

        // Find the coach's team
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

                // Fetch each athlete's name using their UID to display in the list
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
        // Show the details panel
        binding.coachDashLayoutDetails.visibility = View.VISIBLE
        binding.coachDashTXTAthleteName.text = athlete.name

        // Clear previous data from the screen before loading new data
        binding.coachDashPRGRiskScore.progress = 0
        binding.coachDashTXTScore.text = "--%"
        binding.coachDashTXTAiRecommendation.text = "Loading data..."

        loadAthleteHealthData(athlete.uid)
    }

    @SuppressLint("SetTextI18n")
    private fun loadAthleteHealthData(athleteUid: String) {
        // Fetch data without sorting in Firebase to bypass the need for a composite index
        db.collection("users").document(athleteUid)
            .collection("daily_health")
            .get()
            .addOnSuccessListener { documents ->
                if (documents.isEmpty) {
                    binding.coachDashTXTAiRecommendation.text = "No health data available for this athlete yet."
                    binding.coachDashCHARTHistory.clear()
                    return@addOnSuccessListener
                }

                // Sort documents by their ID (date) in ascending order
                val sortedDocs = documents.documents.sortedBy { it.id }

                // The most recent document is now at the end of the list
                val latestDoc = sortedDocs.last()
                val currentRisk = latestDoc.getDouble("finalRiskScore")?.toInt() ?: 0
                val aiRec = latestDoc.getString("aiRecommendation") ?: "recommendation generated today."

                // Update the risk score and AI recommendation
                updateRiskUI(currentRisk, aiRec)

                // Take up to the last 7 days for the chart
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
            .addOnFailureListener {
                binding.coachDashTXTAiRecommendation.text = "Error loading data."
            }
    }

    @SuppressLint("SetTextI18n")
    private fun updateRiskUI(riskScore: Int, aiRecommendation: String) {
        // 1. Determine styling and color based on the risk score range
        val (drawableResId, textColorHex) = when (riskScore) {
            in 0..20 -> Pair(R.drawable.progress_drawable_green, "#388E3C")   // Green
            in 21..50 -> Pair(R.drawable.progress_drawable_yellow, "#E6B300") // Yellow
            in 51..70 -> Pair(R.drawable.progress_drawable_orange, "#F57C00") // Orange
            else -> Pair(R.drawable.progress_drawable_red, "#B71C1C")         // Red
        }

        // 2. Apply the selected drawable to the ProgressBar
        binding.coachDashPRGRiskScore.progressDrawable = ContextCompat.getDrawable(this, drawableResId)

        // 3. Update the progress value (must be done after setting the drawable)
        binding.coachDashPRGRiskScore.progress = riskScore

        // 4. Update the text labels and their corresponding colors
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