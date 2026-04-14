"""Nutrition record model - stores meal data from Gemini AI."""

from sqlalchemy import Column, String, Integer, Float, Date, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from database.connection import Base


class NutritionRecord(Base):
    """Nutrition records - meals analyzed by Gemini AI or manually entered."""
    
    __tablename__ = "nutrition_records"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # Meal info
    meal_type = Column(String, nullable=False)  # 'breakfast', 'lunch', 'dinner', 'snack'
    image_url = Column(String, nullable=True)  # Path to stored image
    
    # Nutrition data (from Gemini AI)
    calories = Column(Integer, nullable=True)
    protein = Column(Float, nullable=True)  # grams
    carbs = Column(Float, nullable=True)  # grams
    fats = Column(Float, nullable=True)  # grams
    
    # Metadata
    gemini_response = Column(JSONB, nullable=True)  # Full Gemini API response
    manual_entry = Column(Boolean, default=False)  # True if entered manually
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="nutrition_records")


