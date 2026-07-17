package com.yahav.athleagent.ui.athlete

import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.yahav.athleagent.utilities.SignalManager
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FieldValue
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import com.yahav.athleagent.R
import com.yahav.athleagent.databinding.ActivityDailyCheckInBinding
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import androidx.core.graphics.toColorInt
import java.util.Calendar
import com.yahav.athleagent.network.ApiClient
import com.yahav.athleagent.network.ApiService
import com.yahav.athleagent.observability.ClientEventReporter
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response
import android.view.animation.AnimationUtils
import androidx.appcompat.widget.LinearLayoutCompat

class DailyCheckInActivity : AppCompatActivity() {
    private lateinit var binding: ActivityDailyCheckInBinding

    private var selectedSoreness: Int = 3
    private var energyLevel: Float = 60f
    private var stressLevel: Float = 30f
    private var injuredYesterday: Int = 0

    // Event reporter
    private val eventReporter = ClientEventReporter(ApiClient.observabilityApi)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityDailyCheckInBinding.inflate(layoutInflater)
        setContentView(binding.root)

        val entranceAnim = AnimationUtils.loadAnimation(this, R.anim.anim_auth_entrance)
        findViewById<LinearLayoutCompat>(R.id.checkin_form_container).startAnimation(entranceAnim)

        eventReporter.reportEvent("screen_view", "DailyCheckInActivity opened")

        initListeners()
    }

    private fun initListeners() {
        binding.checkinTOGGLESoreness.addOnButtonCheckedListener { _, checkedId, isChecked ->
            if (isChecked) {
                selectedSoreness = when (checkedId) {
                    R.id.checkin_BTN_1 -> 1
                    R.id.checkin_BTN_2 -> 2
                    R.id.checkin_BTN_3 -> 3
                    R.id.checkin_BTN_4 -> 4
                    R.id.checkin_BTN_5 -> 5
                    else -> 3
                }
            }
        }

        binding.checkinSWITCHInjured.setOnCheckedChangeListener { _, isChecked ->
            injuredYesterday = if (isChecked) 1 else 0
        }

        binding.dailyCheckInBTNSubmit.setOnClickListener {
            energyLevel = binding.checkinSLDEnergy.value
            stressLevel = binding.checkinSLDStress.value

            saveCheckInToFirebase()
        }
    }


    private fun saveCheckInToFirebase() {
        SignalManager.getInstance().showSignal(binding.root, "Saving your check-in...", SignalManager.SignalType.INFO)

        val userId = FirebaseAuth.getInstance().currentUser?.uid ?: "test_user_123"
        val today = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())

        val checkInData = hashMapOf(
            "energyLevel" to energyLevel.toInt(),
            "muscleSoreness" to selectedSoreness,
            "stressLevel" to stressLevel.toInt(),
            "injuredYesterday" to injuredYesterday,
            "lastCheckInTime" to FieldValue.serverTimestamp()
        )

        val db = FirebaseFirestore.getInstance()
        db.collection("users").document(userId)
            .collection("daily_checkins").document(today)
            .set(checkInData, SetOptions.merge())
            .addOnSuccessListener {

                eventReporter.reportEvent("user_action", "Daily Check-in submitted")

                SignalManager.getInstance().showSignal(binding.root, "Check-in Saved Successfully!", SignalManager.SignalType.SUCCESS)

                checkAndTriggerPredictionInBackground()

                binding.root.postDelayed({ finish() }, 1500)
            }
            .addOnFailureListener { e ->
                Log.e("DailyCheckIn", "Error saving check-in", e)
                SignalManager.getInstance().showSignal(binding.root, "Failed to save: ${e.message}", SignalManager.SignalType.ERROR)
            }
    }

    private fun checkAndTriggerPredictionInBackground() {
        val userId = FirebaseAuth.getInstance().currentUser?.uid ?: return
        val dateFormat = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())
        val today = dateFormat.format(Date())

        val cal = Calendar.getInstance()
        cal.add(Calendar.DATE, -1)
        val yesterday = dateFormat.format(cal.time)

        val db = FirebaseFirestore.getInstance()

        val todayHealthRef = db.collection("users").document(userId).collection("daily_health").document(today)
        val yesterdayHealthRef = db.collection("users").document(userId).collection("daily_health").document(yesterday)
        val todayCheckinRef = db.collection("users").document(userId).collection("daily_checkins").document(today)

        todayHealthRef.get().addOnSuccessListener { todayHealthDoc ->
            yesterdayHealthRef.get().addOnSuccessListener { yesterdayHealthDoc ->
                todayCheckinRef.get().addOnSuccessListener { todayCheckinDoc ->

                    // Check if the background ML model has already run and saved the result
                    val todaySleep = todayHealthDoc.getLong("sleepMinutes") ?: 0L
                    val yesterdaySteps = yesterdayHealthDoc.getLong("steps") ?: 0L
                    val hasTodaySurvey = todayCheckinDoc.exists() && todayCheckinDoc.contains("energyLevel")

                    // New fix: ensure data is greater than 0 and not empty/misleading
                    if (todaySleep > 0L && yesterdaySteps > 0L && hasTodaySurvey) {
                        Log.d("ML_Trigger", "All parameters verified with valid data. Triggering prediction.")
                        eventReporter.reportEvent("ml_trigger", "Triggering core prediction with verified non-zero data")

                        val startTime = System.currentTimeMillis()
                        val requestData = ApiService.PredictionTriggerRequest(userId, today)

                        ApiClient.apiService.getDailyPrediction(requestData)
                            .enqueue(object : Callback<ApiService.PredictionResponse> {
                                override fun onResponse(call: Call<ApiService.PredictionResponse>, response: Response<ApiService.PredictionResponse>) {
                                    val duration = System.currentTimeMillis() - startTime
                                    if (response.isSuccessful) {
                                        Log.d("ML_Trigger", "Core prediction triggered successfully in ${duration}ms!")
                                        val metadata = mapOf("duration_ms" to duration.toString())
                                        if (duration > 3000) {
                                            eventReporter.reportEvent("ml_performance_warning", "Prediction took over 3 seconds", metadata)
                                        } else {
                                            eventReporter.reportEvent("ml_trigger_success", "Prediction triggered successfully", metadata)
                                        }
                                    } else {
                                        if (response.code() == 503) {
                                            android.widget.Toast.makeText(this@DailyCheckInActivity, "Server is busy, analyzing data in background...", android.widget.Toast.LENGTH_LONG).show()
                                            eventReporter.reportEvent("ml_service_unavailable", "Received 503 from prediction API")
                                        } else {
                                            eventReporter.reportEvent("error", "Prediction API error: ${response.code()}")
                                        }
                                    }
                                }
                                override fun onFailure(call: Call<ApiService.PredictionResponse>, t: Throwable) {
                                    Log.e("ML_Trigger", "Failed to trigger prediction", t)
                                    eventReporter.reportEvent("error", "Prediction trigger failed: ${t.message}")
                                }
                            })
                    } else {
                        Log.d("ML_Trigger", "Skipping trigger: Data contains zero values or missing survey. TodaySleep=$todaySleep, YesterdaySteps=$yesterdaySteps, TodaySurvey=$hasTodaySurvey")
                    }
                }
            }
        }
    }
}