# Restrict Debug Mode Configuration in Production

## Overview

Debug mode can be enabled through the database configuration (flask.debug) via the admin UI. In debug mode, the error handler at app/middleware/errors.py (lines 68-70, 75-77) exposes full exception messages to users, which can leak internal paths, database schema, and API details.

## Rationale

If an attacker gains admin access or if debug mode is accidentally enabled, they can trigger errors to gather reconnaissance information about the application's internals. This information disclosure accelerates exploitation of other vulnerabilities.

---
*This spec was created from ideation and is pending detailed specification.*
