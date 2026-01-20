"""Team models - for coach-athlete relationships."""

from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

from database.connection import Base


class Team(Base):
    """Team table - created by coaches."""
    
    __tablename__ = "teams"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, nullable=False)
    coach_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    join_code = Column(String, unique=True, nullable=False, index=True)  # 6-8 character code
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    coach = relationship("User", foreign_keys=[coach_id], back_populates="teams_coached")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")
    join_requests = relationship("JoinRequest", back_populates="team", cascade="all, delete-orphan")


class TeamMember(Base):
    """Team membership - links athletes to teams."""
    
    __tablename__ = "team_members"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    team = relationship("Team", back_populates="members")
    athlete = relationship("User", foreign_keys=[athlete_id], back_populates="team_memberships")
    
    # Constraint: one athlete can only be in a team once
    __table_args__ = (UniqueConstraint("team_id", "athlete_id", name="unique_team_athlete"),)


class JoinRequest(Base):
    """Join requests - athletes requesting to join teams."""
    
    __tablename__ = "join_requests"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(UUID(as_uuid=True), ForeignKey("teams.id"), nullable=False)
    athlete_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(String, nullable=False, default="pending")  # 'pending', 'approved', 'rejected'
    requested_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    team = relationship("Team", back_populates="join_requests")
    athlete = relationship("User", foreign_keys=[athlete_id], back_populates="join_requests")
    
    # Constraint: one pending request per team per athlete
    __table_args__ = (UniqueConstraint("team_id", "athlete_id", name="unique_team_athlete_request"),)


