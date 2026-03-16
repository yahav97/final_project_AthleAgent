# 🏃‍♂️ AthleAgent

> **Shifting Athlete Care from Reaction to Prevention.**

[![Kotlin](https://img.shields.io/badge/Kotlin-Android-blue.svg)](https://kotlinlang.org/)
[![AI](https://img.shields.io/badge/AI-Gemini_API-orange.svg)](https://deepmind.google/technologies/gemini/)
[![HealthConnect](https://img.shields.io/badge/Integration-Health_Connect-green.svg)](https://developer.android.com/health-and-fitness/guides/health-connect)
[![MachineLearning](https://img.shields.io/badge/Machine_Learning-Predictive_Model-red.svg)](https://tensorflow.org/)

## 📖 Overview
Athlete injuries are complex, resulting from a combination of factors that are traditionally tracked in isolation. **AthleAgent** provides a single, intelligent platform to unify the key pillars of athlete wellness.

By continuously monitoring diverse data points and applying advanced Machine Learning algorithms, AthleAgent shifts the paradigm of sports medicine from reactive treatment to proactive injury prevention, generating a daily "Risk Score" based on real-time data.

## ✨ Core Features

AthleAgent integrates seamlessly into an athlete's daily routine:

* **📊 Daily Check-ins:** Athletes fill out quick physical and psychological surveys to log subjective data such as energy levels, muscle soreness, and current stress levels.
* **🥗 AI Meal Analysis:** Utilizing the Google Gemini Vision API, athletes simply upload an image of their meal. The system automatically extracts nutritional values (Calories, Protein, Carbohydrates) and tracks them against daily targets.
* **⌚ Health Connect Sync:** Seamless integration with the Google Health Connect API to pull objective wearable data automatically, such as live heart rate monitoring and sleep data.
* **🤖 Predictive Risk Modeling:** A custom Machine Learning model analyzes the combined objective and subjective data streams to calculate a highly accurate Daily Injury Risk Score (%), alerting both athletes and coaches *before* an injury occurs.

## 🛠️ Tech Stack
* **Frontend:** Kotlin, Android SDK, Material Design, XML.
* **Backend & Database:** Firebase Authentication, Cloud Firestore.
* **Machine Learning:** Predictive Injury Algorithm (TensorFlow / Scikit-learn).
* **APIs:** Google Health Connect API, Google Gemini Vision API.
* **Architecture:** MVVM (Model-View-ViewModel).

## 🏗️ System Architecture & Workflow

The platform features two distinct user flows managed via **Firebase Authentication**:

### The Athlete Application
* **Onboarding:** Register and send a "Join Team Request" to a specific coach.
* **Data Logging:** Upload meal images, connect to Health Connect, and fill out daily surveys.
* **Monitoring:** View personal AI-driven injury risk, recommendations, and historical data.

### The Coach's Toolkit
* **Team Management:** Create a team, view the athlete list, and approve athlete join requests.
* **Risk Assessment:** Monitor the entire roster's real-time risk scores and historical trends to adjust training loads proactively.

## 🧠 Design Philosophy

Designed specifically for the demands of professional sport, our architecture prioritizes:
* **Usability:** A simple, intuitive interface that minimizes manual data entry.
* **Reliability:** Robust handling of missing data and resilience to external service outages.
* **Supportability:** A modular system architecture that allows for continuous improvement and retraining of the ML model with real-world data over time.
* **Performance:** Optimized for speed and computational efficiency, delivering real-time predictions when they matter most.

## 📱 Screenshots

| Architecture | Workflow | Screens | Athlete View | Coach View |
| :---: | :---: | :---: | :---: | :---: |
| <img src="https://github.com/yahav97/AthleAgent-App/blob/main/assets/archi.png?raw=true" width="200"/> | <img src="https://github.com/yahav97/AthleAgent-App/blob/main/assets/workflow.png?raw=true" width="200"/> | <img src="https://github.com/yahav97/AthleAgent-App/blob/main/assets/screens.png?raw=true" width="200"/> | <img src="https://github.com/yahav97/AthleAgent-App/blob/main/assets/Athlete.png?raw=true" width="200"/> | <img src="https://github.com/yahav97/AthleAgent-App/blob/main/assets/coach.png?raw=true" width="200"/> |

## 🚀 Getting Started

### Prerequisites
* Android Studio (Latest Version)
* Physical Android device (Recommended) with [Health Connect](https://play.google.com/store/apps/details?id=com.google.android.apps.healthdata) installed.
* Google Gemini API Key.
* Firebase Project Setup.

### Installation

1. Clone the repository:
   ```bash
   git clone [https://github.com/yahav97/AthleAgent-App.git](https://github.com/yahav97/AthleAgent-App.git)
   ```
2. Open the project in Android Studio.
3. Add your Gemini API Key to the `local.properties` file:
   ```properties
   GEMINI_API_KEY=your_api_key_here
   ```
4. Obtain a `google-services.json` file from your Firebase console and place it in the `app/` directory.
5. *(If applicable)* Ensure the ML model file is placed in the `app/src/main/assets/` directory.
6. Sync the project with Gradle files and run the application.

## 👨‍💻 Authors
* **Yahav Simon** - [GitHub](https://github.com/yahav97)
* **Tzuf Feldon** 
