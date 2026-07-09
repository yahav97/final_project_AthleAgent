# AthleAgent — סקירת קוד פרונטאנד (Android)


| שדה               | ערך                                                                 |
| ----------------- | ------------------------------------------------------------------- |
| **גרסה**          | 1.1                                                                 |
| **תאריך**         | 2026-07-09                                                          |
| **קהל יעד**       | מפתחי Android, בוחני פרויקט גמר, reviewers                          |
| **היקף**          | `android_app/AthleAgent` בלבד — ללא Backend / ML                    |
| **מסמכים קשורים** | [HLD_PROJECT.md](HLD_PROJECT.md) · [LLD_PROJECT.md](LLD_PROJECT.md) · [NFR.md](NFR.md) · [LOGGING_HE.md](LOGGING_HE.md) |


---

## 1. תקציר מנהלים

הפרונטאנד של AthleAgent הוא אפליקציית **Android ב-Kotlin** עם ארכיטקטורה **Activity-centric**: כל מסך הוא `AppCompatActivity` שמדבר ישירות עם Firebase Firestore, Retrofit ו-Gemini.

**חוזקות:** UI מלוטש עם `SignalManager`, זרימות athlete/coach ברורות, שילוב Health Connect ו-Gemini Vision, שכבת observability בסיסית (correlation ID, client events).

**חולשות עיקריות:** מפתחות API בצד הלקוח, fallbacks ל-UID מזויף, memory leaks ב-`onResume`, כפילויות לוגיקה, כיסוי בדיקות דל, **קבצים ארוכים עם יותר מדי אחריות**, ו**חוסר שכבת domain**.

| הערכה              | ציון | הערה                                      |
| ------------------ | ---- | ----------------------------------------- |
| פרויקט גמר / דמו   | 7/10 | זרימות שלמות, אינטגרציות מרשימות          |
| מוכנות לפרודקשן    | 4/10 | P0 באבטחה ו-stability, בדיקות לא מספיקות |
| מבנה קוד וארגון    | 5/10 | God Activities, כפילויות, חוסר שכבות    |

---

## 2. היקף הסקירה

### 2.1 קבצים שנבדקו

| קטגוריה | נתיב |
| ------- | ---- |
| Activities — Athlete | `ui/athlete/*.kt` (9 קבצים) |
| Activities — Coach | `ui/coach/*.kt` (5 קבצים) |
| Activities — Auth | `ui/auth/*.kt` (3 קבצים) |
| אחר | `ui/PrivacyPolicyActivity.kt`, `App.kt` |
| רשת | `network/ApiClient.kt`, `network/ApiService.kt` |
| מודלים | `model/*.kt` |
| כלים | `util/CalculationUtils.kt`, `utilities/SignalManager.kt`, `logic/LoginManager.kt` |
| Observability | `observability/*.kt` (4 קבצים) |
| תצורה | `AndroidManifest.xml`, `app/build.gradle.kts`, `network_security_config.xml` |
| בדיקות | `app/src/test/**`, `app/src/androidTest/**` |

**סה"כ:** 32 קבצי Kotlin ב-`main`, layouts רלוונטיים, 5 קבצי test.

### 2.2 מה לא נכלל

- Backend (`backend/`)
- מודל ML (`ML_model/`)
- Firestore Security Rules (לא נמצאו בתוך מודול Android)
- עיצוב ויזואלי מפורט (רק UX לוגי)

---

## 3. ארכיטקטורה

### 3.1 מבנה שכבות (כפי שמומש)

```
┌──────────────────────────────────────────────────────┐
│  Activity (UI + Business Logic + State)              │
│    ├── View Binding                                  │
│    ├── Firebase Firestore (קריאה/כתיבה ישירה)        │
│    ├── Retrofit ApiClient (POST /predict/daily)      │
│    └── Gemini GenerativeModel (Vision + טקסט)        │
└──────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
    Firestore            FastAPI Backend         Google Gemini
```

**אין:** ViewModel, Repository, Dependency Injection, Navigation Component.

### 3.2 מה עובד טוב

| נושא | פירוט |
| ---- | ----- |
| הפרדת תפקידים | תיקיות `ui/athlete/` ו-`ui/coach/` |
| View Binding | מופעל ומשמש ברוב המסכים |
| APIs מודרניים | Activity Result contracts, edge-to-edge, coroutines |
| Feedback למשתמש | `SignalManager` — snackbar אחיד (success/error/info) |
| Observability | `CorrelationIdInterceptor`, `ClientEventReporter`, Timber ב-`App.kt` |
| מסמכי README | הארכיטקטורה מתועדת ב-`README.md` |

### 3.3 חולשות ארכיטקטוניות

