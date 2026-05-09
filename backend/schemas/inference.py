"""Request/response shapes for injury risk inference."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


# --- Legacy / demo payloads (Android demo_predict, test_predict) ---


class AthleteData(BaseModel):
    age: int
    bmi: float
    history_injury_count: int
    vo2_max: int
    daily_distance_km: float
    workout_intensity_minutes: int
    avg_cadence: int
    sleep_hours: float
    hrv_score: int
    resting_hr: int
    daily_calories: int
    total_calories_burned: int
    calorie_balance: int
    stress_level: int
    muscle_soreness: int
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

    # users/{uid}/profile (static or slowly-changing athlete profile)
    age: int | None = None
    vo2_max: int | None = Field(
        default=None,
        validation_alias=AliasChoices("vo2_max", "vo2Max"),
    )
    history_injury_count: int | None = Field(
        default=None,
        validation_alias=AliasChoices("history_injury_count", "historyInjuryCount"),
    )

    # users/{uid}/daily_health (Health Connect sync)
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


class DailyPredictionTriggerRequest(BaseModel):
    """Minimal trigger contract: backend loads full daily snapshot from Firestore."""

    userId: str = Field(..., description="Firebase Auth uid")
    date: str = Field(..., description="Day key yyyy-MM-dd")


class InjuryPredictionResponse(BaseModel):
    """Production JSON response for POST /predict."""

    risk_level: str
    risk_score: float = Field(..., description="Scalar risk score, e.g. 0.0–1.0")
    recommendation: str
    data_quality_score: float = Field(..., description="Current-day payload quality score in range 0.0–1.0")
    data_quality_status: str = Field(..., description="Current-day quality label: Excellent/Good/Fair/Poor")
    meta: dict[str, str] = Field(default_factory=dict, description="Prediction provenance metadata")
