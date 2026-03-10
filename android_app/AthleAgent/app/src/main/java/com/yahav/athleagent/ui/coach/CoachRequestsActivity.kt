package com.yahav.athleagent.ui.coach

import android.annotation.SuppressLint
import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.FieldValue
import com.yahav.athleagent.model.AthleteRequest
import com.yahav.athleagent.databinding.ActivityCoachRequestsBinding


class CoachRequestsActivity : AppCompatActivity() {

    private lateinit var binding: ActivityCoachRequestsBinding
    private val db = FirebaseFirestore.getInstance()
    private val auth = FirebaseAuth.getInstance()
    private val requestsList = mutableListOf<AthleteRequest>()
    private lateinit var adapter: RequestsAdapter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityCoachRequestsBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupRecyclerView()
        loadPendingRequests()
    }

    private fun setupRecyclerView() {
        adapter = RequestsAdapter(
            requestsList,
            onApproveClick = { request -> approveRequest(request) },
            onRejectClick = { request -> rejectRequest(request) }
        )
        binding.requestsRecyclerView.layoutManager = LinearLayoutManager(this)
        binding.requestsRecyclerView.adapter = adapter
    }

    @SuppressLint("NotifyDataSetChanged")
    private fun loadPendingRequests() {
        binding.requestsProgressBar.visibility = View.VISIBLE
        val coachUid = auth.currentUser?.uid ?: return

        // Find the team managed by this coach
        db.collection("teams").whereEqualTo("coachId", coachUid).get()
            .addOnSuccessListener { teams ->
                if (teams.isEmpty) {
                    showEmptyState()
                    return@addOnSuccessListener
                }

                val myTeam = teams.documents[0]
                val teamId = myTeam.id

                // Fetch pending requests for this team
                myTeam.reference.collection("requests")
                    .whereEqualTo("status", "pending")
                    .get()
                    .addOnSuccessListener { requestsDocs ->
                        requestsList.clear()
                        for (doc in requestsDocs) {
                            val athleteId = doc.getString("athleteId") ?: continue
                            val athleteEmail = doc.getString("athleteEmail") ?: "Unknown"
                            requestsList.add(AthleteRequest(athleteId, athleteEmail, teamId))
                        }

                        binding.requestsProgressBar.visibility = View.GONE
                        if (requestsList.isEmpty()) {
                            showEmptyState()
                        } else {
                            binding.requestsLBLEmpty.visibility = View.GONE
                            adapter.notifyDataSetChanged()
                        }
                    }
                    .addOnFailureListener {
                        showEmptyState()
                    }
            }
    }

    private fun approveRequest(request: AthleteRequest) {
        val requestRef = db.collection("teams").document(request.teamId)
            .collection("requests").document(request.athleteId)

        val teamRef = db.collection("teams").document(request.teamId)
        val athleteRef = db.collection("users").document(request.athleteId)

        // Use a Firestore Batch to approve the request and link the athlete to the team atomically
        db.runBatch { batch ->
            batch.update(requestRef, "status", "approved")
            batch.update(teamRef, "athletes", FieldValue.arrayUnion(request.athleteId))
            batch.update(athleteRef, "teamId", request.teamId)
        }.addOnSuccessListener {
            Toast.makeText(this, "Athlete Approved!", Toast.LENGTH_SHORT).show()
            removeRequestFromList(request)
        }.addOnFailureListener { e ->
            Toast.makeText(this, "Failed to approve: ${e.message}", Toast.LENGTH_SHORT).show()
        }
    }

    private fun rejectRequest(request: AthleteRequest) {
        val requestRef = db.collection("teams").document(request.teamId)
            .collection("requests").document(request.athleteId)

        // On rejection, simply update the request status to rejected
        requestRef.update("status", "rejected")
            .addOnSuccessListener {
                Toast.makeText(this, "Request Rejected", Toast.LENGTH_SHORT).show()
                removeRequestFromList(request)
            }
    }

    private fun removeRequestFromList(request: AthleteRequest) {
        val index = requestsList.indexOf(request)
        if (index != -1) {
            requestsList.removeAt(index)
            adapter.notifyItemRemoved(index)
        }
        if (requestsList.isEmpty()) showEmptyState()
    }

    private fun showEmptyState() {
        binding.requestsProgressBar.visibility = View.GONE
        binding.requestsLBLEmpty.visibility = View.VISIBLE
    }
}