# Note on Unified Models (June 2025)

## Current State

The WhoDis codebase contains unified model files (`unified_log.py`, `unified_cache.py`, `external_service.py`) that were created as part of a model consolidation effort documented in `model_consolidation_analysis.md`. However, these unified models are **NOT currently in use**.

## What's Actually Being Used

The application is still using the original separate models:
- `audit.py` → `audit_log` table
- `error.py` → `error_log` table  
- `access.py` → `access_attempts` table
- `cache.py` → `search_cache` table
- `api_token.py` → `api_tokens` table
- `genesys.py` → `genesys_groups`, `genesys_locations`, `genesys_skills` tables
- etc.

## Why the Unified Models Exist

1. They were created as part of a DRY/SOLID/KISS refactoring effort
2. The intention was to consolidate similar models to reduce code duplication
3. The unified models would have combined multiple tables into single tables with discriminator columns

## Why They're Not Being Used

1. **No Database Migration**: The database schema still uses the separate tables. The `create_tables.sql` file creates the original separate tables, not the unified ones.
2. **Incomplete Migration**: While the models were created, the actual migration of data and update of all code references was not completed.
3. **Backwards Compatibility**: The application needed to maintain compatibility with existing data.

## Current Code State (June 2025)

- All imports now use the actual separate models directly
- No aliases or references to unified models remain in the active code
- The unified model files exist but are not imported or used anywhere
- The `app/models/__init__.py` imports the actual separate models

## Future Consideration

If there's a desire to actually implement the unified models in the future, it would require:
1. Database migration scripts to combine the data
2. Update to `create_tables.sql`
3. Comprehensive testing of all functionality
4. Careful migration plan to avoid data loss

For now, the application continues to work correctly with the separate models, which provides clarity and avoids confusion.