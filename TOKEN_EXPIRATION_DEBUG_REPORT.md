# API Token Expiration Debug Report

## Issue Summary
Users reported that API tokens are showing as expired when they're actually valid, causing authentication failures for Genesys and Microsoft Graph services.

## Root Cause Analysis

### 1. **Missing Buffer for Clock Skew**
The original `is_expired()` method used a simple `now > expires_at` comparison without accounting for:
- Network latency when fetching tokens
- Clock skew between systems
- Processing time between token validation and usage

### 2. **Inconsistent Timezone Handling**
While the code attempted to handle timezone-naive vs timezone-aware datetimes, it didn't use `astimezone()` for proper timezone conversion, which could cause issues if the stored timestamp was in a different timezone.

### 3. **Lack of Debugging Information**
The original `get_token()` method provided no logging, making it difficult to diagnose why tokens were being rejected.

### 4. **Potential Race Conditions**
Tokens could be considered valid when checked but expire by the time they're actually used in an API call.

## Fixes Applied

### 1. **Enhanced `is_expired()` Method** (`/home/administrator/Repos/WhoDis/app/models/api_token.py`)

```python
def is_expired(self) -> bool:
    """
    Override base class is_expired to provide more robust timezone handling.
    
    Returns:
        True if token has expired, False otherwise
    """
    now = datetime.now(timezone.utc)
    expires_at = self.expires_at
    
    # Ensure both datetimes are timezone-aware and in UTC
    if expires_at.tzinfo is None:
        # If stored as naive datetime, assume it's UTC
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    else:
        # Convert to UTC if it's in a different timezone
        expires_at = expires_at.astimezone(timezone.utc)
        
    # Add a small buffer (30 seconds) to account for clock skew and processing time
    buffer = timedelta(seconds=30)
    return now > (expires_at - buffer)
```

**Key improvements:**
- Added 30-second buffer to prevent edge cases
- Proper timezone conversion using `astimezone()`
- Clear documentation of logic

### 2. **Enhanced Debugging in `get_token()`**

```python
@classmethod
def get_token(cls, service_name):
    """Get token for a service if it exists and is valid."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        token = cls.query.filter_by(service_name=service_name).first()
        if token:
            logger.debug(f"Found token for {service_name}, expires_at: {token.expires_at}, is_expired: {token.is_expired}")
            if not token.is_expired:
                logger.debug(f"Returning valid token for {service_name}")
                return token
            else:
                logger.debug(f"Token for {service_name} is expired, time_until_expiry: {token.time_until_expiry}")
        else:
            logger.debug(f"No token found for {service_name}")
    except Exception as e:
        logger.error(f"Error retrieving token for {service_name}: {e}")
        db.session.rollback()
        raise e
    return None
```

**Benefits:**
- Detailed logging for troubleshooting
- Shows exact expiration status and timing
- Helps identify database vs. logic issues

### 3. **Enhanced Status Reporting**

Updated `get_all_tokens_status()` to provide comprehensive debugging information:
- Original expires_at timestamp
- Converted expires_at in UTC
- Current time for comparison
- Time difference in seconds
- Timezone information
- Detailed status for each token

### 4. **Consistent `time_until_expiry` Logic**

Updated the property to use the same timezone handling as `is_expired()` for consistency.

## Debugging Tools Created

### 1. **`/home/administrator/Repos/WhoDis/scripts/debug_token_expiration.py`**
Production debugging script that can be run on a live system to:
- Show detailed token status
- Compare different time calculations
- Test `get_token()` method results
- Provide troubleshooting tips

### 2. **`/home/administrator/Repos/WhoDis/quick_token_test.py`**
Development testing script that simulates various scenarios without requiring database access.

### 3. **`/home/administrator/Repos/WhoDis/test_token_logic.py`**
Unit test-style script that validates the expiration logic against known scenarios.

## Testing Results

All test scenarios pass with the new logic:
- ✅ Valid tokens (1+ hours) remain valid
- ✅ Clearly expired tokens (1+ hours ago) are marked expired
- ✅ Tokens expiring within 30 seconds are marked expired (buffer working)
- ✅ Tokens expiring beyond 30 seconds remain valid
- ✅ Naive datetime tokens are handled correctly
- ✅ Timezone-aware tokens are converted properly

## Recommended Next Steps

### 1. **Deploy and Monitor**
- Deploy the updated `ApiToken` model
- Monitor application logs for the new debug messages
- Watch for patterns in token expiration

### 2. **Enable Debug Logging**
To see the detailed token debugging, ensure debug logging is enabled:
```python
import logging
logging.getLogger('app.models.api_token').setLevel(logging.DEBUG)
```

### 3. **Run Debug Script**
If issues persist, run the debug script:
```bash
python scripts/debug_token_expiration.py
```

### 4. **Verify Token Refresh Timing**
The 30-second buffer means tokens will be considered expired 30 seconds before their actual expiration. Ensure the token refresh service (which runs every 5 minutes) is working correctly and refresh tokens before the 10-minute threshold.

### 5. **Monitor Token Lifetimes**
Consider logging actual token lifetimes received from APIs to ensure they match expected values:
- Genesys tokens typically last 24 hours
- Microsoft Graph tokens typically last 1 hour

## Prevention Measures

### 1. **Automated Testing**
The test scripts created can be integrated into a CI/CD pipeline to prevent regression.

### 2. **Monitoring**
Set up alerts for:
- Frequent token refresh failures
- Services reporting "no valid token" errors
- Unusual patterns in token expiration

### 3. **Documentation**
Updated the `ApiToken` model with clear documentation of the expiration logic and buffer reasoning.

## Files Modified

1. `/home/administrator/Repos/WhoDis/app/models/api_token.py` - Enhanced expiration logic
2. `/home/administrator/Repos/WhoDis/scripts/debug_token_expiration.py` - New debugging tool
3. `/home/administrator/Repos/WhoDis/quick_token_test.py` - New testing tool
4. `/home/administrator/Repos/WhoDis/test_token_logic.py` - New validation tool

The fixes address the core timezone and timing issues while providing comprehensive debugging capabilities for future troubleshooting.