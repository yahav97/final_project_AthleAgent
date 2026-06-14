package com.yahav.athleagent.ui.coach

import android.os.Bundle
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FirebaseFirestore
import com.yahav.athleagent.databinding.ActivityCreateTeamBinding

class CreateTeamActivity : AppCompatActivity() {

    private lateinit var binding: ActivityCreateTeamBinding
    private val db = FirebaseFirestore.getInstance()
    private val auth = FirebaseAuth.getInstance()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityCreateTeamBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.createTeamBTNSubmit.setOnClickListener {
            attemptCreateTeam()
        }
    }

    private fun attemptCreateTeam() {
        val teamName = binding.createTeamETTeamName.text.toString().trim()
        val teamCode = binding.createTeamETTeamCode.text.toString().trim()

        if (teamName.isEmpty() || teamCode.isEmpty()) {
            Toast.makeText(this, "Please fill in both Team Name and Team Code", Toast.LENGTH_SHORT).show()
            return
        }

        val uid = auth.currentUser?.uid ?: return
        setLoading(true)

        // שלב 1: בודקים אם קוד הקבוצה כבר קיים ב-Firestore
        db.collection("teams").whereEqualTo("teamCode", teamCode).get()
            .addOnSuccessListener { querySnapshot ->
                if (!querySnapshot.isEmpty) {
                    // הקוד כבר תפוס
                    setLoading(false)
                    binding.createTeamTILTeamCode.error = "This code already exists. Choose another."
                } else {
                    // הקוד פנוי, ממשיכים לשלב 2: יצירת הקבוצה
                    binding.createTeamTILTeamCode.error = null
                    createTeamRecord(uid, teamName, teamCode)
                }
            }
            .addOnFailureListener {
                setLoading(false)
                Toast.makeText(this, "Error checking team code availability", Toast.LENGTH_SHORT).show()
            }
    }

    private fun createTeamRecord(coachUid: String, teamName: String, teamCode: String) {
        val newTeam = hashMapOf(
            "TeamName" to teamName,
            "teamCode" to teamCode,
            "coachId" to coachUid,
            "athletes" to emptyList<String>()
        )

        db.collection("teams").add(newTeam)
            .addOnSuccessListener {
                setLoading(false)
                Toast.makeText(this, "Team Created Successfully!", Toast.LENGTH_SHORT).show()
                // סוגרים את המסך וחוזרים אוטומטית למסך הבית
                finish()
            }
            .addOnFailureListener {
                setLoading(false)
                Toast.makeText(this, "Error creating team", Toast.LENGTH_SHORT).show()
            }
    }

    private fun setLoading(isLoading: Boolean) {
        if (isLoading) {
            binding.createTeamBTNSubmit.text = ""
            binding.createTeamProgressBar.visibility = View.VISIBLE
            binding.createTeamBTNSubmit.isEnabled = false
        } else {
            binding.createTeamBTNSubmit.text = "Create Team"
            binding.createTeamProgressBar.visibility = View.GONE
            binding.createTeamBTNSubmit.isEnabled = true
        }
    }
}