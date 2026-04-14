"""Authentication service for user registration and login."""

from datetime import timedelta
from typing import Optional

from fastapi import HTTPException, status
from passlib.hash import bcrypt
from sqlalchemy.orm import Session

from config import settings
from external.google_auth import GoogleTokenError, verify_google_token
from models.user import User
from repositories.user_repository import UserRepository
from schemas.user import LoginResponse, UserCreate, UserResponse
from utils.jwt import create_access_token


class AuthService:
    """Service for authentication operations."""

    def __init__(self) -> None:
        """Initialize auth service with user repository."""
        self.user_repo = UserRepository()

    # -------- Password Hashing --------

    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        return bcrypt.hash(password)

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash.

        Args:
            password: Plain text password
            password_hash: Hashed password

        Returns:
            True if password matches, False otherwise
        """
        return bcrypt.verify(password, password_hash)

    # -------- Username/Password Authentication --------

    def register_user(self, db: Session, user_in: UserCreate) -> User:
        """
        Register a new user with email and password.

        Args:
            db: Database session
            user_in: User creation data

        Returns:
            Created user object

        Raises:
            HTTPException: If user with email already exists
        """
        existing = self.user_repo.get_by_email(db, user_in.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

        password_hash = self.hash_password(user_in.password)
        user = self.user_repo.create_user(
            db=db,
            email=user_in.email,
            password_hash=password_hash,
            full_name=user_in.full_name,
            role=user_in.role,
        )
        return user

    def authenticate_user(
        self,
        db: Session,
        email: str,
        password: str,
    ) -> Optional[User]:
        """
        Authenticate user with email and password.

        Args:
            db: Database session
            email: User email
            password: Plain text password

        Returns:
            User object if authentication successful, None otherwise
        """
        user = self.user_repo.get_by_email(db, email)
        if not user or not user.password_hash:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        return user

    # -------- Google OAuth Authentication --------

    def authenticate_google_user(self, db: Session, google_token: str) -> User:
        """
        Authenticate or register user with Google OAuth token.

        Args:
            db: Database session
            google_token: Google ID token from client

        Returns:
            User object (existing or newly created)

        Raises:
            HTTPException: If token verification fails
        """
        try:
            payload = verify_google_token(google_token)
        except GoogleTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
            )

        google_id = payload.get("sub")
        email = payload.get("email")
        full_name = payload.get("name") or email or "Google User"

        if not google_id or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Google token payload: missing required fields",
            )

        user = self.user_repo.create_or_update_google_user(
            db=db,
            google_id=google_id,
            email=email,
            full_name=full_name,
        )
        return user

    # -------- Token Creation / Response --------

    def create_login_response(self, user: User) -> LoginResponse:
        """
        Create login response with JWT token and user data.

        Args:
            user: User object

        Returns:
            LoginResponse with access token and user data
        """
        access_token_expires = timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
        }
        token = create_access_token(
            data=token_data,
            expires_delta=access_token_expires,
        )
        return LoginResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )

