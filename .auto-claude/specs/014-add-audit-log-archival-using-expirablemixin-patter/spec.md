# Add Audit Log Archival Using ExpirableMixin Pattern

## Overview

Extend audit log management with automatic archival of old logs using the ExpirableMixin pattern. Add cleanup_old_logs() method to AuditLog model and admin UI controls for log retention management.

## Rationale

The ExpirableMixin already provides cleanup_expired() and extends_expiration() methods. CacheableModel uses this for cache cleanup. AuditLog extends AuditableModel but doesn't have log retention/archival. The pattern for bulk cleanup exists and can be directly applied.

---
*This spec was created from ideation and is pending detailed specification.*
