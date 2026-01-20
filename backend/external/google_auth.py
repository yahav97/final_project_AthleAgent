"""Google OAuth token verification."""

from typing import Dict

from google.auth.transport import requests
from google.oauth2 import id_token

from config import settings


class GoogleTokenError(Exception):
    """Custom exception for Google token verification errors."""

    pass


def verify_google_token(google_token: str) -> Dict:
    """
    Verify Google ID token and return payload.

    Args:
        google_token: Google ID token from client

    Returns:
        Dictionary containing token payload:
        - sub: Google user ID
        - email: User email
        - name: User full name
        - picture: User profile picture (optional)

    Raises:
        GoogleTokenError: If token verification fails
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise GoogleTokenError("GOOGLE_CLIENT_ID not configured")

    try:
        request = requests.Request()
        payload = id_token.verify_oauth2_token(
            google_token,
            request,
            settings.GOOGLE_CLIENT_ID,
        )
        # verify_oauth2_token already validates the 'aud' claim
        return payload
    except ValueError as e:
        raise GoogleTokenError(f"Invalid Google token: {e}")
    except Exception as e:
        raise GoogleTokenError(f"Token verification failed: {e}")

