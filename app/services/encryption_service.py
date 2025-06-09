"""
Simplified encryption service without backward compatibility.
Use this version after migrating existing encrypted values.
"""

import os
import base64
from typing import Optional, Union
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionService:
    """Service for encrypting and decrypting sensitive configuration values"""

    SALT_FILE = ".whodis_salt"
    SALT_LENGTH = 32  # 256 bits

    def __init__(self, passphrase: Optional[str] = None):
        """Initialize encryption service with passphrase from environment or parameter"""
        self.passphrase = passphrase or os.getenv("WHODIS_ENCRYPTION_KEY")
        if not self.passphrase:
            raise ValueError(
                "WHODIS_ENCRYPTION_KEY must be set in environment variables"
            )

        # Get or generate salt
        self.salt = self._get_or_create_salt()

        # Generate encryption key from passphrase
        self.fernet = self._create_fernet(self.passphrase, self.salt)

    def _get_salt_file_path(self) -> Path:
        """Get the path to the salt file"""
        # For development, prioritize app root directory
        app_root = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

        # Check if we're in development (no production env var)
        if os.getenv("WHODIS_PRODUCTION", "").lower() != "true":
            # In development, always use app root
            return app_root / self.SALT_FILE

        # In production, try multiple locations
        locations = []

        # Only add /etc/whodis on Unix-like systems
        if os.name != "nt":  # Not Windows
            locations.append(Path("/etc/whodis/salt"))

        # User home directory (works on all platforms)
        locations.append(Path.home() / ".whodis" / "salt")

        # App root directory as fallback
        locations.append(app_root / self.SALT_FILE)

        # Return the first writable location
        for location in locations:
            try:
                location.parent.mkdir(parents=True, exist_ok=True)
                return location
            except (PermissionError, OSError):
                continue

        # Fallback to app root
        return app_root / self.SALT_FILE

    def _get_or_create_salt(self) -> bytes:
        """Get existing salt or create a new one"""
        salt_file = self._get_salt_file_path()

        # Try to read existing salt
        if salt_file.exists():
            try:
                with open(salt_file, "rb") as f:
                    salt = f.read()
                if len(salt) == self.SALT_LENGTH:
                    return salt
            except Exception as e:
                print(f"Warning: Could not read salt file: {e}")

        # Generate new salt
        salt = os.urandom(self.SALT_LENGTH)

        # Try to save it
        try:
            with open(salt_file, "wb") as f:
                f.write(salt)
            # Set restrictive permissions (Unix only)
            if os.name != "nt":  # Not Windows
                os.chmod(salt_file, 0o600)
        except Exception as e:
            print(f"Warning: Could not save salt file: {e}")

        return salt

    def _create_fernet(self, passphrase: str, salt: bytes) -> Fernet:
        """Create Fernet instance from passphrase using PBKDF2"""
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
