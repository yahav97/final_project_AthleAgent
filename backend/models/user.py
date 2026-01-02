"""User model - athletes and coaches."""

from sqlalchemy import Column, String, Integer, Float, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from database.connection import Base


class User(Base):
    """User table - stores athletes and coaches."""
    
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=True)  # Nullable for Google OAuth users
    google_id = Column(String, unique=True, nullable=True, index=True)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="athlete")  # 'athlete' or 'coach'
    
    # Profile data
    age = Column(Integer, nullable=True)
    bmi = Column(Float, nullable=True)
    vo2_max = Column(Integer, nullable=True)
    history_injury_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    daily_records = relationship("DailyRecord", back_populates="user", cascade="all, delete-orphan")
    predictions = relationship("Prediction", back_populates="user", cascade="all, delete-orphan")
    nutrition_records = relationship("NutritionRecord", back_populates="user", cascade="all, delete-orphan")
    stress_surveys = relationship("StressSurvey", back_populates="user", cascade="all, delete-orphan")
    health_connect_permission = relationship("HealthConnectPermission", back_populates="user", uselist=False, cascade="all, delete-orphan")
    injuries = relationship("Injury", back_populates="user", cascade="all, delete-orphan")
    
    # Team relationships
    teams_coached = relationship("Team", back_populates="coach", foreign_keys="Team.coach_id")
    team_memberships = relationship("TeamMember", back_populates="athlete", foreign_keys="TeamMember.athlete_id")
    join_requests = relationship("JoinRequest", back_populates="athlete", foreign_keys="JoinRequest.athlete_id")

