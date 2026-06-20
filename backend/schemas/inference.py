"""Request/response shapes for injury risk inference."""

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from schemas.types import RiskLevel, validate_date_key


# --- Legacy payloads (test_predict mock, optional /predict/sklearn) ---


class AthleteData(BaseModel):
    """Legacy engineered row for optional /predict/sklearn (subset merged with defaults)."""

    bmi: float
    age: float = 28.0
    history_injury_count: float = 0.0
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

    # users/{uid} profile (optional until shipped on mobile)
    age: int | None = Field(default=None, description="Athlete age in years")
    historyInjuryCount: int | None = Field(
        default=None,
        validation_alias=AliasChoices("historyInjuryCount", "history_injury_count"),
        description="Lifetime injury count from profile when available",
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
    heightCm: float | None = None
    bmrCalories: int | None = None

    # New Health Connect fields
    hrvRmssd: float | None = Field(
        default=None,
        validation_alias=AliasChoices("hrvRmssd", "hrv_rmssd"),
        description="HRV RMSSD in ms from HeartRateVariabilityRmssd",
    )
    restingHeartRate: int | None = Field(
        default=None,
        validation_alias=AliasChoices("restingHeartRate", "resting_heart_rate"),
        description="Resting HR bpm from RestingHeartRate record",
    )
    bodyFatPct: float | None = Field(
        default=None,
        validation_alias=AliasChoices("bodyFatPct", "body_fat_pct"),
    )
    vo2Max: float | None = Field(
        default=None,
        validation_alias=AliasChoices("vo2Max", "vo2_max"),
        description="VO2max ml/kg/min from Vo2Max record",
    )
    elevationGainedMeters: float | None = Field(
        default=None,
        validation_alias=AliasChoices("elevationGainedMeters", "elevation_gained_meters"),
    )
    floorsClimbed: int | None = None
    avgSpeed: float | None = Field(
        default=None,
        validation_alias=AliasChoices("avgSpeed", "avg_speed"),
        description="Average speed km/h from SpeedSeries",
    )
    maxSpeed: float | None = Field(
        default=None,
        validation_alias=AliasChoices("maxSpeed", "max_speed"),
    )
    avgPower: float | None = Field(
        default=None,
        validation_alias=AliasChoices("avgPower", "avg_power"),
        description="Average power watts from PowerSeries (0 if no power meter)",
    )
    avgCadence: float | None = Field(
        default=None,
        validation_alias=AliasChoices("avgCadence", "avg_cadence"),
        description="Average step cadence spm from StepsCadenceSeries",
    )
    respiratoryRate: float | None = Field(
        default=None,
        validation_alias=AliasChoices("respiratoryRate", "respiratory_rate"),
        description="Breaths per minute from RespiratoryRate",
    )
    oxygenSaturation: float | None = Field(
        default=None,
        validation_alias=AliasChoices("oxygenSaturation", "oxygen_saturation"),
        description="SpO2 % from OxygenSaturation",
    )

    # users/{uid}/daily_checkins (daily survey)
    injuredYesterday: int | None = Field(
        default=None,
        validation_alias=AliasChoices("injuredYesterday", "injured_yesterday"),
        description="0/1 — injured on previous calendar day (daily_checkins/{date})",
    )
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

    @field_validator("date", mode="before")
    @classmethod
    def _validate_date(cls, value: object) -> object:
        return validate_date_key(value)


class DailyPredictionTriggerRequest(BaseModel):
    """Minimal trigger contract: backend loads full daily snapshot from Firestore."""

    userId: str = Field(..., description="Firebase Auth uid")
    date: str = Field(..., description="Day key yyyy-MM-dd")

    @field_validator("date", mode="before")
    @classmethod
    def _validate_date(cls, value: object) -> object:
        return validate_date_key(value)


class InjuryPredictionResponse(BaseModel):
    """
    Production JSON response for POST /predict/daily — these three fields only.

    Also merged onto ``users/{uid}/daily_health/{date}`` (see ``save_daily_prediction_result``):
    - ``risk_level`` → ``riskLevel``
    - ``risk_score`` (0–1) → ``finalRiskScore`` = round(score × 100, 2)
    - ``prediction_confidence`` → ``predictionConfidence``
    - ``predictionUpdatedAt`` (ISO UTC) is written to Firestore only, not returned here.
    """

    risk_level: RiskLevel = Field(..., description="Low | Medium | High — persisted as riskLevel")
    risk_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Injury probability 0–1; persisted as finalRiskScore (0–100)",
    )
    prediction_confidence: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="0–100; persisted as predictionConfidence on daily_health",
    )
