"""
app/utils/security.py — Token encryption and decryption using Fernet.
"""

from cryptography.fernet import Fernet
from app.config import settings


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
