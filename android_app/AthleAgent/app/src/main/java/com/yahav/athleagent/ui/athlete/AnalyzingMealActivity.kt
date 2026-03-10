package com.yahav.athleagent.ui.athlete

import android.content.Intent
import android.graphics.Bitmap
import android.graphics.ImageDecoder
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.MediaStore
import android.util.Log
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.net.toUri
import androidx.lifecycle.lifecycleScope
import com.google.ai.client.generativeai.GenerativeModel
import com.google.ai.client.generativeai.type.content
import com.google.ai.client.generativeai.type.generationConfig
import com.yahav.athleagent.BuildConfig
import com.yahav.athleagent.R
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

class AnalyzingMealActivity : AppCompatActivity() {

    // Gemini API Key
    private val GEMINI_API_KEY = BuildConfig.GEMINI_API_KEY

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_analyzing_meal)

        // Get the image URI passed from the previous screen
        val imageUriString = intent.getStringExtra("IMAGE_URI")

        if (imageUriString != null) {
            val uri = imageUriString.toUri()

            // Convert the URI to a Bitmap so Gemini can process it
            val bitmap = uriToBitmap(uri)

            if (bitmap != null) {
                // Start the AI analysis process
                analyzeImageWithGemini(bitmap, imageUriString)
            } else {
                showErrorAndFinish("Failed to load image.")
            }
        } else {
            showErrorAndFinish("No image received.")
        }
    }

    private fun analyzeImageWithGemini(bitmap: Bitmap, originalUriString: String) {
        // Set temperature to 0.0f for factual, deterministic responses
        val config = generationConfig {
            temperature = 0.0f
        }

        // Initialize the Gemini model
        val generativeModel = GenerativeModel(
            modelName = "gemini-2.5-flash",
            apiKey = GEMINI_API_KEY,
            generationConfig = config
        )

        // Prompt instructing the AI to act as a nutritionist and return only JSON
        val prompt = """
            You are an expert, precise clinical nutritionist. Analyze this meal image.
            Assume standard, average portion sizes for an adult meal unless a scale is obvious.
            Calculate the nutritional values consistently and accurately.
            Return ONLY a valid JSON object with exactly these keys:
            "calories" (integer), "protein" (integer), "carbs" (integer).
            Do not include any markdown formatting like ```json.
        """.trimIndent()

        // Run the network request on a background thread
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val response = generativeModel.generateContent(
                    content {
                        image(bitmap)
                        text(prompt)
                    }
                )

                // Clean up the response to ensure it's a valid JSON string
                val jsonText = response.text?.replace("```json", "")?.replace("```", "")?.trim() ?: "{}"
                Log.d("GeminiAPI", "Response: $jsonText")

                // Extract the nutritional values
                val jsonObject = JSONObject(jsonText)
                val calories = jsonObject.optInt("calories", 0)
                val protein = jsonObject.optInt("protein", 0)
                val carbs = jsonObject.optInt("carbs", 0)

                // Switch back to the main thread to navigate to the results screen
                withContext(Dispatchers.Main) {
                    val intent = Intent(this@AnalyzingMealActivity, MealAnalysisActivity::class.java)
                    intent.putExtra("CALORIES", calories)
                    intent.putExtra("PROTEIN", protein)
                    intent.putExtra("CARBS", carbs)
                    intent.putExtra("IMAGE_URI", originalUriString) // Pass the image forward
                    startActivity(intent)
                    finish() // Close the loading screen
                }

            } catch (e: Exception) {
                Log.e("GeminiAPI", "Error analyzing image", e)
                withContext(Dispatchers.Main) {
                    showErrorAndFinish("AI failed to analyze the image.")
                }
            }
        }
    }

    // Helper function to convert a URI to a Bitmap based on the Android version
    private fun uriToBitmap(uri: Uri): Bitmap? {
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                val source = ImageDecoder.createSource(this.contentResolver, uri)
                ImageDecoder.decodeBitmap(source)
            } else {
                @Suppress("DEPRECATION")
                MediaStore.Images.Media.getBitmap(this.contentResolver, uri)
            }
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }

    // Show an error message and close the activity
    private fun showErrorAndFinish(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
        finish()
    }
}