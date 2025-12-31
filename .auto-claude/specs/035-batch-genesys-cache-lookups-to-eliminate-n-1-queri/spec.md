# Batch Genesys Cache Lookups to Eliminate N+1 Queries

## Overview

When processing user data in genesys_service.py, individual database queries are made for each skill, group, and location in a user's profile via get_skill_name(), get_group_name(), and get_location_info() methods. A user with 5 skills, 3 groups, and 2 locations causes 10 additional database queries.

## Rationale

The Genesys cache lookup methods are called inside loops in _process_expanded_user_data() and get_user_by_id(). Each call performs a separate database query. With typical users having multiple skills/groups/locations, this compounds quickly and adds 50-200ms to search results.

---
*This spec was created from ideation and is pending detailed specification.*