| חומרה | ממצא | מיקום |
| ----- | ---- | ----- |
| P2 | לוגיקת `checkAndTriggerPredictionInBackground()` מועתקת פעמיים | `DailyCheckInActivity.kt`, `WearableSyncActivity.kt` |
| P2 | `CalculationUtils.getRiskLevel()` קיים אך thresholds מוכפלים inline ב-UI | `util/CalculationUtils.kt` |
| P2 | `CalculationUtils.isTeamCodeValid()` קיים אך לא בשימוש | `CreateTeamActivity.kt`, `JoinTeamActivity.kt` |
| P2 | `model/PredictionModels.kt` מת — לא מיובא בשום מקום | `model/PredictionModels.kt` |
| P2 | `PredictionResponse` כפול — גם ב-`ApiService.kt` | `network/ApiService.kt` |
| P2 | `MainActivity` מממש routing אך אינו launcher | `ui/auth/MainActivity.kt`, `AndroidManifest.xml` |
| P3 | חוסר עקביות: `util/` מול `utilities/` | `util/`, `utilities/` |
| P3 | `requestsAdapter.kt` — שם קובץ לא תקני ב-Kotlin | `ui/coach/requestsAdapter.kt` |
| P3 | Adapters משתמשים ב-`findViewById` במקום View Binding | `AthleteAdapter.kt`, `requestsAdapter.kt` |

---

## 4. ממצאים לפי חומרה

### 4.1 P0 — קריטי (חייב תיקון לפני פרודקשן)

| # | ממצא | קובץ | שורות | השפעה |
| - | ---- | ---- | ----- | ----- |
| 1 | **מפתח Gemini ב-BuildConfig** — ניתן לחילוץ מ-APK | `app/build.gradle.kts` | 32–33 | גניבת מפתח, שימוש לרעה, עלויות |
| 2 | שימוש במפתח מה-client | `AnalyzingMealActivity.kt` | 28, 61–64 | אותה בעיה |
| 3 | שימוש במפתח מה-client | `AthleteDashboardActivity.kt` | 38, 247 | אותה בעיה |
| 4 | שימוש במפתח מה-client | `CoachDashboardActivity.kt` | 49, 178 | אותה בעיה |
| 5 | **הזרקת דמו נסתרת** — long-press על כפתור sync מזריק 7 ימים של נתוני בריאות + risk scores מזויפים ל-Firestore | `WearableSyncActivity.kt` | 89–92, 96–177 | נתונים מזויפים בפרודקשן |
| 6 | Fallback ל-UID `"test_user_123"` כשאין משתמש מחובר | `HomeAthleteActivity.kt` | 40 | כתיבה/קריאה לנתיב Firestore שגוי |
| 7 | אותו fallback | `AthleteDashboardActivity.kt` | 36 | אותה בעיה |
| 8 | אותו fallback | `DailyCheckInActivity.kt` | 84 | אותה בעיה |
| 9 | אותו fallback | `MealAnalysisActivity.kt` | 65 | אותה בעיה |
| 10 | Fallback ל-`"test_user"` (שם שונה!) | `WearableSyncActivity.kt` | 213 | חוסר עקביות + נתיב שגוי |
| 11 | `injuryStr.toInt()` ללא ולידציה — קלט לא מספרי גורם ל-`NumberFormatException` | `LoginActivity.kt` | 207 | קריסת אפליקציה |
| 12 | אותה בעיה | `RegisterActivity.kt` | 96 | קריסת אפליקציה |

### 4.2 P1 — גבוה

#### אבטחה ורשת

| # | ממצא | קובץ | שורות |
| - | ---- | ---- | ----- |
| 1 | Backend ללא אימות — רק `X-Request-ID`, ללא Firebase ID token | `ApiClient.kt`, `CorrelationIdInterceptor.kt` | — |
| 2 | URL קשיח `http://10.0.2.2:8000/` — עובד רק באמולטור | `ApiClient.kt` | 10 |
| 3 | Cleartext HTTP מותר במפורש | `network_security_config.xml` | 3–5 |
| 4 | `android:allowBackup="true"` עם נתוני בריאות רגישים | `AndroidManifest.xml` | 33 |
| 5 | כתיבות Firestore מה-client (בריאות, קבוצות, אישורים) — תלוי ב-Security Rules חיצוניים | מספר Activities | — |
| 6 | מסך Privacy Policy ריק — נדרש ל-Health Connect rationale | `PrivacyPolicyActivity.kt`, `activity_privacy_policy_activity.xml` | — |

#### Lifecycle ו-memory leaks

| # | ממצא | קובץ | שורות |
| - | ---- | ---- | ----- |
| 7 | `addSnapshotListener` חדש בכל `onResume` ללא הסרה | `HomeCoachActivity.kt` | 46–51, 105–134 |
| 8 | `TabLayoutMediator` חדש בכל `checkDailyDataStatus()` ללא `detach` | `HomeAthleteActivity.kt` | 240, 284 |

#### באגים ו-UX

| # | ממצא | קובץ | שורות |
| - | ---- | ---- | ----- |
| 9 | `MainActivity` — כשל Firestore משאיר משתמש על splash ריק | `MainActivity.kt` | 76–78 |
| 10 | `showErrorAndFinish()` קורא `finish()` מיד אחרי snackbar — המשתמש לא רואה שגיאה | `AnalyzingMealActivity.kt` | 134–137 |
| 11 | Google Sign-In כושל/מבוטל — ללא הודעה למשתמש | `LoginActivity.kt` | 150–153 |
| 12 | כתיבות Firestore פנימיות ב-sync ללא `addOnFailureListener` | `WearableSyncActivity.kt` | 237–256 |
| 13 | פרסור JSON מ-Gemini עם `optInt` default 0 — תוצאות תזונה אפס בשקט | `AnalyzingMealActivity.kt` | 92–95 |

#### ביצועים

