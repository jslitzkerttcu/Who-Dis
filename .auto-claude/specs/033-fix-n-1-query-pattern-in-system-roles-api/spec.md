# Fix N+1 Query Pattern in System Roles API

## Overview

The api_system_roles() function in job_role_compliance.py has an N+1 query pattern where len(role.role_mappings) is called for each role in the paginated results, triggering a separate database query for each role to fetch its mappings count.

## Rationale

Each time the system roles API is called with 20 roles per page, 21 database queries are executed (1 for the roles + 20 for mapping counts). This pattern mirrors the already-fixed job_codes endpoint which properly uses a bulk mapping_count query. Applying the same pattern would reduce queries from O(n+1) to O(2).

---
*This spec was created from ideation and is pending detailed specification.*
