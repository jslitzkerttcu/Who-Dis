# Enable HTTP Strict Transport Security (HSTS) Header

## Overview

The Strict-Transport-Security header is currently commented out in app/middleware/security_headers.py (line 47). Without HSTS, browsers may still accept HTTP connections initially before being redirected to HTTPS, creating a window for SSL stripping attacks.

## Rationale

HSTS ensures that browsers only connect via HTTPS after the first visit, preventing man-in-the-middle attacks where an attacker could intercept the initial HTTP request and redirect users to a malicious site. For an identity lookup service handling employee PII, this is a critical protection.

---
*This spec was created from ideation and is pending detailed specification.*