| # | ממצא | קובץ | שורות |
| - | ---- | ---- | ----- |
| 14 | פענוח bitmap במלוא הרזולוציה — סיכון OOM | `AnalyzingMealActivity.kt` | 118–130 |
| 15 | N+1 קריאות Firestore בטעינת roster | `CoachDashboardActivity.kt` | 92–99 |

#### בדיקות

| # | ממצא | קובץ | שורות |
| - | ---- | ---- | ----- |
| 16 | `CalculationUtilsTest` מצפה `getRiskLevel(35) == "Medium"` אך הקוד מחזיר `"Low"` | `CalculationUtilsTest.kt` / `CalculationUtils.kt` | 15 / 14 |

### 4.3 P2 — בינוני

| # | ממצא | קובץ | שורות |
| - | ---- | ---- | ----- |
| 1 | לוגיקת ML trigger מועתקת | `DailyCheckInActivity.kt`, `WearableSyncActivity.kt` | 115–174, 367–426 |
| 2 | תאריך לידה נשמר מ-`selectedBirthDate` ולא משדה הטקסט | `RegisterActivity.kt` | 74, 104 |
| 3 | אותה בעיה ב-Google sign-in flow | `LoginActivity.kt` | 208 |
| 4 | `updateUIWithMissingDataState()` מוגדר אך לא נקרא | `AthleteDashboardActivity.kt` | 206–216 |
| 5 | `ClientEventReporter` — `CoroutineScope(Dispatchers.IO)` ללא ביטול | `ClientEventReporter.kt` | 10 |
| 6 | Retrofit `enqueue()` ו-callbacks של Firestore לא מבוטלים ב-lifecycle | `DailyCheckInActivity.kt`, `WearableSyncActivity.kt` | 147–167, 237–256 |
| 7 | `RequestIdHolder.generateNewId()` לא נקרא בתחילת session | `RequestIdHolder.kt` | 13–16 |
| 8 | `CreateTeamActivity` — אין ולידציה לפורמט קוד קבוצה; מאמן יכול ליצור כמה קבוצות | `CreateTeamActivity.kt` | 32–82 |
| 9 | `JoinTeamActivity` — `.set()` עם UID כ-doc ID דורס בקשה קיימת | `JoinTeamActivity.kt` | 84–85 |
| 10 | יעדי תזונה קשיחים (2500 kcal, 150g חלבון, 300g פחמימות) | `MealAnalysisActivity.kt` | 23–25 |
| 11 | Coach dashboard — "AI Doctor is offline" ללא retry | `CoachDashboardActivity.kt` | 114, 199–202 |
| 12 | `PrivacyPolicyActivity` מוגדר `exported="true"` | `AndroidManifest.xml` | 94–100 |
| 13 | אין ולידציה לחוזק סיסמה / פורמט אימייל | `RegisterActivity.kt`, `LoginManager.kt` | — |
| 14 | `isMinifyEnabled = false` ב-release | `app/build.gradle.kts` | 37–38 |
| 15 | `SignalManager.contextRef` נשמר אך לא בשימוש | `utilities/SignalManager.kt` | 16 |

### 4.4 P3 — נמוך

| # | ממצא | קובץ | שורות |
| - | ---- | ---- | ----- |
| 1 | Timber רק ב-DEBUG — אין crash reporting ב-release | `App.kt` | 11–13 |
| 2 | `notifyItemChanged(NO_POSITION)` בקצה | `AthleteAdapter.kt` | 54 |
| 3 | Imports לא בשימוש | `DailyCheckInActivity.kt` | 3–8 |
| 4 | Import `Log` לא בשימוש | `HomeCoachActivity.kt` | 6 |
| 5 | הערה לא פורמלית בקוד | `ApiClient.kt` | 28 |
| 6 | אנימציית הקלדה (`delay(30)` לתו) על טקסט AI ארוך | `AthleteDashboardActivity.kt`, `CoachDashboardActivity.kt` | 226–234, 260–268 |
| 7 | `AlertItem` מכיל `onClick` lambda — מונע equality יציבה | `model/AlertItem.kt` | 10 |
| 8 | `enableEdgeToEdge()` לא אחיד בכל המסכים | מספר Activities | — |
| 9 | הערות מעורבות עברית/אנגלית | `MealAnalysisActivity.kt`, `WearableSyncActivity.kt` | — |
| 10 | כרטיס התראות תמיד גלוי גם כש-"No pending requests" | `HomeCoachActivity.kt` | 125–126 |
| 11 | PII (אימייל, מדדי בריאות) נשלח ל-Gemini מה-client ללא consent מפורש | Dashboard + meal activities | — |

---

## 5. אבטחה — פירוט

### 5.1 מפתחות API בצד הלקוח

```kotlin
// app/build.gradle.kts
buildConfigField("String", "GEMINI_API_KEY", "\"$apiKey\"")

// AnalyzingMealActivity.kt
private val GEMINI_API_KEY = BuildConfig.GEMINI_API_KEY
```

**סיכון:** חילוץ מפתח מ-APK (גם עם obfuscation — `isMinifyEnabled = false`).

**המלצה (לעתיד):** proxy דרך Backend; הלקוח שולח תמונה לשרת, השרת קורא ל-Gemini.

### 5.2 תקשורת עם Backend

| נושא | מצב נוכחי |
| ---- | --------- |
| Base URL | `http://10.0.2.2:8000/` (אמולטור בלבד) |
| אימות | אין — רק `X-Request-ID` |
| הצפנה | Cleartext HTTP מותר |

