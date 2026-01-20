"""Injury model - tracks actual injuries (optional, for model validation)."""

from sqlalchemy import Column, String, Date, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from database.connection import Base


class Injury(Base):
    """Injury records - tracks actual injuries for model validation."""
    
    __tablename__ = "injuries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # Injury details
    injury_type = Column(String, nullable=True)
    severity = Column(String, nullable=True)  # 'mild', 'moderate', 'severe'
    body_part = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="injuries")


