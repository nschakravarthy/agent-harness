import jwt
import uuid
from datetime import datetime, timedelta
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from api.core.config import settings

# Initialize the hasher once (it holds recommended default security parameters)
ph = PasswordHasher()

def get_password_hash(password: str) -> str:
    """
    Hashes a plain-text password using Argon2id.
    The salt and parameters are automatically included in the returned string.
    """
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain-text password against a stored Argon2 hash.
    Returns True if valid, False otherwise.
    """
    try:
        # verify() returns None on success, or raises an exception on failure
        ph.verify(hashed_password, plain_password)
        return True
    except VerifyMismatchError:
        # Password was incorrect
        return False
    except Exception:
        # Handles other potential errors (e.g., malformed hash)
        return False

def create_token_session_id(data: dict):
    """
    Creates both access and refresh tokens.
    Returns a dictionary with both tokens.
    """
    # Create access token (short-lived)
    access_payload = data.copy()
    access_expire = datetime.now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_payload.update({"exp": access_expire, "type": "access"})
    access_token = jwt.encode(access_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    # Create refresh token (long-lived)
    refresh_payload = data.copy()
    refresh_expire = datetime.now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_payload.update({"exp": refresh_expire, "type": "refresh"})
    refresh_token = jwt.encode(refresh_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    session_id = str(uuid.uuid4())

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "session_id": session_id,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # seconds
    }

def verify_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("user_id")
        token_type: str = payload.get("type", "access")  # Default to access if not specified
        if user_id is None:
            return None
        return {
            "user_id": user_id,
            "type": token_type,
            "payload": payload
        }
    except jwt.PyJWTError:
        return None

def refresh_access_token(refresh_token: str):
    """
    Generates a new access token using a valid refresh token.
    """
    try:
        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_type = payload.get("type")
        
        # Ensure this is actually a refresh token
        if token_type != "refresh":
            return None
            
        user_id = payload.get("user_id")
        if user_id is None:
            return None
            
        # Create new access token
        new_token_data = {"user_id": user_id}
        return create_token_session_id(new_token_data)
        
    except jwt.PyJWTError:
        return None