### 5.3 נתונים רגישים

| נושא | מצב |
| ---- | --- |
| גיבוי אפליקציה | `allowBackup="true"` |
| כתיבות Firestore | ישירות מה-client |
| הזרקת דמו | long-press ב-`WearableSyncActivity` |
| UID fallback | `test_user_123` / `test_user` |

### 5.4 Health Connect

| דרישה | מצב |
| ----- | --- |
| הרשאות ב-Manifest | מוגדרות (שינה, דופק, צעדים, HRV ועוד) |
| Privacy Policy rationale | Activity קיים אך **תוכן ריק** |
| `exported` | `PrivacyPolicyActivity` — `true` (נדרש ל-Health Connect intent) |

---

## 6. איכות קוד ו-lifecycle

### 6.1 Memory leaks — דפוס בעייתי

**HomeCoachActivity** — בכל `onResume`:

```
onResume()
  └── listenForPendingRequests()
        └── addSnapshotListener()  ← listener חדש, הישן לא מוסר
```

**HomeAthleteActivity** — בכל `onResume`:

```
onResume()
  └── checkDailyDataStatus()
        └── updateAlertUI() / updateAlertUIWithZeroDataState()
              └── TabLayoutMediator(...).attach()  ← mediator חדש, הישן לא מנותק
```

### 6.2 Coroutines ו-callbacks

| נושא | מיקום |
| ---- | ----- |
| `lifecycleScope` ב-`AnalyzingMealActivity` — טוב | `AnalyzingMealActivity.kt` |
| `ClientEventReporter` — scope גלובלי ללא ביטול | `ClientEventReporter.kt` |
| Retrofit `enqueue()` — לא קשור ל-lifecycle | `DailyCheckInActivity.kt`, `WearableSyncActivity.kt` |

### 6.3 קוד מת (Dead code)

| פריט | קובץ |
| ---- | ---- |
| `MainActivity` (לא launcher) | `ui/auth/MainActivity.kt` |
| `PredictionModels.kt` | `model/PredictionModels.kt` |
| `updateUIWithMissingDataState()` | `AthleteDashboardActivity.kt` |
| `SignalManager.contextRef` | `utilities/SignalManager.kt` |
| `RequestIdHolder.generateNewId()` — לא נקרא | `RequestIdHolder.kt` |

---

## 7. טיפול בשגיאות ו-UX

### 7.1 מה עובד טוב

- `SignalManager` — הודעות success/error/info עקביות
- מצבי loading ב-login, join team, create team, coach requests
- Alerts ב-Home Athlete מנחים את המשתמש (sync, check-in, meal)
- Dashboard מציג מצב pending כשנתוני ML חסרים

### 7.2 פערים

| חומרה | ממצא |
| ----- | ---- |
| P1 | שגיאות Gemini מוצגות ונעלמות מיד (`finish()` מיידי) |
| P1 | כשל Google Sign-In — שקט |
| P1 | כשל כתיבה ל-Firestore ב-sync — שקט |
| P1 | תוצאות תזונה 0/0/0 במקום שגיאה |
| P2 | אין cancel/progress בזמן ניתוח ארוחה |
| P2 | Coach dashboard — אין retry ל-AI recommendation |
| P2 | יעדי תזונה לא מותאמים אישית |

---

## 8. ביצועים

| חומרה | ממצא | מיקום | השפעה |
| ----- | ---- | ----- | ----- |
| P1 | Bitmap במלוא הרזולוציה ל-Gemini | `AnalyzingMealActivity.kt` | OOM |
| P2 | N+1 Firestore reads לרשימת ספורטאים | `CoachDashboardActivity.kt` | איטיות |
| P2 | טעינת כל `daily_health` ללא פילטר תאריך | `AthleteDashboardActivity.kt`, `CoachDashboardActivity.kt` | איטיות + עלות |
| P2 | 3 קריאות Firestore בכל `onResume` | `HomeAthleteActivity.kt` | רשת מיותרת |
| P2 | קריאות Gemini ישירות מ-Activity — ללא cache מעבר ל-Firestore | Dashboard activities | עלות API |
| P3 | `isMinifyEnabled = false` | `build.gradle.kts` | APK גדול, reverse engineering קל |
| P3 | אנימציית הקלדה על main thread | Dashboard activities | jank אפשרי |

---

## 9. עקביות ותחזוקה

### 9.1 שמות שדות Firestore

שימוש לא אחיד: `TeamName` מול `teamCode` מול `teamId` — מקשה על תחזוקה.

### 9.2 לוגים

| כלי | שימוש |
| --- | ----- |
| Timber | `App.kt` (DEBUG בלבד) |
| `Log.d` / `Log.e` | Activities שונים |
| `ClientEventReporter` | שליחה לשרת observability |

אין אסטרטגיה אחידה ל-production logging.

### 9.3 SDK versions

| הגדרה | ערך |
| ----- | --- |
| `compileSdk` | 36 |
| `targetSdk` | 34 |
| `minSdk` | 26 |

### 9.4 כלי עזר שלא מנוצלים

```kotlin
// CalculationUtils.kt — קיים אך לא בשימוש ב-production:
fun getRiskLevel(score: Int): String
fun isTeamCodeValid(code: String): Boolean
```

