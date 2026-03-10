package com.yahav.athleagent.ui.athlete

import android.os.Bundle
import android.util.Log
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.DocumentReference
import com.google.firebase.firestore.FirebaseFirestore
import com.yahav.athleagent.databinding.ActivityJoinTeamBinding

class JoinTeamActivity : AppCompatActivity() {

    private lateinit var binding: ActivityJoinTeamBinding
    private val db = FirebaseFirestore.getInstance()
    private val auth = FirebaseAuth.getInstance()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityJoinTeamBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.joinTeamBTNSubmit.setOnClickListener {
            val code = binding.joinTeamEDTCode.text.toString().trim()
            if (code.isNotEmpty()) {
                searchTeamAndSendRequest(code)
            } else {
                Toast.makeText(this, "Please enter a team code", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun searchTeamAndSendRequest(teamCode: String) {
        binding.joinTeamProgressBar.visibility = View.VISIBLE
        binding.joinTeamBTNSubmit.isEnabled = false

        // Query the "teams" collection to find a match for the entered team code
        db.collection("teams")
            .whereEqualTo("TeamCode", teamCode)
            .get()
            .addOnSuccessListener { documents ->
                if (documents.isEmpty) {
                    binding.joinTeamProgressBar.visibility = View.GONE
                    binding.joinTeamBTNSubmit.isEnabled = true
                    Toast.makeText(this, "Team not found. Check the code.", Toast.LENGTH_LONG).show()
                } else {
                    val teamDoc = documents.documents[0]
                    val teamName = teamDoc.getString("TeamName") ?: "Unknown Team"

                    // Proceed to send the join request using the team's DocumentReference
                    sendJoinRequest(teamDoc.reference, teamName)
                }
            }
            .addOnFailureListener { e ->
                binding.joinTeamProgressBar.visibility = View.GONE
                binding.joinTeamBTNSubmit.isEnabled = true
                Log.e("JoinTeamDebug", "Firebase Query Failed: ", e)
                Toast.makeText(this, "Error connecting to server", Toast.LENGTH_SHORT).show()
            }
    }

    // Constructs the request payload and saves it to the specific team's subcollection
    private fun sendJoinRequest(teamRef: DocumentReference, teamName: String) {
        val currentUser = auth.currentUser
        if (currentUser == null) {
            Toast.makeText(this, "User not logged in", Toast.LENGTH_SHORT).show()
            return
        }

        val requestData = hashMapOf(
            "athleteId" to currentUser.uid,
            "athleteEmail" to currentUser.email,
            "status" to "pending",
            "timestamp" to System.currentTimeMillis()
        )

        // Save the request under the "requests" subcollection of the targeted team
        teamRef.collection("requests").document(currentUser.uid)
            .set(requestData)
            .addOnSuccessListener {
                binding.joinTeamProgressBar.visibility = View.GONE
                Toast.makeText(this, "Request sent to $teamName!", Toast.LENGTH_LONG).show()
                finish()
            }
            .addOnFailureListener {
                binding.joinTeamProgressBar.visibility = View.GONE
                binding.joinTeamBTNSubmit.isEnabled = true
                Toast.makeText(this, "Failed to send request", Toast.LENGTH_SHORT).show()
            }
    }
}