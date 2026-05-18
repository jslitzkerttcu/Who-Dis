"""Unit tests for password generator utility."""

import re

import pytest

from app.utils.password_generator import generate_temp_password

pytestmark = pytest.mark.unit


def test_generate_temp_password_format():
    """Password matches pattern: uppercase word + 2 digits + symbol."""
    password = generate_temp_password()
    # Pattern: starts with uppercase letter, lowercase letters, 2 digits, then a symbol
    assert re.match(r"^[A-Z][a-z]+\d{2}[!@#$%&*]$", password)


def test_generate_temp_password_length():
    """Generated passwords are at least 8 characters."""
    for _ in range(20):
        password = generate_temp_password()
        assert len(password) >= 8


def test_generate_temp_password_complexity():
    """Password contains uppercase, lowercase, digit, and symbol."""
    password = generate_temp_password()
    assert any(c.isupper() for c in password), "Missing uppercase"
    assert any(c.islower() for c in password), "Missing lowercase"
    assert any(c.isdigit() for c in password), "Missing digit"
    assert any(c in "!@#$%&*" for c in password), "Missing symbol"


def test_generate_temp_password_uniqueness():
    """100 generated passwords should have at least 50 unique values."""
    passwords = [generate_temp_password() for _ in range(100)]
    unique = set(passwords)
    assert len(unique) >= 50, f"Only {len(unique)} unique passwords out of 100"