---

## 10. מבנה קוד, ארגון וחלוקה לקלאסים

### 10.1 סיכום

הקוד מאורגן לפי **מסכים (Activities)** ולא לפי **תחומי אחריות (domains)**. רוב הלוגיקה העסקית, גישת הנתונים, ואינטגרציות חיצוניות יושבות בתוך קלאסי Activity בודדים. אין Repository, ViewModel, UseCase, או שכבת data נפרדת.

**הבעיה המרכזית:** Activities שמטפלים ב-4–6 תחומים שונים במקביל (UI, Firestore, Health Connect, Gemini, Retrofit, charting).

### 10.2 אורך קבצים — Kotlin

סף מומלץ ל-Activity: **~150–200 שורות**. מעל 250 — סימן לפיצול.

| שורות | קובץ | הערכה |
| ----- | ---- | ----- |
| **366** | `WearableSyncActivity.kt` | **ארוך מדי** — 4 תחומי אחריות |
| **255** | `HomeAthleteActivity.kt` | **ארוך** — home + alerts + camera + Firestore |
| **253** | `CoachDashboardActivity.kt` | **ארוך** — roster + details + Gemini + chart |
| **250** | `AthleteDashboardActivity.kt` | **ארוך** — prediction + Gemini + chart |
| **237** | `LoginActivity.kt` | **ארוך** — login + Google + dialog + routing |
| 145 | `DailyCheckInActivity.kt` | סביר, אך כולל ML trigger מועתק |
| 126 | `HomeCoachActivity.kt` | סביר |
| 121 | `RegisterActivity.kt` | סביר |
| 121 | `AnalyzingMealActivity.kt` | סביר |
| ≤111 | שאר הקבצים | בגודל סביר |

**סטטיסטיקה:**

| מדד | ערך |
| --- | --- |
| סה"כ קבצי Kotlin ב-`main` | 32 |
| ממוצע שורות לקובץ | ~95 |
| קבצים מעל 200 שורות | **5** (כולם Activities) |
| קבצים מעל 300 שורות | **1** (`WearableSyncActivity`) |
| קלאסים public בקובץ | 1 לכל קובץ (טוב) |
| Adapters בתוך `ui/` | 3 — לצד Activities (מקובל לפרויקט קטן) |

### 10.3 אורך קבצים — Layouts (XML)

| שורות | קובץ | הערכה |
| ----- | ---- | ----- |
| **355** | `activity_daily_check_in.xml` | **ארוך** — מסך אחד, הרבה widgets |
| **304** | `activity_home_athlete.xml` | **ארוך** |
| 229 | `activity_home_coach.xml` | גבולי |
| 198 | `activity_login.xml` | סביר |
| ≤193 | שאר ה-layouts | סביר |

**בעיה:** layouts ארוכים משקפים מסכים עמוסים. אין שימוש ב-`<include>`, `<merge>`, או custom views לחלוקה.

### 10.4 God Activities — פירוט אחריות

#### `WearableSyncActivity.kt` (366 שורות) — **הכי בעייתי**

| אחריות | שורות (בערך) | מה צריך להיות |
| ------ | ------------ | ------------- |
| הרשאות Health Connect | 48–78, 179–194 | `HealthConnectPermissionManager` |
| הזרקת דמו ל-Firestore | 96–177 | למחוק / `DemoDataInjector` (debug בלבד) |
| סנכרון נתונים אמיתי | 196–265 | `HealthConnectSyncRepository` |
| קריאת שינה | 267–274 | בתוך repository |
| קריאת מדדים פיזיים | 276–365 | `HealthMetricsMapper` |
| טריגר ML | 367–426 | `PredictionTriggerUseCase` (משותף) |

**6 תחומי אחריות בקלאס אחד.**

#### `AthleteDashboardActivity.kt` + `CoachDashboardActivity.kt` — **כפילות מבנית**

שני הקבצים חולקים את אותה מבנה:

| פונקציה | Athlete | Coach |
| ------- | ------- | ----- |
| טעינת נתוני יום מ-Firestore | `loadTodayPredictionFromFirestore` | `loadAthleteHealthData` |
| קריאה ל-Gemini | `fetchAIRecommendation` | `fetchAIRecommendationForCoach` |
| עדכון UI לפי risk score | `updateUIWithScore` | `updateRiskUI` |
| אנימציית הקלדה | `typeText` | `typeText` (זהה) |
| גרף היסטוריה | `loadHistoricalData` + `updateChart` | `loadHistoricalChartData` + `updateChart` |

**~80 שורות של `updateChart` + `typeText` + risk thresholds מועתקים בין שני קבצים.**

#### `HomeAthleteActivity.kt` (255 שורות)

| אחריות | פונקציות |
| ------ | -------- |
| ניווט / כפתורים | `initViews` |
| מצלמה + גלריה | `showImageSourceDialog`, `openCamera`, launchers |
| שם משתמש + קבוצה | `fetchUserName` |
| בדיקת סטטוס יומי | `checkDailyDataStatus` |
| בניית alerts | `updateAlertUI`, `updateAlertUIWithZeroDataState` |
| logout | `performLogout` |

**המלצה:** לחלץ `DailyStatusChecker` + `AlertCarouselBinder`.

#### `LoginActivity.kt` (237 שורות)

