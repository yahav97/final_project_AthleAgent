package com.yahav.athleagent.ui.athlete

import android.graphics.Color
import android.os.Bundle
import android.util.Log
import androidx.appcompat.app.AppCompatActivity
import androidx.core.graphics.toColorInt
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.PermissionController
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.ActiveCaloriesBurnedRecord
import androidx.health.connect.client.records.BasalMetabolicRateRecord
import androidx.health.connect.client.records.DistanceRecord
import androidx.health.connect.client.records.ExerciseSessionRecord
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.SleepSessionRecord
import androidx.health.connect.client.records.SpeedRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.records.TotalCaloriesBurnedRecord
import androidx.health.connect.client.records.WeightRecord
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
import java.time.Instant
import java.time.temporal.ChronoUnit
import java.util.Date
import java.util.Locale

class WearableSyncActivity : AppCompatActivity() {
    private lateinit var binding: ActivityWearableSyncBinding
    private lateinit var healthConnectClient: HealthConnectClient

    // Set of permissions required for the model (organized and deduplicated)
    private val permissions = setOf(
        HealthPermission.getReadPermission(SleepSessionRecord::class),
        HealthPermission.getReadPermission(HeartRateRecord::class),
        HealthPermission.getReadPermission(StepsRecord::class),
        HealthPermission.getReadPermission(DistanceRecord::class),
        HealthPermission.getReadPermission(SpeedRecord::class),
        HealthPermission.getReadPermission(ActiveCaloriesBurnedRecord::class),
        HealthPermission.getReadPermission(ExerciseSessionRecord::class),
        HealthPermission.getReadPermission(TotalCaloriesBurnedRecord::class),
        HealthPermission.getReadPermission(BasalMetabolicRateRecord::class),
        HealthPermission.getReadPermission(WeightRecord::class)
    )

    private val requestPermissions = registerForActivityResult(
        PermissionController.createRequestPermissionResultContract()
    ) { granted ->
        if (granted.containsAll(permissions)) {
            startHealthSync()
        } else {
            Snackbar.make(binding.root, "Permissions required for sync.", Snackbar.LENGTH_LONG).show()
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

    // Main function that manages background synchronization and saves to the database
    private fun startHealthSync() {
        Snackbar.make(binding.root, "Fetching today's metrics...", Snackbar.LENGTH_SHORT).show()

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                //  Fetch data from the wearable/phone
                val sleepMinutes = fetchSleepData()
                val physicalData = fetchPhysicalData()

                //  Prepare the data for saving to Firebase
                val userId = FirebaseAuth.getInstance().currentUser?.uid ?: "test_user_123"
                val today = SimpleDateFormat("yyyy-MM-dd", Locale.getDefault()).format(Date())

                // Pack everything into a single comprehensive map
                val healthDataToSave = hashMapOf<String, Any>(
                    "sleepMinutes" to sleepMinutes,
                    "lastSync" to FieldValue.serverTimestamp() // Timestamp indicating the last synchronization
                )
                healthDataToSave.putAll(physicalData)

                //  Save to Firestore
                val db = FirebaseFirestore.getInstance()
                db.collection("users").document(userId)
                    .collection("daily_health").document(today)
                    // SetOptions.merge() ensures that if synced today, it only updates the data without overwriting other existing fields
                    .set(healthDataToSave, SetOptions.merge())
                    .addOnSuccessListener {
                        lifecycleScope.launch(Dispatchers.Main) {
                            Snackbar.make(binding.root, "Daily data synced successfully!", Snackbar.LENGTH_LONG)
                                .setBackgroundTint("#3A6578".toColorInt())
                                .show()

                            delay(2000)
                            finish()
                        }
                    }
                    .addOnFailureListener { e ->
                        lifecycleScope.launch(Dispatchers.Main) {
                            Snackbar.make(binding.root, "Failed to save: ${e.message}", Snackbar.LENGTH_LONG)
                                .setBackgroundTint(Color.RED)
                                .show()
                        }
                    }

            } catch (e: Exception) {
                Log.e("HealthConnectSync", "Sync failed", e)
                withContext(Dispatchers.Main) {
                    Snackbar.make(binding.root, "Sync failed: ${e.message}", Snackbar.LENGTH_LONG)
                        .setBackgroundTint(Color.RED)
                        .show()
                }
            }
        }
    }

    // The function returns the total sleep duration in minutes (Long)
    private suspend fun fetchSleepData(): Long {
        val endTime = Instant.now()
        val startTime = endTime.minus(24, ChronoUnit.HOURS)
        val request = ReadRecordsRequest(
            recordType = SleepSessionRecord::class,
            timeRangeFilter = TimeRangeFilter.between(startTime, endTime)
        )
        val response = healthConnectClient.readRecords(request)

        var totalSleepMinutes = 0L
        for (record in response.records) {
            totalSleepMinutes += Duration.between(record.startTime, record.endTime).toMinutes()
        }
        return totalSleepMinutes
    }

    // The function retrieves all extended metrics based on the provided requirements
    private suspend fun fetchPhysicalData(): Map<String, Any> {
        val endTime = Instant.now()
        val startTime = endTime.minus(24, ChronoUnit.HOURS)
        val response = healthConnectClient.aggregate(
            AggregateRequest(
                metrics = setOf(
                    StepsRecord.COUNT_TOTAL,
                    DistanceRecord.DISTANCE_TOTAL,
                    ActiveCaloriesBurnedRecord.ACTIVE_CALORIES_TOTAL,
                    TotalCaloriesBurnedRecord.ENERGY_TOTAL, // Total calories (active + resting)
                    HeartRateRecord.BPM_AVG,
                    HeartRateRecord.BPM_MAX, // Maximum heart rate
                    HeartRateRecord.BPM_MIN, // Minimum heart rate
                    WeightRecord.WEIGHT_AVG, // Average weight
                    BasalMetabolicRateRecord.BASAL_CALORIES_TOTAL // Basal metabolic rate (BMR)
                ),
                timeRangeFilter = TimeRangeFilter.between(startTime, endTime)
            )
        )

        // Extract the data and convert it into clean numerical values
        val steps = response[StepsRecord.COUNT_TOTAL] ?: 0L
        val distance = response[DistanceRecord.DISTANCE_TOTAL]?.inMeters ?: 0.0
        val activeCalories = response[ActiveCaloriesBurnedRecord.ACTIVE_CALORIES_TOTAL]?.inKilocalories ?: 0.0
        val totalCalories = response[TotalCaloriesBurnedRecord.ENERGY_TOTAL]?.inKilocalories ?: 0.0
        val avgHr = response[HeartRateRecord.BPM_AVG] ?: 0L
        val maxHr = response[HeartRateRecord.BPM_MAX] ?: 0L
        val minHr = response[HeartRateRecord.BPM_MIN] ?: 0L
        val weight = response[WeightRecord.WEIGHT_AVG]?.inKilograms ?: 0.0
        val bmr = response[BasalMetabolicRateRecord.BASAL_CALORIES_TOTAL]?.inKilocalories ?: 0.0

        // Return the map to be uploaded to Firebase
        return mapOf(
            "steps" to steps,
            "distanceMeters" to distance.toInt(),
            "activeCalories" to activeCalories.toInt(),
            "totalCalories" to totalCalories.toInt(),
            "heartRateAvg" to avgHr,
            "heartRateMax" to maxHr,
            "heartRateMin" to minHr,
            "weightKg" to weight,
            "bmrCalories" to bmr.toInt()
        )
    }
}