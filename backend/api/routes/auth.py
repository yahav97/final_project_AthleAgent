"""Authentication API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.dependencies import get_current_user, get_db_session
from models.user import User
from schemas.user import (
    GoogleAuthRequest,
    LoginRequest,
    LoginResponse,
    UserCreate,
    UserResponse,
)
from services.auth_service import AuthService

router = APIRouter()


@router.post("/register", response_model=LoginResponse, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserCreate,
    db: Session = Depends(get_db_session),
) -> LoginResponse:
    """
    Register a new user.

    Args:
        user_in: User registration data
        db: Database session

    Returns:
        Login response with access token and user data

    Raises:
        HTTPException: If user with email already exists
    """
    auth_service = AuthService()
    user = auth_service.register_user(db, user_in)
    return auth_service.create_login_response(user)


@router.post("/login", response_model=LoginResponse)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db_session),
) -> LoginResponse:
    """
    Authenticate user and return access token.

    Args:
        credentials: Login credentials (email, password)
        db: Database session

    Returns:
        Login response with access token and user data

    Raises:
        HTTPException: If credentials are invalid
    """
    auth_service = AuthService()
    user = auth_service.authenticate_user(
        db, credentials.email, credentials.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    return auth_service.create_login_response(user)


@router.post("/google", response_model=LoginResponse)
def google_auth(
    body: GoogleAuthRequest,
    db: Session = Depends(get_db_session),
) -> LoginResponse:
    """
    Authenticate or register user with Google OAuth.

    Args:
        body: Google authentication request with ID token
        db: Database session

    Returns:
        Login response with access token and user data

    Raises:
        HTTPException: If Google token is invalid
    """
    auth_service = AuthService()
    user = auth_service.authenticate_google_user(db, body.google_token)
    return auth_service.create_login_response(user)


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """
    Get current authenticated user information.

    Args:
        current_user: Current authenticated user (from JWT token)

    Returns:
        Current user data
    """
    return UserResponse.model_validate(current_user)

