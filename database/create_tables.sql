-- WhoDis Database Schema
-- Updated to include base model structure
-- Run this after creating the database


-- API Tokens table (using CacheableModel)
CREATE TABLE IF NOT EXISTS api_tokens (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(50) UNIQUE NOT NULL,
    access_token TEXT NOT NULL,
    token_type VARCHAR(20) DEFAULT 'Bearer',
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    refresh_token TEXT,
    additional_data JSONB,
    last_refreshed TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_api_tokens_service_name ON api_tokens(service_name);
CREATE INDEX IF NOT EXISTS idx_api_tokens_expires_at ON api_tokens(expires_at);

-- Users table (using BaseModel + TimestampMixin)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
CREATE INDEX IF NOT EXISTS idx_users_last_login ON users(last_login);

-- User Notes table (using BaseModel + TimestampMixin)
CREATE TABLE IF NOT EXISTS user_notes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    note TEXT NOT NULL,
    created_by VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    context VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_notes_user_id ON user_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_user_notes_created_by ON user_notes(created_by);
CREATE INDEX IF NOT EXISTS idx_user_notes_is_active ON user_notes(is_active);

-- Configuration table
CREATE TABLE IF NOT EXISTS configuration (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100) NOT NULL,
    setting_key VARCHAR(100) NOT NULL,
    setting_value TEXT,
    data_type VARCHAR(20) DEFAULT 'string',
    description TEXT,
    is_sensitive BOOLEAN DEFAULT FALSE,
    validation_regex VARCHAR(255),
    min_value FLOAT,
    max_value FLOAT,
    default_value TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(255),
    encrypted_value BYTEA,
    encryption_method VARCHAR(50) DEFAULT 'fernet',
    UNIQUE(category, setting_key),
    CONSTRAINT check_encryption_exclusivity CHECK (
        NOT (encrypted_value IS NOT NULL AND setting_value IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_configuration_category_key ON configuration(category, setting_key);
CREATE INDEX IF NOT EXISTS idx_configuration_sensitive ON configuration(is_sensitive);

-- Configuration History table
CREATE TABLE IF NOT EXISTS configuration_history (
    id SERIAL PRIMARY KEY,
    config_id INTEGER NOT NULL,
    category VARCHAR(100) NOT NULL,
    setting_key VARCHAR(100) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    old_encrypted BOOLEAN DEFAULT FALSE,
    new_encrypted BOOLEAN DEFAULT FALSE,
    changed_by VARCHAR(255) NOT NULL,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    change_type VARCHAR(20) NOT NULL,
    change_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_config_history_config_id ON configuration_history(config_id);
CREATE INDEX IF NOT EXISTS idx_config_history_changed_at ON configuration_history(changed_at);

-- Audit Log table (using AuditableModel)
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    -- Base fields from AuditableModel
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_email VARCHAR(255) NOT NULL,
    user_agent TEXT,
    ip_address VARCHAR(45),
    session_id VARCHAR(255),
    success BOOLEAN DEFAULT TRUE,
    message TEXT,
    additional_data JSONB,
    -- Audit-specific fields
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- Synonym for created_at
    event_type VARCHAR(50) NOT NULL,
    user_role VARCHAR(50),
    action VARCHAR(100) NOT NULL,
    target_resource VARCHAR(500),
    search_query VARCHAR(500),
    search_results_count INTEGER,
    search_services TEXT -- JSON array
);

-- Indexes for audit_log
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user_email ON audit_log(user_email);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_search_query ON audit_log(search_query);
CREATE INDEX IF NOT EXISTS idx_audit_ip_address ON audit_log(ip_address);
CREATE INDEX IF NOT EXISTS idx_audit_success ON audit_log(success);

-- Error Log table (using AuditableModel)
CREATE TABLE IF NOT EXISTS error_log (
    id SERIAL PRIMARY KEY,
    -- Base fields from AuditableModel
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_email VARCHAR(255),
    user_agent TEXT,
    ip_address VARCHAR(45),
    session_id VARCHAR(255),
    success BOOLEAN DEFAULT FALSE, -- Errors are always failures
    message TEXT NOT NULL, -- Maps to error_message
    additional_data JSONB, -- Maps to request_data
    -- Error-specific fields
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- Synonym for created_at
    error_type VARCHAR(100) NOT NULL,
    stack_trace TEXT,
    request_path VARCHAR(500),
    request_method VARCHAR(10),
    severity VARCHAR(20) DEFAULT 'ERROR'
);

-- Indexes for error_log
CREATE INDEX IF NOT EXISTS idx_error_log_created_at ON error_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_error_timestamp ON error_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_error_type ON error_log(error_type);
CREATE INDEX IF NOT EXISTS idx_error_severity ON error_log(severity);

-- Access Attempts table (using AuditableModel)
CREATE TABLE IF NOT EXISTS access_attempts (
    id SERIAL PRIMARY KEY,
    -- Base fields from AuditableModel
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_email VARCHAR(255),
    user_agent TEXT,
    ip_address VARCHAR(45) NOT NULL,
    session_id VARCHAR(255),
    success BOOLEAN NOT NULL, -- Maps to access_granted
    message VARCHAR(255), -- Maps to denial_reason
    additional_data JSONB,
    -- Access-specific fields
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- Synonym for created_at
    requested_path VARCHAR(500),
    auth_method VARCHAR(50)
);

-- Indexes for access_attempts
CREATE INDEX IF NOT EXISTS idx_access_attempts_created_at ON access_attempts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_access_timestamp ON access_attempts(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_access_user_email ON access_attempts(user_email);
CREATE INDEX IF NOT EXISTS idx_access_ip_address ON access_attempts(ip_address);
CREATE INDEX IF NOT EXISTS idx_access_granted ON access_attempts(success);

-- Search cache table (using CacheableModel)
CREATE TABLE IF NOT EXISTS search_cache (
    id SERIAL PRIMARY KEY,
    search_query VARCHAR(500) NOT NULL,
    search_type VARCHAR(50) NOT NULL,
    result_data JSONB NOT NULL,
    additional_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_search_cache_query ON search_cache(search_query, search_type);
CREATE INDEX IF NOT EXISTS idx_search_cache_expires ON search_cache(expires_at);

-- Genesys Groups table (using ServiceDataModel)
CREATE TABLE IF NOT EXISTS genesys_groups (
    id VARCHAR(100) PRIMARY KEY,
    service_id VARCHAR(255) NOT NULL,
    service_name VARCHAR(100) NOT NULL DEFAULT 'genesys',
    name VARCHAR(255) NOT NULL,
    description TEXT,
    member_count INTEGER,
    date_modified TIMESTAMP WITH TIME ZONE,
    raw_data JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    additional_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Synonym for updated_at
);

CREATE INDEX IF NOT EXISTS idx_genesys_groups_service ON genesys_groups(service_name, service_id);
CREATE INDEX IF NOT EXISTS idx_genesys_groups_name ON genesys_groups(name);
CREATE INDEX IF NOT EXISTS idx_genesys_groups_is_active ON genesys_groups(is_active);

-- Genesys Locations table (using ServiceDataModel)
CREATE TABLE IF NOT EXISTS genesys_locations (
    id VARCHAR(100) PRIMARY KEY,
    service_id VARCHAR(255) NOT NULL,
    service_name VARCHAR(100) NOT NULL DEFAULT 'genesys',
    name VARCHAR(255) NOT NULL,
    emergency_number VARCHAR(50),
    address JSONB,
    raw_data JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    additional_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Synonym for updated_at
);

CREATE INDEX IF NOT EXISTS idx_genesys_locations_service ON genesys_locations(service_name, service_id);
CREATE INDEX IF NOT EXISTS idx_genesys_locations_name ON genesys_locations(name);
CREATE INDEX IF NOT EXISTS idx_genesys_locations_is_active ON genesys_locations(is_active);

-- Genesys Skills table (using ServiceDataModel)
CREATE TABLE IF NOT EXISTS genesys_skills (
    id VARCHAR(100) PRIMARY KEY,
    service_id VARCHAR(255) NOT NULL,
    service_name VARCHAR(100) NOT NULL DEFAULT 'genesys',
    name VARCHAR(255) NOT NULL,
    raw_data JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    additional_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    cached_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Synonym for updated_at
);

CREATE INDEX IF NOT EXISTS idx_genesys_skills_service ON genesys_skills(service_name, service_id);
CREATE INDEX IF NOT EXISTS idx_genesys_skills_name ON genesys_skills(name);
CREATE INDEX IF NOT EXISTS idx_genesys_skills_is_active ON genesys_skills(is_active);

-- REMOVED: graph_photos table - consolidated into employee_profiles

-- User Sessions table (using BaseModel + TimestampMixin + ExpirableMixin)
CREATE TABLE IF NOT EXISTS user_sessions (
    id VARCHAR(255) PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    user_email VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    warning_shown BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_session_user_email ON user_sessions(user_email);
CREATE INDEX IF NOT EXISTS idx_session_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_session_expires ON user_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_session_is_active ON user_sessions(is_active);

-- REMOVED: data_warehouse_cache table - consolidated into employee_profiles

-- Employee Profiles consolidated table
CREATE TABLE IF NOT EXISTS employee_profiles (
    upn VARCHAR(255) PRIMARY KEY,
    
    -- Keystone fields
    ks_user_serial INTEGER,
    ks_last_login_time TIMESTAMP WITH TIME ZONE,
    ks_login_lock VARCHAR(1),
    
    -- Role fields  
    live_role VARCHAR(255),
    test_role VARCHAR(255),
    keystone_expected_role VARCHAR(255),
    
    -- UKG field
    ukg_job_code VARCHAR(50),
    
    -- Photo fields
    photo_data BYTEA,
    photo_content_type VARCHAR(50) DEFAULT 'image/jpeg',
    
    -- Raw data storage
    raw_data JSONB,
    
    -- Timestamp fields
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for employee_profiles table
CREATE INDEX IF NOT EXISTS idx_employee_profiles_ks_login_lock ON employee_profiles(ks_login_lock);
CREATE INDEX IF NOT EXISTS idx_employee_profiles_live_role ON employee_profiles(live_role);
CREATE INDEX IF NOT EXISTS idx_employee_profiles_upn ON employee_profiles(upn);
CREATE INDEX IF NOT EXISTS idx_employee_profiles_keystone_expected_role ON employee_profiles(keystone_expected_role);
CREATE INDEX IF NOT EXISTS idx_employee_profiles_created_at ON employee_profiles(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_employee_profiles_updated_at ON employee_profiles(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_employee_profiles_ukg_job_code ON employee_profiles(ukg_job_code);
CREATE INDEX IF NOT EXISTS idx_employee_profiles_ks_user_serial ON employee_profiles(ks_user_serial);
CREATE INDEX IF NOT EXISTS idx_employee_profiles_raw_data_gin ON employee_profiles USING GIN (raw_data);

-- Create views for common queries
CREATE OR REPLACE VIEW recent_searches AS
SELECT 
    created_at as timestamp,
    user_email,
    search_query,
    search_results_count,
    search_services,
    ip_address
FROM audit_log
WHERE event_type = 'search'
ORDER BY created_at DESC
LIMIT 100;

CREATE OR REPLACE VIEW failed_access_attempts AS
SELECT 
    created_at as timestamp,
    user_email,
    ip_address,
    requested_path,
    message as denial_reason
FROM access_attempts
WHERE success = FALSE
ORDER BY created_at DESC
LIMIT 100;

-- Function to clean up old data
CREATE OR REPLACE FUNCTION cleanup_old_data() RETURNS void AS $$
BEGIN
    -- Delete audit logs older than 90 days
    DELETE FROM audit_log WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '90 days';
    
    -- Delete error logs older than 30 days
    DELETE FROM error_log WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
    
    -- Delete access attempts older than 30 days
    DELETE FROM access_attempts WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
    
    -- Delete expired search cache
    DELETE FROM search_cache WHERE expires_at < CURRENT_TIMESTAMP;
    
    -- Delete expired sessions
    DELETE FROM user_sessions WHERE expires_at < CURRENT_TIMESTAMP;
    
    -- Clean up old Genesys cache (older than 30 days)
    DELETE FROM genesys_groups WHERE updated_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
    DELETE FROM genesys_locations WHERE updated_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
    DELETE FROM genesys_skills WHERE updated_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
    
    -- Clean up old Employee Profiles cache (older than 30 days)
    DELETE FROM employee_profiles WHERE updated_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
    
    -- Clean up job role compliance data (calls the specialized function)
    PERFORM cleanup_old_compliance_data();
END;
$$ LANGUAGE plpgsql;

-- Insert default configuration values
INSERT INTO configuration (category, setting_key, setting_value, data_type, description, is_sensitive) VALUES
-- Non-sensitive Flask settings
('flask', 'host', '0.0.0.0', 'string', 'Flask application host', FALSE),
('flask', 'port', '5000', 'integer', 'Flask application port', FALSE),
('flask', 'debug', 'False', 'boolean', 'Enable Flask debug mode', FALSE),

-- Non-sensitive LDAP settings
('ldap', 'host', '', 'string', 'LDAP server host URL', FALSE),
('ldap', 'port', '389', 'integer', 'LDAP server port', FALSE),
('ldap', 'use_ssl', 'False', 'boolean', 'Use SSL for LDAP connection', FALSE),
('ldap', 'base_dn', '', 'string', 'LDAP base distinguished name', FALSE),
('ldap', 'user_search_base', '', 'string', 'LDAP user search base DN', FALSE),
('ldap', 'connect_timeout', '5', 'integer', 'LDAP connection timeout in seconds', FALSE),
('ldap', 'operation_timeout', '10', 'integer', 'LDAP operation timeout in seconds', FALSE),

-- Non-sensitive Genesys settings
('genesys', 'region', '', 'string', 'Genesys Cloud region', FALSE),
('genesys', 'api_timeout', '15', 'integer', 'Genesys API timeout in seconds', FALSE),
('genesys', 'cache_timeout', '30', 'integer', 'Genesys cache refresh timeout in seconds', FALSE),
('genesys', 'cache_refresh_period', '21600', 'integer', 'Genesys cache refresh period in seconds (default 6 hours)', FALSE),

-- Non-sensitive Graph settings
('graph', 'api_timeout', '15', 'integer', 'Microsoft Graph API timeout in seconds', FALSE),

-- Non-sensitive Data Warehouse settings
('data_warehouse', 'database', 'CUFX', 'string', 'Data warehouse database name', FALSE),
('data_warehouse', 'connection_timeout', '30', 'integer', 'Data warehouse connection timeout in seconds', FALSE),
('data_warehouse', 'query_timeout', '60', 'integer', 'Data warehouse query timeout in seconds', FALSE),
('data_warehouse', 'cache_refresh_hours', '6.0', 'float', 'Data warehouse cache refresh period in hours', FALSE),

-- Search settings
('search', 'overall_timeout', '20', 'integer', 'Overall search timeout in seconds', FALSE),
('search', 'lazy_load_photos', 'true', 'boolean', 'Enable lazy loading of user photos for better performance', FALSE),

-- Session settings
('session', 'timeout_minutes', '15', 'integer', 'Session timeout in minutes (default 15)', FALSE),
('session', 'warning_minutes', '2', 'integer', 'Minutes before timeout to show warning (default 2)', FALSE),
('session', 'check_interval_seconds', '30', 'integer', 'How often to check session validity in seconds', FALSE),

-- CSRF protection settings
('csrf', 'cookie_name', 'whodis-csrf-token', 'string', 'Name of the CSRF protection cookie', FALSE),
('csrf', 'cookie_secure', 'False', 'boolean', 'Whether CSRF cookie requires HTTPS (set True in production)', FALSE),
('csrf', 'cookie_httponly', 'False', 'boolean', 'Whether CSRF cookie is HTTP-only (must be False for JS access)', FALSE),
('csrf', 'cookie_samesite', 'Strict', 'string', 'SameSite attribute for CSRF cookie', FALSE),
('csrf', 'cookie_path', '/', 'string', 'Path attribute for CSRF cookie', FALSE),
('csrf', 'header_name', 'X-CSRF-Token', 'string', 'HTTP header name for CSRF token', FALSE),
('csrf', 'token_expire', '3600', 'integer', 'CSRF token expiration time in seconds (default 1 hour)', FALSE),

-- Sensitive settings (will be populated during setup)
('auth', 'viewers', NULL, 'string', 'Comma-separated list of viewer emails', TRUE),
('auth', 'editors', NULL, 'string', 'Comma-separated list of editor emails', TRUE),
('auth', 'admins', NULL, 'string', 'Comma-separated list of admin emails', TRUE),
('ldap', 'bind_dn', NULL, 'string', 'LDAP bind distinguished name', TRUE),
('ldap', 'bind_password', NULL, 'string', 'LDAP bind password', TRUE),
('genesys', 'client_id', NULL, 'string', 'Genesys Cloud client ID', TRUE),
('genesys', 'client_secret', NULL, 'string', 'Genesys Cloud client secret', TRUE),
('graph', 'tenant_id', NULL, 'string', 'Microsoft Graph tenant ID', TRUE),
('graph', 'client_id', NULL, 'string', 'Microsoft Graph client ID', TRUE),
('graph', 'client_secret', NULL, 'string', 'Microsoft Graph client secret', TRUE),
('data_warehouse', 'server', NULL, 'string', 'Data warehouse SQL Server hostname', TRUE),
('data_warehouse', 'client_id', NULL, 'string', 'Data warehouse Azure AD client ID', TRUE),
('data_warehouse', 'client_secret', NULL, 'string', 'Data warehouse Azure AD client secret', TRUE),
('flask', 'secret_key', NULL, 'string', 'Flask secret key for sessions', TRUE)
ON CONFLICT (category, setting_key) DO NOTHING;

-- Add default admin user (should be updated after installation)
INSERT INTO users (email, role, is_active) VALUES
('admin@example.com', 'admin', TRUE)
ON CONFLICT (email) DO NOTHING;

-- ============================================================================
-- Job Role Compliance Matrix Schema
-- ============================================================================
-- Added: 2025-06-12 - Complete job role compliance tracking system

-- Job Codes table - stores all possible job codes from UKG/data warehouse
CREATE TABLE IF NOT EXISTS job_codes (
    id SERIAL PRIMARY KEY,
    job_code VARCHAR(50) UNIQUE NOT NULL,
    job_title VARCHAR(255) NOT NULL,
    department VARCHAR(255),
    job_family VARCHAR(100),
    job_level VARCHAR(50),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    additional_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- System Roles table - stores all possible roles across systems (Keystone, AD groups, etc.)
CREATE TABLE IF NOT EXISTS system_roles (
    id SERIAL PRIMARY KEY,
    role_name VARCHAR(255) NOT NULL,
    system_name VARCHAR(100) NOT NULL, -- 'keystone', 'ad_groups', 'genesys', etc.
    role_type VARCHAR(50) NOT NULL, -- 'application', 'security_group', 'distribution_list', etc.
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    additional_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(role_name, system_name, role_type)
);

-- Job Role Mappings table - defines expected roles for each job code
CREATE TABLE IF NOT EXISTS job_role_mappings (
    id SERIAL PRIMARY KEY,
    job_code_id INTEGER NOT NULL REFERENCES job_codes(id) ON DELETE CASCADE,
    system_role_id INTEGER NOT NULL REFERENCES system_roles(id) ON DELETE CASCADE,
    mapping_type VARCHAR(50) NOT NULL DEFAULT 'required', -- 'required', 'optional', 'prohibited'
    priority INTEGER DEFAULT 1, -- for ordering/importance
    effective_date DATE DEFAULT CURRENT_DATE,
    expiration_date DATE,
    notes TEXT,
    created_by VARCHAR(255) NOT NULL,
    additional_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_code_id, system_role_id)
);

-- Job Role Mapping History table - tracks all changes to mappings
CREATE TABLE IF NOT EXISTS job_role_mapping_history (
    id SERIAL PRIMARY KEY,
    mapping_id INTEGER REFERENCES job_role_mappings(id) ON DELETE CASCADE,
    job_code VARCHAR(50) NOT NULL,
    role_name VARCHAR(255) NOT NULL,
    system_name VARCHAR(100) NOT NULL,
    old_mapping_type VARCHAR(50),
    new_mapping_type VARCHAR(50),
    old_priority INTEGER,
    new_priority INTEGER,
    change_type VARCHAR(20) NOT NULL, -- 'created', 'updated', 'deleted'
    changed_by VARCHAR(255) NOT NULL,
    change_reason TEXT,
    additional_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Compliance Checks table - stores results of compliance checking runs
CREATE TABLE IF NOT EXISTS compliance_checks (
    id SERIAL PRIMARY KEY,
    check_run_id VARCHAR(100) NOT NULL, -- unique identifier for each check run
    employee_upn VARCHAR(255) NOT NULL,
    job_code VARCHAR(50) NOT NULL,
    system_name VARCHAR(100) NOT NULL,
    role_name VARCHAR(255) NOT NULL,
    expected_mapping_type VARCHAR(50), -- what the mapping says it should be
    actual_assignment BOOLEAN NOT NULL, -- whether they actually have the role
    compliance_status VARCHAR(50) NOT NULL, -- 'compliant', 'missing_required', 'has_prohibited', 'unexpected_role'
    violation_severity VARCHAR(20) DEFAULT 'medium', -- 'low', 'medium', 'high', 'critical'
    notes TEXT,
    remediation_action VARCHAR(100), -- 'add_role', 'remove_role', 'no_action', 'manual_review'
    additional_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Compliance Check Runs table - metadata about each compliance checking run
CREATE TABLE IF NOT EXISTS compliance_check_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(100) UNIQUE NOT NULL,
    run_type VARCHAR(50) NOT NULL DEFAULT 'manual', -- 'manual', 'scheduled', 'triggered'
    scope VARCHAR(100) DEFAULT 'all', -- 'all', 'department', 'job_code', 'individual'
    scope_filter VARCHAR(255), -- additional filter criteria
    total_employees INTEGER DEFAULT 0,
    total_checks INTEGER DEFAULT 0,
    compliant_count INTEGER DEFAULT 0,
    violation_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    duration_seconds INTEGER,
    status VARCHAR(50) DEFAULT 'running', -- 'running', 'completed', 'failed', 'cancelled'
    started_by VARCHAR(255) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    additional_data JSONB DEFAULT '{}'
);

-- Employee Role Assignments cache - current roles from all systems
CREATE TABLE IF NOT EXISTS employee_role_assignments (
    id SERIAL PRIMARY KEY,
    employee_upn VARCHAR(255) NOT NULL,
    system_name VARCHAR(100) NOT NULL,
    role_name VARCHAR(255) NOT NULL,
    assignment_type VARCHAR(50) DEFAULT 'direct', -- 'direct', 'inherited', 'nested_group'
    assignment_source VARCHAR(255), -- source group/container if inherited
    is_active BOOLEAN DEFAULT TRUE,
    assigned_date TIMESTAMP WITH TIME ZONE,
    last_verified TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    additional_data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(employee_upn, system_name, role_name)
);

-- Indexes for Job Role Compliance performance
CREATE INDEX IF NOT EXISTS idx_job_codes_job_code ON job_codes(job_code);
CREATE INDEX IF NOT EXISTS idx_job_codes_is_active ON job_codes(is_active);
CREATE INDEX IF NOT EXISTS idx_job_codes_department ON job_codes(department);
CREATE INDEX IF NOT EXISTS idx_job_codes_synced_at ON job_codes(synced_at);

CREATE INDEX IF NOT EXISTS idx_system_roles_system_name ON system_roles(system_name);
CREATE INDEX IF NOT EXISTS idx_system_roles_role_type ON system_roles(role_type);
CREATE INDEX IF NOT EXISTS idx_system_roles_is_active ON system_roles(is_active);
CREATE INDEX IF NOT EXISTS idx_system_roles_synced_at ON system_roles(synced_at);

CREATE INDEX IF NOT EXISTS idx_job_role_mappings_job_code_id ON job_role_mappings(job_code_id);
CREATE INDEX IF NOT EXISTS idx_job_role_mappings_system_role_id ON job_role_mappings(system_role_id);
CREATE INDEX IF NOT EXISTS idx_job_role_mappings_mapping_type ON job_role_mappings(mapping_type);
CREATE INDEX IF NOT EXISTS idx_job_role_mappings_effective_date ON job_role_mappings(effective_date);
CREATE INDEX IF NOT EXISTS idx_job_role_mappings_created_by ON job_role_mappings(created_by);

CREATE INDEX IF NOT EXISTS idx_job_role_mapping_history_mapping_id ON job_role_mapping_history(mapping_id);
CREATE INDEX IF NOT EXISTS idx_job_role_mapping_history_changed_by ON job_role_mapping_history(changed_by);
CREATE INDEX IF NOT EXISTS idx_job_role_mapping_history_created_at ON job_role_mapping_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_role_mapping_history_change_type ON job_role_mapping_history(change_type);

CREATE INDEX IF NOT EXISTS idx_compliance_checks_check_run_id ON compliance_checks(check_run_id);
CREATE INDEX IF NOT EXISTS idx_compliance_checks_employee_upn ON compliance_checks(employee_upn);
CREATE INDEX IF NOT EXISTS idx_compliance_checks_job_code ON compliance_checks(job_code);
CREATE INDEX IF NOT EXISTS idx_compliance_checks_compliance_status ON compliance_checks(compliance_status);
CREATE INDEX IF NOT EXISTS idx_compliance_checks_violation_severity ON compliance_checks(violation_severity);
CREATE INDEX IF NOT EXISTS idx_compliance_checks_system_name ON compliance_checks(system_name);
CREATE INDEX IF NOT EXISTS idx_compliance_checks_created_at ON compliance_checks(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_compliance_check_runs_run_id ON compliance_check_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_compliance_check_runs_status ON compliance_check_runs(status);
CREATE INDEX IF NOT EXISTS idx_compliance_check_runs_started_by ON compliance_check_runs(started_by);
CREATE INDEX IF NOT EXISTS idx_compliance_check_runs_started_at ON compliance_check_runs(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_employee_role_assignments_employee_upn ON employee_role_assignments(employee_upn);
CREATE INDEX IF NOT EXISTS idx_employee_role_assignments_system_name ON employee_role_assignments(system_name);
CREATE INDEX IF NOT EXISTS idx_employee_role_assignments_role_name ON employee_role_assignments(role_name);
CREATE INDEX IF NOT EXISTS idx_employee_role_assignments_is_active ON employee_role_assignments(is_active);
CREATE INDEX IF NOT EXISTS idx_employee_role_assignments_last_verified ON employee_role_assignments(last_verified);

-- Job Role Compliance Views for common queries
CREATE OR REPLACE VIEW compliance_violations AS
SELECT 
    cc.employee_upn,
    cc.job_code,
    cc.system_name,
    cc.role_name,
    cc.compliance_status,
    cc.violation_severity,
    cc.remediation_action,
    cc.created_at,
    ccr.started_by as check_run_by,
    ccr.started_at as check_run_date
FROM compliance_checks cc
JOIN compliance_check_runs ccr ON cc.check_run_id = ccr.run_id
WHERE cc.compliance_status != 'compliant'
ORDER BY cc.violation_severity DESC, cc.created_at DESC;

CREATE OR REPLACE VIEW latest_compliance_status AS
WITH latest_runs AS (
    SELECT employee_upn, system_name, role_name, 
           MAX(created_at) as latest_check
    FROM compliance_checks
    GROUP BY employee_upn, system_name, role_name
)
SELECT cc.*
FROM compliance_checks cc
JOIN latest_runs lr ON cc.employee_upn = lr.employee_upn 
                   AND cc.system_name = lr.system_name 
                   AND cc.role_name = lr.role_name 
                   AND cc.created_at = lr.latest_check;

CREATE OR REPLACE VIEW compliance_summary_by_job_code AS
SELECT 
    jc.job_code,
    jc.job_title,
    jc.department,
    COUNT(DISTINCT cc.employee_upn) as employees_checked,
    COUNT(cc.id) as total_checks,
    COUNT(CASE WHEN cc.compliance_status = 'compliant' THEN 1 END) as compliant_count,
    COUNT(CASE WHEN cc.compliance_status != 'compliant' THEN 1 END) as violation_count,
    ROUND(
        (COUNT(CASE WHEN cc.compliance_status = 'compliant' THEN 1 END)::DECIMAL / COUNT(cc.id)) * 100, 
        2
    ) as compliance_percentage
FROM job_codes jc
LEFT JOIN compliance_checks cc ON jc.job_code = cc.job_code
GROUP BY jc.job_code, jc.job_title, jc.department
ORDER BY compliance_percentage ASC, violation_count DESC;

-- Job Role Compliance cleanup function
CREATE OR REPLACE FUNCTION cleanup_old_compliance_data() RETURNS void AS $$
BEGIN
    -- Delete compliance checks older than 90 days (keep latest run per employee)
    DELETE FROM compliance_checks 
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '90 days'
    AND id NOT IN (
        SELECT DISTINCT cc.id
        FROM compliance_checks cc
        JOIN (
            SELECT employee_upn, MAX(created_at) as latest_check
            FROM compliance_checks
            GROUP BY employee_upn
        ) latest ON cc.employee_upn = latest.employee_upn 
                 AND cc.created_at = latest.latest_check
    );
    
    -- Delete completed check runs older than 180 days
    DELETE FROM compliance_check_runs 
    WHERE completed_at < CURRENT_TIMESTAMP - INTERVAL '180 days'
    AND status = 'completed';
    
    -- Delete mapping history older than 1 year
    DELETE FROM job_role_mapping_history 
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '1 year';
    
    -- Clean up old employee role assignments (older than 30 days and not active)
    DELETE FROM employee_role_assignments 
    WHERE last_verified < CURRENT_TIMESTAMP - INTERVAL '30 days'
    AND is_active = FALSE;
END;
$$ LANGUAGE plpgsql;