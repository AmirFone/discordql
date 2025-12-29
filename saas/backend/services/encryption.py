"""
Token encryption service using Fernet symmetric encryption.
"""
from cryptography.fernet import Fernet

from config import get_settings

settings = get_settings()

# Initialize Fernet with encryption key
# Key should be 32 url-safe base64-encoded bytes
_fernet = None


def get_fernet() -> Fernet:
    """Get or create Fernet instance."""
    global _fernet
    if _fernet is None:
        key = settings.discord_token_encryption_key
        if not key:
            raise ValueError("DISCORD_TOKEN_ENCRYPTION_KEY environment variable not set")
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_token(token: str) -> bytes:
    """
    Encrypt a Discord bot token.

    Args:
        token: The plaintext Discord bot token

    Returns:
        Encrypted token as bytes (suitable for BYTEA column)
    """
    fernet = get_fernet()
    return fernet.encrypt(token.encode('utf-8'))


def decrypt_token(encrypted_token: bytes) -> str:
    """
    Decrypt a Discord bot token.

    Args:
        encrypted_token: The encrypted token bytes from database

    Returns:
        Plaintext Discord bot token
    """
    fernet = get_fernet()
    return fernet.decrypt(encrypted_token).decode('utf-8')


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.

    Use this to generate the DISCORD_TOKEN_ENCRYPTION_KEY value.
    Run once and store the result in environment variables.

    Returns:
        Base64-encoded 32-byte key suitable for Fernet
    """
    return Fernet.generate_key().decode('utf-8')


if __name__ == "__main__":
    # Utility: generate a new encryption key
    print("New encryption key:")
    print(generate_encryption_key())
