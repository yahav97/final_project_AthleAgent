"""User repository for database operations."""

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from models.user import User


class UserRepository:
    """Repository for User model database operations."""

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """Get user by email."""
        return db.query(User).filter(User.email == email).first()

    def get_by_google_id(self, db: Session, google_id: str) -> Optional[User]:
        """Get user by Google ID."""
        return db.query(User).filter(User.google_id == google_id).first()

    def get_by_id(self, db: Session, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        return db.query(User).filter(User.id == user_id).first()

    def create_user(
        self,
        db: Session,
        email: str,
        password_hash: Optional[str],
        full_name: str,
        role: str = "athlete",
        google_id: Optional[str] = None,
    ) -> User:
        """Create a new user."""
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            role=role,
            google_id=google_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def create_or_update_google_user(
        self,
        db: Session,
        google_id: str,
        email: str,
        full_name: str,
    ) -> User:
        """Create or update user from Google OAuth."""
        user = self.get_by_google_id(db, google_id)
        if user:
            # Update email/name if changed
            user.email = email
            user.full_name = full_name
            db.commit()
            db.refresh(user)
            return user

        # Create new user
        user = self.create_user(
            db=db,
            email=email,
            password_hash=None,
            full_name=full_name,
            role="athlete",
            google_id=google_id,
        )
        return user

