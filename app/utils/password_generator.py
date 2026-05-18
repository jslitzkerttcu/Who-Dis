"""Temporary password generator for AD account operations.

Generates readable passwords meeting AD complexity requirements:
uppercase, lowercase, digit, and symbol. Designed for verbal
communication to end users (D-06 pattern).
"""

import secrets
from typing import List

WORDS: List[str] = [
    "Sunset", "Silver", "Garden", "Breeze", "Castle",
    "Dragon", "Forest", "Harbor", "Island", "Marble",
    "Orange", "Planet", "Rocket", "Sierra", "Timber",
    "Violet", "Winter", "Zenith", "Crystal", "Phoenix",
    "Thunder", "Diamond", "Falcon", "Copper",
]

SYMBOLS: str = "!@#$%&*"


def generate_temp_password() -> str:
    """Generate a temporary password meeting AD complexity requirements.

    Format: {Word}{2-digit-number}{symbol}
    Example: Castle42!

    Returns:
        A readable temporary password with uppercase, lowercase, digit, and symbol.
    """
    word = secrets.choice(WORDS)
    digits = secrets.randbelow(90) + 10
    symbol = secrets.choice(SYMBOLS)
    return f"{word}{digits}{symbol}"
