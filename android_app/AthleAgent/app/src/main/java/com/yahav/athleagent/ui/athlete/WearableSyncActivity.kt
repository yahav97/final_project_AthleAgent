package com.yahav.athleagent.ui.athlete

import android.graphics.Color
import android.os.Bundle
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import androidx.core.graphics.toColorInt
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.PermissionController
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.*
import androidx.health.connect.client.request.AggregateRequest
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import androidx.lifecycle.lifecycleScope
import com.google.android.material.snackbar.Snackbar
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.firestore.FieldValue
import com.google.firebase.firestore.FirebaseFirestore
import com.google.firebase.firestore.SetOptions
import com.yahav.athleagent.databinding.ActivityWearableSyncBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.time.Duration
import java.time.LocalDateTime
import java.time.ZoneId
import java.util.Calendar
import java.util.Date
import java.util.Locale

import com.yahav.athleagent.network.ApiClient
import com.yahav.athleagent.network.ApiService
import com.yahav.athleagent.observability.ClientEventReporter
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response

@Suppress("SpellCheckingInspection")
class WearableSyncActivity : AppCompatActivity() {
    private lateinit var binding: ActivityWearableSyncBinding
    private lateinit var healthConnectClient: HealthConnectClient

    private val eventReporter = ClientEventReporter(ApiClient.observabilityApi)

    private val permissions = setOf(
        HealthPermission.getReadPermission(SleepSessionRecord::class),
        HealthPermission.getReadPermission(HeartRateRecord::class),
        HealthPermission.getReadPermission(StepsRecord::class),
        HealthPermission.getReadPermission(DistanceRecord::class),
        HealthPermission.getReadPermission(SpeedRecord::class),
        HealthPermission.getReadPermission(ActiveCaloriesBurnedRecord::class),
        HealthPermission.getReadPermission(TotalCaloriesBurnedRecord::class),
        HealthPermission.getReadPermission(BasalMetabolicRateRecord::class),
        HealthPermission.getReadPermission(WeightRecord::class),
        HealthPermission.getReadPermission(HeartRateVariabilityRmssdRecord::class),
        HealthPermission.getReadPermission(RestingHeartRateRecord::class),
        HealthPermission.getReadPermission(OxygenSaturationRecord::class),
        HealthPermission.getReadPermission(Vo2MaxRecord::class),
        HealthPermission.getReadPermission(BodyFatRecord::class),
        HealthPermission.getReadPermission(RespiratoryRateRecord::class),
        HealthPermission.getReadPermission(ElevationGainedRecord::class),
        HealthPermission.getReadPermission(FloorsClimbedRecord::class),
        HealthPermission.getReadPermission(StepsCadenceRecord::class),
        HealthPermission.getReadPermission(ExerciseSessionRecord::class)
    )

