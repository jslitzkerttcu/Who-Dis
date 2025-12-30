# Job Role Compliance Matrix

A comprehensive system for managing and auditing user role compliance across multiple integrated systems (Active Directory, Genesys Cloud, Microsoft Graph, etc.).

## Table of Contents
- [Overview](#overview)
- [Core Components](#core-components)
- [Admin Interface](#admin-interface)
- [Performance Optimizations](#performance-optimizations)
- [Data Warehouse Integration](#data-warehouse-integration)
- [Usage Guide](#usage-guide)

## Overview

The Job Role Compliance Matrix ensures that users have the correct system access based on their job code. It maps job codes from UKG/data warehouse to expected roles across all integrated systems and validates actual user roles against these expectations.

**Key Capabilities:**
- Define expected system roles for each job code
- Validate actual user roles against expected roles
- Identify users with missing or extra privileges
- Bulk import/export role mappings via CSV
- Full audit trail of all mapping changes
- Integration with data warehouse for automatic synchronization

## Core Components

### Data Models (`app/models/job_role_compliance.py`)

#### JobCode Model

Stores job codes from UKG/data warehouse with metadata.

**Fields:**
- `job_code`: Unique job code identifier (e.g., "ENG001", "MGR042")
- `job_title`: Human-readable title (e.g., "Software Engineer", "Branch Manager")
- `department`: Department name for filtering and organization
- `job_family`: Broader categorization (optional)
- `job_level`: Level within organization (optional)
- `description`: Detailed description of the role
- `is_active`: Whether this job code is currently in use
- `synced_at`: Last synchronization timestamp from data warehouse
- `data`: JSONB field for additional metadata

**Relationships:**
- Has many `JobRoleMapping` entries (cascade delete)

**Key Methods:**
```python
JobCode.get_by_job_code("ENG001")  # Get specific job code
JobCode.get_active_job_codes()  # Get all active codes
JobCode.sync_from_warehouse(data)  # Bulk sync from warehouse
```

#### SystemRole Model

Defines available roles across all integrated systems.

**Fields:**
- `role_name`: Unique role identifier (e.g., "AD_Sales_Team", "Genesys_Queue_Support")
- `system_name`: Source system (e.g., "Active Directory", "Genesys Cloud", "Microsoft Graph")
- `description`: What this role provides access to
- `role_type`: Category (e.g., "security_group", "queue", "license")
- `is_active`: Whether this role is currently available
- `data`: JSONB field for role-specific metadata

**Relationships:**
- Has many `JobRoleMapping` entries (cascade delete)

**Key Methods:**
```python
SystemRole.get_by_role_name("AD_Sales_Team")
SystemRole.get_by_system("Active Directory")
SystemRole.get_active_roles()
```

#### JobRoleMapping Model

Many-to-many mapping between job codes and system roles.

**Fields:**
- `job_code_id`: Foreign key to JobCode
- `system_role_id`: Foreign key to SystemRole
- `is_required`: Whether this role is mandatory for the job code
- `notes`: Explanation for why this mapping exists
- `created_by`: User who created the mapping
- `created_at`, `updated_at`: Timestamps

**Relationships:**
- Belongs to `JobCode`
- Belongs to `SystemRole`

**Unique Constraint:**
- (`job_code_id`, `system_role_id`) - prevents duplicate mappings

## Admin Interface

### Routes (`/admin/job-role-compliance`)

#### Job Codes Management (`/admin/job-role-compliance/job-codes`)

**Features:**
- Paginated table of all job codes with search
- Mapping count for each job code (optimized with bulk query)
- Add/edit/deactivate job codes
- Sync button to pull latest from data warehouse
- CSV export for backup

**Performance Note:** Uses single bulk query to get mapping counts instead of N+1 individual queries:
```python
# Optimized approach
mapping_counts = db.session.query(
    JobRoleMapping.job_code_id,
    func.count(JobRoleMapping.id)
).group_by(JobRoleMapping.job_code_id).all()
```

#### System Roles Management (`/admin/job-role-compliance/system-roles`)

**Features:**
- List all system roles grouped by system
- Add/edit/deactivate roles
- Filter by system name
- Bulk import from CSV

#### Mapping Matrix (`/admin/job-role-compliance/matrix`)

**Features:**
- Efficient filtered table showing only existing mappings
- Client-side filtering by department, system, job code
- Progressive loading with "Load More" for large datasets
- Real-time search without server requests
- Add/remove mappings with validation
- Mark mappings as required/optional

**Key Optimization (v2.1.0):** Originally implemented as 131,097-cell grid (377 job codes × 348 system roles) which caused severe browser performance issues. Redesigned to show only existing mappings (~50-500 rows) with client-side filtering.

#### Compliance Dashboard (`/admin/job-role-compliance/compliance`)

**Features:**
- Shows users with missing required roles
- Shows users with extra roles not in their job code mapping
- Drill-down to see specific discrepancies
- Export compliance reports to CSV
- Filter by department, severity, system

## Performance Optimizations

### v2.1.0 Improvements

**Problem:** Initial matrix view rendered all 131,097 possible combinations, causing:
- Browser unresponsiveness (10+ seconds to render)
- Memory issues with large DOM
- Difficult navigation and filtering

**Solution:** Complete redesign with:

1. **Filtered Table Approach**
   - Only render existing mappings (~50-500 rows)
   - Client-side filtering for instant results
   - Progressive loading with "Load More" button

2. **N+1 Query Elimination**
   - Job codes table: single bulk query for mapping counts
   - Matrix view: eager loading with `joinedload()`

3. **Client-Side Filtering**
   ```javascript
   // Real-time filtering without server requests
   function filterMappings() {
       const dept = departmentFilter.value;
       const system = systemFilter.value;
       rows.forEach(row => {
           row.hidden = !matches(row, dept, system);
       });
   }
   ```

4. **Database Indexes**
   ```sql
   CREATE INDEX idx_job_codes_job_code ON job_codes(job_code);
   CREATE INDEX idx_job_codes_is_active ON job_codes(is_active);
   CREATE INDEX idx_system_roles_system_name ON system_roles(system_name);
   CREATE INDEX idx_job_role_mappings_job_code_id ON job_role_mappings(job_code_id);
   CREATE INDEX idx_job_role_mappings_system_role_id ON job_role_mappings(system_role_id);
   ```

### Performance Best Practices

1. **Use Bulk Queries**: Avoid N+1 queries with `joinedload()` or bulk aggregation
2. **Client-Side Filtering**: For datasets < 1000 rows, filter in browser
3. **Progressive Loading**: Render initial 50 rows, load more on demand
4. **Lazy Data Loading**: Don't fetch compliance data until user requests it
5. **Cache Aggressively**: Cache warehouse sync data for 24 hours

## Data Warehouse Integration

### Warehouse Service (`app/services/job_role_warehouse_service.py`)

Integrates with SQL Server data warehouse via `pyodbc` to pull job codes and current user role assignments.

**Configuration:**
```python
# In database configuration
WAREHOUSE_SERVER = "warehouse.example.com"
WAREHOUSE_DATABASE = "HR_Analytics"
WAREHOUSE_USER = "whodis_reader"
WAREHOUSE_PASSWORD = "encrypted_password"
```

**Key Operations:**

#### Sync Job Codes
```python
# Pull all job codes from warehouse
job_codes = warehouse_service.get_job_codes()

# Upsert into local database
for code_data in job_codes:
    JobCode.upsert_from_warehouse(code_data)
```

#### Get User's Expected Roles
```python
# Based on user's job code, what roles should they have?
user_job_code = "ENG001"
expected_roles = JobRoleMapping.get_roles_for_job_code(user_job_code)
```

#### Get User's Actual Roles
```python
# What roles does the user actually have in each system?
actual_roles = {
    'ad_groups': ldap_service.get_user_groups(user_email),
    'genesys_queues': genesys_service.get_user_queues(user_id),
    'graph_licenses': graph_service.get_user_licenses(user_id)
}
```

#### Compliance Check
```python
# Compare expected vs actual
compliance = compliance_service.check_user_compliance(
    user_email=user_email,
    expected_roles=expected_roles,
    actual_roles=actual_roles
)

# Returns:
{
    'missing_roles': [...],  # Required roles user doesn't have
    'extra_roles': [...],    # Roles user has but shouldn't
    'compliant': True/False
}
```

### Sync Schedule

**Manual Sync:** Admin can trigger via "Sync from Warehouse" button
**Automatic Sync:** Scheduled daily at 2 AM via background job (optional)

**Sync Process:**
1. Connect to warehouse via pyodbc
2. Query `HR.JobCodes` table for active job codes
3. Query `HR.EmployeeJobCodes` for current assignments
4. Upsert job codes into local `job_codes` table
5. Mark codes not in warehouse as inactive
6. Log sync results to audit log

## Usage Guide

### For Admins

#### Initial Setup

1. **Sync Job Codes from Warehouse**
   - Navigate to Job Codes tab
   - Click "Sync from Warehouse"
   - Verify all active job codes appear

2. **Add System Roles**
   - Navigate to System Roles tab
   - Add roles from each integrated system:
     - Active Directory security groups
     - Genesys queues, skills, and roles
     - Microsoft Graph licenses
     - Any custom application roles

3. **Create Mappings**
   - Navigate to Matrix tab
   - For each job code, add expected system roles
   - Mark critical roles as "Required"
   - Add notes explaining why each role is needed

#### Ongoing Maintenance

**Weekly:**
- Review compliance dashboard for discrepancies
- Address users with missing required roles
- Investigate users with unexpected extra roles

**Monthly:**
- Re-sync job codes from warehouse
- Update mappings for new or changed job codes
- Export mappings as CSV backup

**Quarterly:**
- Audit all mappings for accuracy
- Remove mappings for inactive job codes
- Update role descriptions

### For Developers

#### Adding a New System

1. **Add System Roles**
   ```python
   # Create roles for the new system
   role = SystemRole(
       role_name="NewSystem_Admin",
       system_name="New System",
       description="Admin access to New System",
       role_type="admin_group"
   )
   role.save()
   ```

2. **Update Compliance Service**
   ```python
   # Add new system to compliance checking
   def check_user_compliance(user):
       actual_roles = {
           # ... existing systems
           'newsystem_roles': new_system_service.get_user_roles(user.id)
       }
   ```

3. **Update Warehouse Integration**
   ```python
   # If new system data comes from warehouse
   def sync_newsystem_roles():
       roles = warehouse_service.get_newsystem_roles()
       for role_data in roles:
           SystemRole.upsert_from_warehouse(role_data)
   ```

## API Reference

See [Architecture Documentation](architecture.md#service-layer) for details on:
- `JobRoleMappingService`: CRUD operations for mappings
- `JobRoleWarehouseService`: Warehouse integration
- `ComplianceCheckingService`: Compliance validation

## Troubleshooting

**Issue:** Warehouse sync fails
- Check database connection string in encrypted config
- Verify warehouse credentials are valid
- Check firewall rules allow connection from app server
- Review error logs: `SELECT * FROM error_log WHERE message LIKE '%warehouse%'`

**Issue:** Compliance check shows false positives
- Verify role names match exactly between systems
- Check for case sensitivity issues
- Ensure warehouse data is current (recent sync)

**Issue:** Matrix page loads slowly
- Check if filtering is client-side (should be instant)
- Verify progressive loading is enabled
- Review browser console for JavaScript errors
- Check mapping count (should be < 10,000 for good performance)

## References

- [Architecture Documentation](architecture.md)
- [Database Documentation](database.md)
- [Admin Blueprint Code](../app/blueprints/admin/job_role_compliance.py)
