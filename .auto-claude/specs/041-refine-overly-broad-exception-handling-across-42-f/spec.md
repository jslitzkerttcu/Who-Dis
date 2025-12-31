# Refine overly broad exception handling across 42 files

## Overview

The codebase contains 260 instances of 'except Exception' across 42 files. Many of these catch-all handlers silently swallow errors or log generic messages, making debugging difficult and potentially hiding important failures. The worst offenders are audit_service_postgres.py (21), genesys_cache_db.py (12), ldap_service.py (12), and simple_config.py (10).

## Rationale

Broad exception handling: 1) Hides specific error types that callers might want to handle differently, 2) Makes debugging harder when logs show only 'Error occurred', 3) Can mask programming errors like AttributeError or KeyError, 4) Violates the principle of 'fail fast' for unexpected conditions. Some errors should propagate to trigger proper error handling upstream.

---
*This spec was created from ideation and is pending detailed specification.*