| אחריות | פונקציות |
| ------ | -------- |
| Email/password login | `initViews` + `LoginManager` |
| Google Sign-In | `signInWithGoogle`, `onSignInResult` |
| דיאלוג בחירת role | `showRoleSelectionDialog` (70+ שורות) |
| שמירת פרופיל | `saveUserToFirestore` |
| ניווט לפי role | `checkUserRoleAndNavigate`, `navigateToDashboard` |

**המלצה:** `AuthNavigator`, `GoogleProfileSetupDialog` (Fragment/Composable).

### 10.5 מבנה חבילות (Packages)

```
com.yahav.athleagent/
├── App.kt
├── logic/          ← רק LoginManager (1 קובץ)
├── model/          ← 4 data classes (טוב)
├── network/        ← ApiClient + ApiService (טוב, דק)
├── observability/  ← 4 קבצים (טוב, ממוקד)
├── ui/
│   ├── athlete/    ← 9 Activities + 2 Adapters (עמוס)
│   ├── auth/       ← 3 Activities
│   ├── coach/      ← 5 Activities + 1 Adapter
│   └── PrivacyPolicyActivity.kt  ← שורש ui/ (לא עקבי)
├── util/           ← CalculationUtils
└── utilities/      ← SignalManager  ← כפילות שם!
```

#### בעיות במבנה החבילות

| חומרה | בעיה |
| ----- | ---- |
| P1 | **אין שכבת `data/`** — Firestore + Retrofit + Health Connect בתוך Activities |
| P1 | **אין שכבת `domain/`** — לוגיקת ML trigger, risk thresholds, validation |
| P2 | `util/` ו-`utilities/` — שני packages לכלים |
| P2 | `logic/` עם קובץ בודד — לא ברור למה לא `auth/` |
| P2 | Adapters גם ב-`ui/athlete/` וגם ב-`ui/coach/` — אין `ui/common/` |
| P2 | `PrivacyPolicyActivity` ישירות תחת `ui/` ולא `ui/common/` |
| P3 | `CoachDashboardActivity` מייבא מ-`ui.athlete.AthleteAdapter` — coupling בין coach ל-athlete |

### 10.6 כפילויות קוד (DRY)

| כפילות | מיקומים | שורות משוערות |
| ------ | ------- | ------------- |
| `checkAndTriggerPredictionInBackground()` | `DailyCheckInActivity`, `WearableSyncActivity` | ~60 × 2 = **120** |
| `updateChart()` + הגדרות MPAndroidChart | `AthleteDashboardActivity`, `CoachDashboardActivity` | ~35 × 2 = **70** |
| `typeText()` — אנימציית הקלדה | שני ה-Dashboards | ~10 × 2 = **20** |
| Risk score → צבע/drawable | שני ה-Dashboards (לא משתמשים ב-`CalculationUtils`) | ~15 × 2 = **30** |
| `performLogout()` | `HomeAthleteActivity`, `HomeCoachActivity` | ~10 × 2 = **20** |
| Edge-to-edge + window insets | כמעט כל Activity | ~8 × 10 = **80** |
| `SimpleDateFormat("yyyy-MM-dd")` | 12+ מקומות | — |
| `FirebaseFirestore.getInstance()` | כל Activity | — |
| `ClientEventReporter(ApiClient.observabilityApi)` | 6 Activities | — |

**סה"כ כפילות משוערת:** ~340+ שורות שניתן לרכז.

### 10.7 חלוקה לקלאסים — מה קיים vs מה חסר

| שכבה | קיים | חסר |
| ---- | ---- | --- |
| UI (Activity) | 15 Activities | — |
| UI (Adapter) | 3 adapters | ViewBinding ב-adapters |
| UI (Dialog) | inline ב-`LoginActivity` | Fragment / Dialog class |
| Auth | `LoginManager` (רק email/password) | `AuthRepository`, Google flow |
| Network | `ApiClient`, `ApiService` | Repository wrapper |
| Data / Firestore | — | `UserRepository`, `TeamRepository`, `HealthRepository` |
| Health Connect | — | `HealthConnectRepository`, `HealthMetricsMapper` |
| AI / Gemini | — | `GeminiRecommendationService` |
| Domain | `CalculationUtils` (חלקי, לא בשימוש) | `PredictionTrigger`, `RiskLevelMapper` |
| DI | — | Hilt / Koin (או factory פשוט) |

**יחס קלאסים:** 15 Activities לעומת 4 utility/service classes — **יחס לא מאוזן**.

### 10.8 סדר וארגון בתוך קבצים

#### מה טוב

- Import statements בראש הקובץ
- `onCreate` תמיד ראשון אחרי properties
- שמות פונקציות ברורים (`loadTeamAthletes`, `saveCheckInToFirebase`)
- קובץ אחד = קלאס אחד (למעט data classes קטנים)

#### מה פחות טוב

