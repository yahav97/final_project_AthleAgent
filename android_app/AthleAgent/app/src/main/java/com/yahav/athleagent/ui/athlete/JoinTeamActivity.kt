package com.yahav.athleagent.ui.athlete

import android.os.Bundle
import android.util.Log
import android.view.View
import com.yahav.athleagent.utilities.SignalManager
import android.view.animation.AnimationUtils
import com.yahav.athleagent.R
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

        val entranceAnim = AnimationUtils.loadAnimation(this, R.anim.anim_auth_entrance)
        binding.joinTeamFormContainer.startAnimation(entranceAnim)

        binding.joinTeamBTNSubmit.setOnClickListener {
            val code = binding.joinTeamEDTCode.text.toString().trim()
            if (code.isNotEmpty()) {
                searchTeamAndSendRequest(code)
            } else {
                SignalManager.getInstance().showSignal(binding.root, "Please enter a team code", SignalManager.SignalType.INFO)
            }
        }
    }

    private fun searchTeamAndSendRequest(teamCode: String) {
        binding.joinTeamProgressBar.visibility = View.VISIBLE
        binding.joinTeamBTNSubmit.isEnabled = false

        // Query the "teams" collection to find a match for the entered team code
        db.collection("teams")
            .whereEqualTo("teamCode", teamCode)
            .get()
            .addOnSuccessListener { documents ->
                if (documents.isEmpty) {
                    binding.joinTeamProgressBar.visibility = View.GONE
                    binding.joinTeamBTNSubmit.isEnabled = true
                    SignalManager.getInstance().showSignal(binding.root, "Team not found. Check the code.", SignalManager.SignalType.ERROR)
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
                SignalManager.getInstance().showSignal(binding.root, "Error connecting to server", SignalManager.SignalType.ERROR)
            }
    }

    // Constructs the request payload and saves it to the specific team's subcollection
    private fun sendJoinRequest(teamRef: DocumentReference, teamName: String) {
        val currentUser = auth.currentUser
        if (currentUser == null) {
            SignalManager.getInstance().showSignal(binding.root, "User not logged in", SignalManager.SignalType.ERROR)
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
                SignalManager.getInstance().showSignal(binding.root, "Request sent to $teamName!", SignalManager.SignalType.SUCCESS)
                finish()
            }
            .addOnFailureListener {
                binding.joinTeamProgressBar.visibility = View.GONE
                binding.joinTeamBTNSubmit.isEnabled = true
                SignalManager.getInstance().showSignal(binding.root, "Failed to send request", SignalManager.SignalType.ERROR)
            }
    }
}