    private val requestPermissions = registerForActivityResult(
        PermissionController.createRequestPermissionResultContract()
    ) { granted ->
        if (granted.containsAll(permissions)) {
            startHealthSync()
        } else {
            Snackbar.make(binding.root, "Missing required health permissions.", Snackbar.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityWearableSyncBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.syncBTNSubmit.setOnClickListener {
            checkAndRequestHealthPermissions()
        }
    }

    private fun checkAndRequestHealthPermissions() {
        val availabilityStatus = HealthConnectClient.getSdkStatus(this)
        if (availabilityStatus == HealthConnectClient.SDK_AVAILABLE) {
            healthConnectClient = HealthConnectClient.getOrCreate(this)
            lifecycleScope.launch {
                val granted = healthConnectClient.permissionController.getGrantedPermissions()
                if (granted.containsAll(permissions)) {
                    startHealthSync()
                } else {
                    requestPermissions.launch(permissions)
                }
            }
        } else {
            Snackbar.make(binding.root, "Health Connect is not available.", Snackbar.LENGTH_LONG).show()
        }
    }

    private fun startHealthSync() {
        eventReporter.reportEvent("sync", "Started wearable data sync")
        Snackbar.make(binding.root, "Fetching advanced metrics...", Snackbar.LENGTH_SHORT).show()

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val zoneId = ZoneId.systemDefault()
                val now = LocalDateTime.now()
                val yesterdayStart = now.minusDays(1).withHour(0).withMinute(0).withSecond(0).atZone(zoneId).toInstant()
                val yesterdayEnd = now.minusDays(1).withHour(23).withMinute(59).withSecond(59).atZone(zoneId).toInstant()

                val sleepStart = now.minusDays(1).withHour(18).withMinute(0).atZone(zoneId).toInstant()
                val sleepEnd = now.withHour(12).withMinute(0).atZone(zoneId).toInstant()

                val sleepMinutes = fetchSleepData(sleepStart, sleepEnd)
                val physicalData = fetchPhysicalData(yesterdayStart, yesterdayEnd)

                val userId = FirebaseAuth.getInstance().currentUser?.uid ?: "test_user"

                // חישוב מפתחות התאריכים (היום ואתמול)
                val dateFormat = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault())
                val todayKey = dateFormat.format(Date())

                val cal = Calendar.getInstance()
                cal.add(Calendar.DATE, -1)
                val yesterdayKey = dateFormat.format(cal.time)

                // 1. נתוני שינה להיום בלבד
                val sleepDataToSave = mapOf(
                    "sleepMinutes" to sleepMinutes,
                    "lastSync" to FieldValue.serverTimestamp()
                )

                // 2. נתונים פיזיים של אתמול
                val physicalDataToSave = physicalData.toMutableMap().apply {
                    put("lastSync", FieldValue.serverTimestamp())
                }

                val db = FirebaseFirestore.getInstance()

                // ביצוע שמירה מפוצלת ב-Firestore
                db.collection("users").document(userId)
                    .collection("daily_health").document(todayKey)
                    .set(sleepDataToSave, SetOptions.merge())
                    .addOnSuccessListener {

                        // שמירת נתוני אתמול מתבצעת מיד לאחר הצלחת הראשונה
                        db.collection("users").document(userId)
                            .collection("daily_health").document(yesterdayKey)
                            .set(physicalDataToSave, SetOptions.merge())
                            .addOnSuccessListener {

                                checkAndTriggerPredictionInBackground()

                                lifecycleScope.launch(Dispatchers.Main) {
                                    Snackbar.make(binding.root, "Sync complete!", Snackbar.LENGTH_LONG)
                                        .setBackgroundTint("#3A6578".toColorInt()).show()
                                    delay(1500)
                                    finish()
                                }
                            }
                    }

            } catch (e: Exception) {
                Log.e("Sync", "Error", e)
                withContext(Dispatchers.Main) {
                    Snackbar.make(binding.root, "Sync failed.", Snackbar.LENGTH_SHORT).show()
                }
            }
        }
    }

    private suspend fun fetchSleepData(start: java.time.Instant, end: java.time.Instant): Long {
        val request = ReadRecordsRequest(
            recordType = SleepSessionRecord::class,
            timeRangeFilter = TimeRangeFilter.between(start, end)
        )
        val response = healthConnectClient.readRecords(request)
        return response.records.sumOf { Duration.between(it.startTime, it.endTime).toMinutes() }
    }

    private suspend fun fetchPhysicalData(start: java.time.Instant, end: java.time.Instant): Map<String, Any> {
        val response = healthConnectClient.aggregate(
            AggregateRequest(
                metrics = setOf(
                    StepsRecord.COUNT_TOTAL,
                    DistanceRecord.DISTANCE_TOTAL,
                    ActiveCaloriesBurnedRecord.ACTIVE_CALORIES_TOTAL,
                    TotalCaloriesBurnedRecord.ENERGY_TOTAL,
                    HeartRateRecord.BPM_AVG,
                    HeartRateRecord.BPM_MAX,
                    HeartRateRecord.BPM_MIN,
                    WeightRecord.WEIGHT_AVG,
                    BasalMetabolicRateRecord.BASAL_CALORIES_TOTAL,
                    SpeedRecord.SPEED_AVG,
                    SpeedRecord.SPEED_MAX
                ),
                timeRangeFilter = TimeRangeFilter.between(start, end)
            )
        )

        var hrvRmssd = 0.0
        var spo2 = 0.0
        var vo2Max = 0.0
        var bodyFat = 0.0
        var respRate = 0.0
        var avgCadence = 0.0
        var restingHr = 0
        var elevation = 0.0
        var floors = 0

        try {
            val hrvReq = healthConnectClient.readRecords(ReadRecordsRequest(HeartRateVariabilityRmssdRecord::class, TimeRangeFilter.between(start, end)))
            if (hrvReq.records.isNotEmpty()) hrvRmssd = hrvReq.records.last().heartRateVariabilityMillis

            val spo2Req = healthConnectClient.readRecords(ReadRecordsRequest(OxygenSaturationRecord::class, TimeRangeFilter.between(start, end)))
            if (spo2Req.records.isNotEmpty()) spo2 = spo2Req.records.last().percentage.value

            val vo2Req = healthConnectClient.readRecords(ReadRecordsRequest(Vo2MaxRecord::class, TimeRangeFilter.between(start, end)))
            if (vo2Req.records.isNotEmpty()) vo2Max = vo2Req.records.last().vo2MillilitersPerMinuteKilogram

            val fatReq = healthConnectClient.readRecords(ReadRecordsRequest(BodyFatRecord::class, TimeRangeFilter.between(start, end)))
            if (fatReq.records.isNotEmpty()) bodyFat = fatReq.records.last().percentage.value

            val respReq = healthConnectClient.readRecords(ReadRecordsRequest(RespiratoryRateRecord::class, TimeRangeFilter.between(start, end)))
            if (respReq.records.isNotEmpty()) respRate = respReq.records.last().rate

            val cadenceReq = healthConnectClient.readRecords(ReadRecordsRequest(StepsCadenceRecord::class, TimeRangeFilter.between(start, end)))
            if (cadenceReq.records.isNotEmpty()) {
                val samples = cadenceReq.records.flatMap { it.samples }
                if (samples.isNotEmpty()) avgCadence = samples.map { it.rate }.average()
            }

            val restingReq = healthConnectClient.readRecords(ReadRecordsRequest(RestingHeartRateRecord::class, TimeRangeFilter.between(start, end)))
            if (restingReq.records.isNotEmpty()) restingHr = restingReq.records.last().beatsPerMinute.toInt()

            val elevReq = healthConnectClient.readRecords(ReadRecordsRequest(ElevationGainedRecord::class, TimeRangeFilter.between(start, end)))
            if (elevReq.records.isNotEmpty()) elevation = elevReq.records.sumOf { it.elevation.inMeters }

            val floorReq = healthConnectClient.readRecords(ReadRecordsRequest(FloorsClimbedRecord::class, TimeRangeFilter.between(start, end)))
            if (floorReq.records.isNotEmpty()) floors = floorReq.records.sumOf { it.floors.toInt() }

        } catch (e: Exception) {
            Log.e("Sync", "Fallback read failed for some specialized sensors", e)
        }

        return mapOf(
            "steps" to (response[StepsRecord.COUNT_TOTAL] ?: 0L),
            "distanceMeters" to (response[DistanceRecord.DISTANCE_TOTAL]?.inMeters?.toInt() ?: 0),
            "activeCalories" to (response[ActiveCaloriesBurnedRecord.ACTIVE_CALORIES_TOTAL]?.inKilocalories?.toInt() ?: 0),
            "totalCalories" to (response[TotalCaloriesBurnedRecord.ENERGY_TOTAL]?.inKilocalories?.toInt() ?: 0),
            "heartRateAvg" to (response[HeartRateRecord.BPM_AVG]?.toInt() ?: 0),
            "heartRateMax" to (response[HeartRateRecord.BPM_MAX]?.toInt() ?: 0),
            "heartRateMin" to (response[HeartRateRecord.BPM_MIN]?.toInt() ?: 0),
            "weightKg" to (response[WeightRecord.WEIGHT_AVG]?.inKilograms ?: 0.0),
            "bmrCalories" to (response[BasalMetabolicRateRecord.BASAL_CALORIES_TOTAL]?.inKilocalories?.toInt() ?: 0),

            "restingHeartRate" to restingHr,
            "elevationGainedMeters" to elevation,
            "floorsClimbed" to floors,
            "avgSpeed" to (response[SpeedRecord.SPEED_AVG]?.inMetersPerSecond?.times(3.6) ?: 0.0),
            "maxSpeed" to (response[SpeedRecord.SPEED_MAX]?.inMetersPerSecond?.times(3.6) ?: 0.0),
            "avgCadence" to avgCadence,

            "hrvRmssd" to hrvRmssd,
            "oxygenSaturation" to spo2,
            "vo2Max" to vo2Max,
            "bodyFatPct" to bodyFat,
            "respiratoryRate" to respRate
        )
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

                    // בדיקת התנאים המפוצלים החדשה לפי דרישות צוף
                    val hasTodaySleep = todayHealthDoc.exists() && todayHealthDoc.contains("sleepMinutes")
                    val hasYesterdayPhysical = yesterdayHealthDoc.exists() && yesterdayHealthDoc.contains("steps")
                    val hasTodaySurvey = todayCheckinDoc.exists() && todayCheckinDoc.contains("energyLevel")

                    if (hasTodaySleep && hasYesterdayPhysical && hasTodaySurvey) {
                        Log.d("ML_Trigger", "All parameters verified (Today Sleep + Yesterday Physical + Survey). Triggering prediction.")
                        eventReporter.reportEvent("ml_trigger", "Triggering core prediction with full cross-day context")

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
                                        eventReporter.reportEvent("error", "Prediction API error: ${response.code()}")
                                    }
                                }
                                override fun onFailure(call: Call<ApiService.PredictionResponse>, t: Throwable) {
                                    Log.e("ML_Trigger", "Failed to trigger prediction", t)
                                    eventReporter.reportEvent("error", "Prediction trigger failed: ${t.message}")
                                }
                            })
                    } else {
                        Log.d("ML_Trigger", "Skipping trigger due to missing variables. TodaySleep=$hasTodaySleep, YesterdayPhysical=$hasYesterdayPhysical, TodaySurvey=$hasTodaySurvey")
                    }
                }
            }
        }
    }
}