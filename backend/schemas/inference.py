"""Request/response shapes for injury risk inference."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


# --- Legacy / demo payloads (Android demo_predict, test_predict) ---


class AthleteData(BaseModel):
    """Legacy engineered row for optional /predict/sklearn (subset merged with defaults)."""

    bmi: float
    injured_yesterday: float = 0.0
    daily_distance_km: float
    workout_intensity_minutes: int
    avg_cadence: int
    sleep_hours: float
    hrv_score: int
    resting_hr: int
    nutrition_intake_calories: float = 2500.0
    daily_calories: int
    total_calories_burned: int
    calorie_balance: int
    stress_level: int
    muscle_soreness: int
    energy_level: float = 5.0
    acute_load_7d: float
    chronic_load_21d: float
    acwr_ratio: float
    sleep_debt_3d: float
    hrv_drop: float


class SimpleData(BaseModel):
    user_id: str


# --- Production contract (field names aligned with Android / Firestore) ---


class InjuryPredictionRequest(BaseModel):
    """
    Daily signals as stored or computed in the Android app (camelCase JSON).

    All fields optional so partial payloads are valid; the service applies defaults.
    """

    model_config = ConfigDict(extra="ignore")

    userId: str | None = Field(default=None, description="Firebase Auth uid")
    date: str | None = Field(default=None, description="Day key yyyy-MM-dd")

    # users/{uid}/daily_health (Health Connect sync + survey flags on same doc)
    injuredYesterday: int | None = Field(
        default=None,
        validation_alias=AliasChoices("injuredYesterday", "injured_yesterday"),
        description="0/1 — injury on previous calendar day (stored on today's daily_health doc)",
    )
    sleepMinutes: int | None = None
    steps: int | None = None
    distanceMeters: int | None = None
    activeCalories: int | None = None
    totalCalories: int | None = None
    heartRateAvg: int | None = None
    heartRateMax: int | None = None
    heartRateMin: int | None = None
    weightKg: float | None = None
    bmrCalories: int | None = None

    # users/{uid}/daily_checkins
    energyLevel: int | None = None
    muscleSoreness: int | None = None
    stressLevel: int | None = None

    # users/{uid}/daily_nutrition/{date} aggregates
    totalProtein: int | None = None
    totalCarbs: int | None = None
    mealsLoggedCount: int | None = None
    nutritionTotalCalories: float | None = Field(
        default=None,
        validation_alias=AliasChoices("nutritionTotalCalories", "nutrition_total_calories"),
        description="Meal-logged kcal sum that day (Firestore totalCalories on nutrition doc); not Health burn.",
    )


class DailyPredictionTriggerRequest(BaseModel):
    """Minimal trigger contract: backend loads full daily snapshot from Firestore."""

    userId: str = Field(..., description="Firebase Auth uid")
    date: str = Field(..., description="Day key yyyy-MM-dd")


class InjuryPredictionResponse(BaseModel):
    """Production JSON response for POST /predict/daily."""

    risk_level: str
    risk_score: float = Field(..., description="Injury positive-class probability, 0.0–1.0")
    prediction_confidence: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Confidence score 0–100 (history coverage + input completeness)",
    )
