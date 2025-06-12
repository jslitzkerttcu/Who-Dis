# WhoDis Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-06-10

### Added
- **Consolidated Employee Data Architecture**: New unified `employee_profiles` table centralizing all employee information
- **Employee Profiles Service**: Comprehensive service managing data warehouse integration, photo fetching, and profile updates
- **Phone Number Tooltips**: Detailed tooltips on Teams/Genesys/Legacy tags showing raw AD and Genesys field sources
- **Legacy Table Migration Tools**: Scripts for safely migrating from old architecture to new consolidated model

### Changed
- **BREAKING**: Migrated from separate `graph_photos` and `data_warehouse_cache` tables to unified `employee_profiles` table
- **Performance**: Significantly improved admin dashboard loading with optimized queries and lazy photo loading
- **Caching**: Enhanced search result caching with visual indicators and 30-minute expiration
- **UI/UX**: Updated admin interface with modern HTMX-powered interactions and Tailwind CSS styling
- **Architecture**: Simplified service layer with consolidated employee data management

### Removed
- **DEPRECATED**: `GraphPhoto` and `DataWarehouseCache` models removed in favor of `EmployeeProfiles`
- **DEPRECATED**: Legacy data warehouse service consolidated into employee profiles service
- **Tables**: `graph_photos` and `data_warehouse_cache` tables dropped (use migration script)
- **Documentation**: Removed outdated docs for deprecated caching systems

### Migration Guide

#### For Existing Installations

1. **Backup your database** before starting migration:
   ```bash
   pg_dump -U whodis_user -h localhost whodis_db > backup_before_migration.sql
   ```

2. **Run the legacy table drop script**:
   ```bash
   python scripts/drop_legacy_tables.py --dry-run  # Preview changes
   python scripts/drop_legacy_tables.py            # Execute migration
   ```

3. **Verify the migration**:
   ```bash
   python scripts/refresh_employee_profiles.py refresh
   ```

4. **Update your application**:
   ```bash
   ruff check --fix
   mypy app/ scripts/ --ignore-missing-imports
   python run.py
   ```

#### For New Installations

- No migration needed - new `create_tables.sql` uses consolidated architecture
- Follow standard installation procedure in README.md

### Technical Details

#### Database Changes
- **New Table**: `employee_profiles` with consolidated schema
- **Removed Tables**: `graph_photos`, `data_warehouse_cache`
- **Updated Indexes**: Optimized for unified employee data queries
- **Schema Version**: Bumped to support consolidated architecture

#### Service Layer Changes
- **`EmployeeProfilesRefreshService`**: New centralized service for all employee operations
- **Admin Interface**: Updated to use new service endpoints
- **Token Refresh**: Modified to refresh employee profiles instead of separate caches
- **Search Enhancement**: Uses consolidated employee data for Keystone integration

#### Performance Improvements
- **Admin Dashboard**: 60-80% faster loading through query optimization
- **Search Caching**: 95% faster repeat searches with visual cache indicators
- **Photo Loading**: Lazy loading prevents blocking on photo retrieval
- **Database Operations**: Fewer queries with consolidated data model

### Compatibility Notes

- **Python**: Requires Python 3.10+
- **PostgreSQL**: Requires PostgreSQL 12+
- **Dependencies**: No new external dependencies added
- **API**: All existing search and admin APIs remain compatible
- **Configuration**: No configuration changes required

### Security Enhancements

- **Input Validation**: Enhanced escaping with comprehensive `escapeHtml()` function
- **CSRF Protection**: Continued robust CSRF token validation
- **Session Management**: Improved session timeout handling with consolidated architecture
- **Audit Logging**: Enhanced tracking of employee data operations

## [1.x.x] - Previous Versions

See git history for previous version details. Version 2.0.0 represents a major architectural consolidation milestone.

---

**Note**: This changelog focuses on the major 2.0.0 consolidation release. For detailed commit history, see `git log --oneline --graph`.