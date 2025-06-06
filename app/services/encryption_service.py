import os
import base64
from typing import Optional, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionService:
    """Service for encrypting and decrypting sensitive configuration values"""

    def __init__(self, passphrase: Optional[str] = None):
        """Initialize encryption service with passphrase from environment or parameter"""
        self.passphrase = passphrase or os.getenv("CONFIG_ENCRYPTION_KEY")
        if not self.passphrase:
            raise ValueError(
                "CONFIG_ENCRYPTION_KEY must be set in environment variables"
            )

        # Generate encryption key from passphrase
        self.fernet = self._create_fernet(self.passphrase)

    def _create_fernet(self, passphrase: str) -> Fernet:
        """Create Fernet instance from passphrase using PBKDF2"""
        # Use a fixed salt for consistent key generation
        # In production, you might want to store this separately
        salt = b"whodis-config-salt-2024"

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )

        key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        return Fernet(key)

    def encrypt(self, value: Union[str, bytes]) -> bytes:
        """Encrypt a value and return encrypted bytes"""
        if isinstance(value, str):
            value = value.encode("utf-8")
        return self.fernet.encrypt(value)

    def decrypt(self, encrypted_value: bytes) -> str:
        """Decrypt a value and return as string"""
        decrypted_bytes = self.fernet.decrypt(encrypted_value)
        return decrypted_bytes.decode("utf-8")

    def encrypt_string(self, value: str) -> str:
        """Encrypt a string and return base64-encoded string"""
        encrypted_bytes = self.encrypt(value)
        return base64.b64encode(encrypted_bytes).decode("utf-8")

    def decrypt_string(self, encrypted_value: str) -> str:
        """Decrypt a base64-encoded string"""
        encrypted_bytes = base64.b64decode(encrypted_value.encode("utf-8"))
        return self.decrypt(encrypted_bytes)

    @staticmethod
    def generate_key() -> str:
        """Generate a new encryption key/passphrase"""
        # Generate a secure random key
        key = Fernet.generate_key()
        # Return as base64 string for easy storage in .env
        return base64.b64encode(key).decode("utf-8")

    def is_encrypted(self, value: Union[str, bytes]) -> bool:
        """Check if a value appears to be encrypted"""
        try:
            if isinstance(value, str):
                # Try to decode as base64
                encrypted_bytes = base64.b64decode(value.encode("utf-8"))
            else:
                encrypted_bytes = value

            # Try to decrypt - if it works, it was encrypted
            self.fernet.decrypt(encrypted_bytes)
            return True
        except Exception:
            return False


# Singleton instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service(passphrase: Optional[str] = None) -> EncryptionService:
    """Get or create encryption service instance"""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService(passphrase)
    return _encryption_service


def encrypt_value(value: str) -> bytes:
    """Convenience function to encrypt a value"""
    service = get_encryption_service()
    return service.encrypt(value)


def decrypt_value(encrypted_value: bytes) -> str:
    """Convenience function to decrypt a value"""
    service = get_encryption_service()
    return service.decrypt(encrypted_value)