| בעיה | דוגמה |
| ---- | ----- |
| סדר פונקציות לא עקבי | `WearableSyncActivity`: demo injection לפני sync אמיתי |
| Properties מפוזרות | imports באמצע הקובץ (`WearableSyncActivity` שורות 34–39) |
| לוגיקה עמוקה (callback hell) | `checkAndTriggerPredictionInBackground` — 3 רמות `addOnSuccessListener` |
| Magic strings | `"daily_health"`, `"finalRiskScore"`, `"Athlete"`, `"Coach"` — אין constants |
| Magic numbers | risk thresholds `35, 55, 75` — קיימים ב-`CalculationUtils` אך לא בשימוש |
| Hardcoded colors ב-Kotlin | `"#E65100"`, `"#00F59B"` — גם ב-adapters וגם ב-activities |
| `@SuppressLint` רב | `SetTextI18n`, `NotifyDataSetChanged` — סימן ללוגיקה שצריכה ViewModel |

### 10.9 מבנה מומלץ (לעתיד)

```
com.yahav.athleagent/
├── data/
│   ├── firebase/
│   │   ├── UserRepository.kt
│   │   ├── TeamRepository.kt
│   │   └── HealthDataRepository.kt
│   ├── healthconnect/
│   │   ├── HealthConnectClientProvider.kt
│   │   └── HealthMetricsMapper.kt
│   ├── remote/
│   │   ├── ApiClient.kt
│   │   ├── ApiService.kt
│   │   └── PredictionRemoteDataSource.kt
│   └── ai/
│       └── GeminiService.kt
├── domain/
│   ├── PredictionTrigger.kt      ← מחליף את הכפילות
│   ├── RiskLevelMapper.kt        ← משתמש ב-CalculationUtils
│   └── model/                    ← data classes
├── ui/
│   ├── common/
│   │   ├── RiskChartHelper.kt
│   │   ├── TypingAnimator.kt
│   │   └── EdgeToEdgeExt.kt
│   ├── athlete/
│   ├── coach/
│   └── auth/
├── observability/
└── util/
    └── CalculationUtils.kt
```

### 10.10 ממצאים לפי חומרה — מבנה וארגון

| חומרה | ממצא |
| ----- | ---- |
| **P1** | `WearableSyncActivity` — 366 שורות, 6 אחריות — God Class |
| **P1** | `checkAndTriggerPredictionInBackground` מועתק בשלמותו ב-2 קבצים |
| **P1** | `updateChart` + `typeText` + risk UI מועתקים בין Athlete/Coach Dashboard |
| **P2** | 5 Activities מעל 200 שורות |
| **P2** | אין שכבת `data/` או `domain/` |
| **P2** | `util/` + `utilities/` — packages כפולים |
| **P2** | Layouts ארוכים (355, 304 שורות) ללא `<include>` |
| **P2** | `CoachDashboardActivity` תלוי ב-`ui.athlete.AthleteAdapter` |
| **P2** | Magic strings לשמות Firestore collections/fields |
| **P3** | `PrivacyPolicyActivity` לא בתת-תיקייה עקבית |
| **P3** | `requestsAdapter.kt` — שם קובץ lowercase |
| **P3** | `AlertItem` עם 6 פרמטרי צבע hex — צריך theme/resources |
| **P3** | Edge-to-edge boilerplate חוזר ב-10+ Activities |

### 10.11 סדר עדיפויות לריפקטור מבנה

| שלב | פעולה | השפעה |
| --- | ----- | ----- |
| 1 | חילוץ `PredictionTrigger` מ-shared class | מוריד ~120 שורות כפולות |
| 2 | חילוץ `RiskChartHelper` + `RiskLevelUiMapper` | מוריד ~120 שורות כפולות |
| 3 | חילוץ `HealthConnectRepository` מ-`WearableSyncActivity` | מוריד ~200 שורות |
| 4 | איחוד `util/` + `utilities/` | עקביות |
| 5 | העברת `AthleteAdapter` ל-`ui/common/` | decoupling coach/athlete |
| 6 | פיצול layouts ארוכים עם `<include>` | תחזוקת XML |

---

## 11. בדיקות (Testing)

### 11.1 כיסוי קיים

| קובץ | מה נבדק |
| ---- | ------- |
| `CalculationUtilsTest.kt` | `getRiskLevel`, `formatDateToKey`, `isTeamCodeValid`, `getSleepHours` |
| `RequestIdHolderTest.kt` | יצירת request ID |
| `ClientEventReporterTest.kt` | קריאת API (עלול להיות flaky) |
| `ExampleUnitTest.kt` | boilerplate |
| `ExampleInstrumentedTest.kt` | בדיקת package name בלבד |

### 11.2 פערים (חסר לחלוטין)

| קטגוריה | דוגמאות |
| ------- | ------- |
| Activity / flow tests | Login, register, check-in, sync, meal analysis |
| Integration tests | Firebase / Retrofit (mocked) |
| Adapter tests | `AlertsAdapter`, `AthleteAdapter`, `RequestsAdapter` |
| ML trigger preconditions | sleep > 0, steps אתמול > 0, survey קיים |
| Security tests | אין `test_user_123` ב-production paths |
| Gemini parsing | JSON פגום, markdown wrappers |
| Health Connect | הרשאות ו-sync |
| UI / Instrumentation | מעבר boilerplate |

### 11.3 באג בבדיקה קיימת

```
CalculationUtils.getRiskLevel(35)
  Implementation: score <= 35 → "Low"
  Test expects:  "Medium"
```

קובץ: `CalculationUtilsTest.kt` שורה 15.

---

## 12. מפת מסכים (Activities)

