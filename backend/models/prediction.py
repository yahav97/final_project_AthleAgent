"""Prediction model - stores daily injury risk predictions."""

from sqlalchemy import Column, String, Float, Date, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from database.connection import Base


class Prediction(Base):
    """Injury risk predictions - generated daily by ML model."""
    
    __tablename__ = "predictions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # Prediction results
    risk_percentage = Column(Float, nullable=False)  # 0-100
    risk_level = Column(String, nullable=False)  # 'Low', 'Medium', 'High'
    
    # Additional data
    features_used = Column(JSONB, nullable=True)  # Store features dict used for prediction
    recommendations = Column(Text, nullable=True)  # Generated recommendations
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="predictions")
    
    # Constraint: one prediction per user per day
    __table_args__ = (UniqueConstraint("user_id", "date", name="unique_user_date_prediction"),)


