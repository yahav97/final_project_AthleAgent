"""Stress survey model - daily stress and mood surveys."""

from sqlalchemy import Column, String, Integer, Date, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from database.connection import Base


class StressSurvey(Base):
    """Stress surveys - one per day per user."""
    
    __tablename__ = "stress_surveys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # Survey responses (1-10 scale)
    stress_level = Column(Integer, nullable=False)  # 1-10
    mood_score = Column(Integer, nullable=True)  # 1-10
    energy_level = Column(Integer, nullable=True)  # 1-10
    sleep_quality = Column(Integer, nullable=True)  # 1-10
    
    # Additional notes
    additional_notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="stress_surveys")
    
    # Constraint: one survey per user per day
    __table_args__ = (UniqueConstraint("user_id", "date", name="unique_user_date_survey"),)

