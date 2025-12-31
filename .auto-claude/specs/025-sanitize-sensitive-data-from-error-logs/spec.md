# Sanitize Sensitive Data from Error Logs

## Overview

The error handling middleware (app/middleware/errors.py) logs form data directly: `'form': dict(request.form) if request.form else None`. Additionally, configuration values aren't filtered before being logged. This creates risk of credentials or PII appearing in logs.

## Rationale

Error logs are often stored with less stringent access controls than production databases and may be shipped to third-party logging services. Logging sensitive form fields (passwords, tokens) or configuration values violates data protection principles and could lead to credential exposure.

---
*This spec was created from ideation and is pending detailed specification.*
