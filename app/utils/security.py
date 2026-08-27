"""
app/utils/security.py — Token encryption and decryption using Fernet.
"""

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from cryptography.fernet import Fernet
from app.config import settings

AUTH_TOKEN_SALT = "voxyl-auth-token"
AUTH_TOKEN_MAX_AGE_SECONDS = 14 * 24 * 3600


def _get_fernet() -> Fernet:
    """Return a Fernet cipher initialized with the configured encryption key."""
    # Ensure key is in bytes format
    key = settings.token_encryption_key.encode("utf-8")
    return Fernet(key)


def encrypt_token(token: str) -> str:
    """Encrypt a plaintext string token and return a base64-encoded encrypted string."""
    if not token:
        return ""
    fernet = _get_fernet()
    encrypted_bytes = fernet.encrypt(token.encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a base64-encoded encrypted token string back to plaintext."""
    if not encrypted_token:
        return ""
    fernet = _get_fernet()
    decrypted_bytes = fernet.decrypt(encrypted_token.encode("utf-8"))
    return decrypted_bytes.decode("utf-8")


def _get_auth_serializer() -> URLSafeTimedSerializer:
    """Return a serializer for signed auth handoff tokens."""
    return URLSafeTimedSerializer(settings.session_secret_key, salt=AUTH_TOKEN_SALT)


def create_auth_token(user_id: int) -> str:
    """Create a short signed token that can bootstrap auth on browsers with strict cookie rules."""
    serializer = _get_auth_serializer()
    return serializer.dumps({"user_id": user_id})


def decode_auth_token(token: str, max_age_seconds: int = AUTH_TOKEN_MAX_AGE_SECONDS) -> int | None:
    """Validate a bootstrap token and return the embedded user id if it is still valid."""
    if not token:
        return None

    serializer = _get_auth_serializer()
    try:
        payload = serializer.loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    except Exception:
        return None

    user_id = payload.get("user_id") if isinstance(payload, dict) else None
    return int(user_id) if isinstance(user_id, int) or (isinstance(user_id, str) and user_id.isdigit()) else None
