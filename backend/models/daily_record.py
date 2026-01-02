"""Daily record model - stores daily training and health data."""

from sqlalchemy import Column, String, Integer, Float, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from database.connection import Base


class DailyRecord(Base):
    """Daily records - training, sleep, HR, calories, etc."""
    
    __tablename__ = "daily_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # Training data
    daily_distance_km = Column(Float, nullable=True)
    workout_intensity_minutes = Column(Integer, nullable=True)
    avg_cadence = Column(Integer, nullable=True)
    
    # Health data (from Health Connect)
    sleep_hours = Column(Float, nullable=True)
    hrv_score = Column(Integer, nullable=True)
    resting_hr = Column(Integer, nullable=True)
    
    # Nutrition data
    daily_calories = Column(Integer, nullable=True)  # Aggregated from nutrition_records
    total_calories_burned = Column(Integer, nullable=True)  # From Health Connect
    calorie_balance = Column(Integer, nullable=True)  # Calculated: daily_calories - total_calories_burned
    
    # Survey data
    stress_level = Column(Integer, nullable=True)  # From stress survey (1-10)
    muscle_soreness = Column(Integer, nullable=True)  # Optional
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="daily_records")
    
    # Constraint: one record per user per day
    __table_args__ = (UniqueConstraint("user_id", "date", name="unique_user_date"),)

