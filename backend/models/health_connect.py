"""Health Connect permission model - tracks Health Connect integration."""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from database.connection import Base


class HealthConnectPermission(Base):
    """Health Connect permissions - one per user."""
    
    __tablename__ = "health_connect_permissions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False, index=True)
    
    # Connection status
    is_connected = Column(Boolean, default=False)
    permissions_granted = Column(JSONB, nullable=True)  # Which permissions user granted
    
    # Sync info
    last_sync_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="health_connect_permission")