| מסך | תפקיד | Launcher |
| --- | ----- | -------- |
| `LoginActivity` | התחברות (Email + Google) | **כן** |
| `RegisterActivity` | הרשמה | לא |
| `MainActivity` | Routing לפי role | לא (dead code) |
| `HomeAthleteActivity` | בית ספורטאי | לא |
| `HomeCoachActivity` | בית מאמן | לא |
| `DailyCheckInActivity` | סקר יומי | לא |
| `WearableSyncActivity` | סנכרון Health Connect | לא |
| `MealAnalysisActivity` | תוצאות ארוחה | לא |
| `AnalyzingMealActivity` | ניתוח Gemini | לא |
| `AthleteDashboardActivity` | דשבורד סיכון + AI | לא |
| `JoinTeamActivity` | הצטרפות לקבוצה | לא |
| `CreateTeamActivity` | יצירת קבוצה | לא |
| `CoachDashboardActivity` | דשבורד מאמן | לא |
| `CoachRequestsActivity` | בקשות הצטרפות | לא |
| `PrivacyPolicyActivity` | מדיניות פרטיות (ריק) | exported (Health Connect) |

---

## 13. תוכנית תיקון מומלצת

### שלב 1 — לפני כל demo חיצוני

| עדיפות | פעולה | ממצאים |
| ------ | ----- | ------ |
| 1 | הסרת `injectSevenDaysOfWearableDemoData` ו-long-press | P0 #5 |
| 2 | החלפת `test_user_123` ב-logout / finish | P0 #6–10 |
| 3 | ולידציה ל-`injuryStr` לפני `toInt()` | P0 #11–12 |

### שלב 2 — אבטחה

| עדיפות | פעולה | ממצאים |
| ------ | ----- | ------ |
| 4 | העברת Gemini ל-Backend proxy | P0 #1–4 |
| 5 | הוספת Firebase ID token ל-Retrofit | P1 #1 |
| 6 | כתיבת תוכן Privacy Policy | P1 #6 |
| 7 | `allowBackup="false"` או exclusion rules | P1 #4 |

### שלב 3 — יציבות

| עדיפות | פעולה | ממצאים |
| ------ | ----- | ------ |
| 8 | שמירת reference ל-listener + `remove()` ב-`onPause` | P1 #7 |
| 9 | שמירת `TabLayoutMediator` + `detach()` | P1 #8 |
| 10 | תיקון `showErrorAndFinish` — delay לפני `finish()` | P1 #10 |
| 11 | Downsample לפני שליחת bitmap ל-Gemini | P1 #14 |

### שלב 4 — תחזוקה

| עדיפות | פעולה | ממצאים |
| ------ | ----- | ------ |
| 12 | חילוץ `checkAndTriggerPredictionInBackground` ל-shared class | P2 #1 |
| 13 | שימוש ב-`CalculationUtils` בכל ה-UI | P2 thresholds |
| 14 | מחיקת dead code (`MainActivity`, `PredictionModels`) | P2 |
| 15 | תיקון `CalculationUtilsTest` או הקוד | P1 #16 |

### שלב 5 — בדיקות

| עדיפות | פעולה |
| ------ | ----- |
| 16 | Unit tests ל-Gemini JSON parsing |
| 17 | Unit tests ל-ML trigger preconditions |
| 18 | Instrumentation test ל-login flow |

### שלב 6 — מבנה קוד

| עדיפות | פעולה |
| ------ | ----- |
| 19 | חילוץ `PredictionTrigger` ל-shared class |
| 20 | חילוץ `RiskChartHelper` + `RiskLevelUiMapper` |
| 21 | חילוץ `HealthConnectRepository` מ-`WearableSyncActivity` |
| 22 | איחוד `util/` + `utilities/` |
| 23 | פיצול layouts ארוכים עם `<include>` |

---

## 14. נספח — רשימת קבצים לפי חומרה מקסימלית

| חומרה מקסימלית | קבצים |
| -------------- | ----- |
| **P0** | `build.gradle.kts`, `AnalyzingMealActivity.kt`, `AthleteDashboardActivity.kt`, `CoachDashboardActivity.kt`, `WearableSyncActivity.kt`, `HomeAthleteActivity.kt`, `DailyCheckInActivity.kt`, `MealAnalysisActivity.kt`, `LoginActivity.kt`, `RegisterActivity.kt` |
| **P1** | `ApiClient.kt`, `CorrelationIdInterceptor.kt`, `network_security_config.xml`, `AndroidManifest.xml`, `HomeCoachActivity.kt`, `MainActivity.kt`, `CoachDashboardActivity.kt`, `CalculationUtilsTest.kt` |
| **P2** | `DailyCheckInActivity.kt`, `CreateTeamActivity.kt`, `JoinTeamActivity.kt`, `ClientEventReporter.kt`, `RequestIdHolder.kt`, `SignalManager.kt`, `ApiService.kt`, `PredictionModels.kt`, `LoginManager.kt` |
| **P3** | `App.kt`, `AthleteAdapter.kt`, `AlertItem.kt`, `requestsAdapter.kt` |

---

## 15. שינויי מסמך

| גרסה | תאריך | שינוי |
| ---- | ----- | ----- |
| 1.0 | 2026-07-09 | סקירה ראשונית מלאה של פרונטאנד Android |
| 1.1 | 2026-07-09 | הוספת פרק 10: מבנה קוד, אורך קבצים, חלוקה לקלאסים, כפילויות, packages |
