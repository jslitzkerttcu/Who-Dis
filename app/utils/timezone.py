"""
Timezone utilities for WhoDis application.
"""

import pytz
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


def get_configured_timezone() -> pytz.tzinfo.BaseTzInfo:
    """
    Get the configured timezone from configuration.
    Falls back to US/Central if not configured or invalid.

    Returns:
        pytz timezone object
    """
    from app.services.configuration_service import config_get

    timezone_str = config_get("app.timezone", "US/Central")

    try:
        return pytz.timezone(timezone_str)
    except pytz.exceptions.UnknownTimeZoneError:
        logger.warning(
            f"Invalid timezone '{timezone_str}' in configuration, using US/Central"
        )
        return pytz.timezone("US/Central")


def convert_to_configured_timezone(dt: datetime) -> datetime:
    """
    Convert a datetime to the configured timezone.

    Args:
        dt: datetime object (can be timezone-aware or naive)

    Returns:
        datetime object in configured timezone
    """
    tz = get_configured_timezone()

    # Handle timezone-naive datetime
    if dt.tzinfo is None:
        # Assume it's UTC
        dt = dt.replace(tzinfo=timezone.utc)

    # Convert to configured timezone
    return dt.astimezone(tz)


def format_timestamp(dt: datetime, format_str: str = "%m/%d %H:%M:%S %Z") -> str:
    """
    Format a timestamp in the configured timezone.

    Args:
        dt: datetime object
        format_str: strftime format string (default includes timezone abbreviation)

    Returns:
        Formatted timestamp string
    """
    local_dt = convert_to_configured_timezone(dt)
    return local_dt.strftime(format_str)


def format_timestamp_long(dt: datetime) -> str:
    """
    Format a timestamp in long format with configured timezone.

    Args:
        dt: datetime object

    Returns:
        Formatted timestamp string like "2024-01-15 14:30:45 CST"
    """
    return format_timestamp(dt, "%Y-%m-%d %H:%M:%S %Z")


def get_timezone_abbreviation() -> str:
    """
    Get the abbreviation for the configured timezone.

    Returns:
        Timezone abbreviation (e.g., "CST", "EST", "PST")
    """
    tz = get_configured_timezone()
    # Get current time to determine if DST is active
    now = datetime.now(tz)
    return now.strftime("%Z")
