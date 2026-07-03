# Professional Unit Testing Suite Implementation Plan

This plan introduces a robust unit testing infrastructure to AthleAgent, focusing on business logic, data integrity, and API contract validation.

## User Review Required
> [!IMPORTANT]
> I am adding `Mockito` and `Kotlin Coroutines Test` dependencies to the project to enable proper mocking and asynchronous testing.

## Proposed Changes

### 1. Build & Dependencies
Adding industry-standard testing libraries.

#### [libs.versions.toml](file:///C:/FinalProject/final_project_AthleAgent/android_app/AthleAgent/gradle/libs.versions.toml)
- Add `mockito` and `kotlinx-coroutines-test` versions and library definitions.

#### [app/build.gradle.kts](file:///C:/FinalProject/final_project_AthleAgent/android_app/AthleAgent/app/build.gradle.kts)
- Include the new testing dependencies.

---

### 2. Domain & Logic Tests
Testing core data structures and logic.

#### [NEW] [DomainModelTest.kt](file:///C:/FinalProject/final_project_AthleAgent/android_app/AthleAgent/app/src/test/java/com/yahav/athleagent/DomainModelTest.kt)
- Test JSON parsing/serialization logic for `PredictionResponse`.
- Validate data integrity of `AthleteItem` and `AlertItem`.

#### [NEW] [ClientEventReporterTest.kt](file:///C:/FinalProject/final_project_AthleAgent/android_app/AthleAgent/app/src/test/java/com/yahav/athleagent/observability/ClientEventReporterTest.kt)
- Mock the `ObservabilityApi`.
- Verify that `reportEvent` correctly dispatches payloads to the server.
- Test error handling in the reporter.

#### [NEW] [RequestIdHolderTest.kt](file:///C:/FinalProject/final_project_AthleAgent/android_app/AthleAgent/app/src/test/java/com/yahav/athleagent/observability/RequestIdHolderTest.kt)
- Verify UUID generation and persistence during a session.
- Ensure unique IDs are generated upon calling `generateNewId()`.

---

### 3. Utility Upgrades
Creating a central utility class to house testable logic (e.g., risk level formatting, date calculations).

#### [NEW] [CalculationUtils.kt](file:///C:/FinalProject/final_project_AthleAgent/android_app/AthleAgent/app/src/main/java/com/yahav/athleagent/util/CalculationUtils.kt)
- Centralize risk score color logic and text formatting.

#### [NEW] [CalculationUtilsTest.kt](file:///C:/FinalProject/final_project_AthleAgent/android_app/AthleAgent/app/src/test/java/com/yahav/athleagent/util/CalculationUtilsTest.kt)
- Test risk level thresholds (Low, Medium, High).
- Test date key formatting used for Firestore lookups.

## Verification Plan

### Automated Tests
- Run `./gradlew test` to execute the full suite.
- I will provide the output of the test execution in the final walkthrough.
