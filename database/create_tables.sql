-- WhoDis Database Schema
-- Run this after creating the database
-- Updated to include all tables required by current models

-- API Tokens table (NEW - for token persistence)
CREATE TABLE IF NOT EXISTS api_tokens (
    id SERIAL PRIMARY KEY,
    service_name VARCHAR(50) UNIQUE NOT NULL,
    access_token TEXT NOT NULL,
    token_type VARCHAR(20) DEFAULT 'Bearer',
    expires_at TIMESTAMP NOT NULL,
    refresh_token TEXT,
    additional_data JSONB,
    last_refreshed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_api_tokens_service_name ON api_tokens(service_name);
CREATE INDEX IF NOT EXISTS idx_api_tokens_expires_at ON api_tokens(expires_at);

-- Users table (NEW - for user management)
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'viewer',
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(255),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(255),
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);

-- Configuration table (NEW - for database configuration with encryption support)
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(255),
    encrypted_value BYTEA,
    encryption_method VARCHAR(50) DEFAULT 'fernet',
    UNIQUE(category, setting_key),
    -- Ensure we don't have both encrypted and plain values
    CONSTRAINT check_encryption_exclusivity CHECK (
        NOT (encrypted_value IS NOT NULL AND setting_value IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_configuration_category_key ON configuration(category, setting_key);
CREATE INDEX IF NOT EXISTS idx_configuration_sensitive ON configuration(is_sensitive);

-- Configuration History table for tracking changes
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
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    change_type VARCHAR(20) NOT NULL,
    change_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_config_history_config_id ON configuration_history(config_id);
CREATE INDEX IF NOT EXISTS idx_config_history_changed_at ON configuration_history(changed_at);

-- Audit Log table
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event_type VARCHAR(50) NOT NULL,
    user_email VARCHAR(255) NOT NULL,
    user_role VARCHAR(50),
    ip_address VARCHAR(45),
    action VARCHAR(100) NOT NULL,
    target_resource VARCHAR(500),
    search_query VARCHAR(500),
    search_results_count INTEGER,
    search_services TEXT, -- JSON array
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    additional_data JSONB, -- Using JSONB for better performance
    session_id VARCHAR(255),
    user_agent TEXT
);

-- Indexes for audit_log
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_user_email ON audit_log(user_email);
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_search_query ON audit_log(search_query);
CREATE INDEX IF NOT EXISTS idx_audit_ip_address ON audit_log(ip_address);
CREATE INDEX IF NOT EXISTS idx_audit_success ON audit_log(success);

-- Error Log table (separate from audit for better organization)
CREATE TABLE IF NOT EXISTS error_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    user_email VARCHAR(255),
    request_path VARCHAR(500),
    request_method VARCHAR(10),
    request_data JSONB,
    ip_address VARCHAR(45),
    user_agent TEXT,
    severity VARCHAR(20) DEFAULT 'ERROR' -- DEBUG, INFO, WARNING, ERROR, CRITICAL
);

-- Indexes for error_log
CREATE INDEX IF NOT EXISTS idx_error_timestamp ON error_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_error_type ON error_log(error_type);
CREATE INDEX IF NOT EXISTS idx_error_severity ON error_log(severity);

-- Access Attempts table (for security monitoring)
CREATE TABLE IF NOT EXISTS access_attempts (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_email VARCHAR(255),
    ip_address VARCHAR(45) NOT NULL,
    user_agent TEXT,
    requested_path VARCHAR(500),
    access_granted BOOLEAN NOT NULL,
    denial_reason VARCHAR(255),
    auth_method VARCHAR(50) -- 'azure_ad', 'basic_auth', etc.
);

-- Indexes for access_attempts
CREATE INDEX IF NOT EXISTS idx_access_timestamp ON access_attempts(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_access_user_email ON access_attempts(user_email);
CREATE INDEX IF NOT EXISTS idx_access_ip_address ON access_attempts(ip_address);
CREATE INDEX IF NOT EXISTS idx_access_granted ON access_attempts(access_granted);

-- Genesys Cache tables
CREATE TABLE IF NOT EXISTS genesys_groups (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    member_count INTEGER,
    date_modified TIMESTAMP,
    cached_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    raw_data JSONB
);

CREATE TABLE IF NOT EXISTS genesys_locations (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    emergency_number VARCHAR(50),
    address JSONB,
    cached_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    raw_data JSONB
);

CREATE TABLE IF NOT EXISTS genesys_skills (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    cached_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    raw_data JSONB
);

-- User search results cache (optional, for performance)
CREATE TABLE IF NOT EXISTS search_cache (
    id SERIAL PRIMARY KEY,
    search_query VARCHAR(500) NOT NULL,
    search_type VARCHAR(50) NOT NULL, -- 'ldap', 'genesys', 'graph'
    result_data JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- Index for search cache
CREATE INDEX IF NOT EXISTS idx_search_cache_query ON search_cache(search_query, search_type);
CREATE INDEX IF NOT EXISTS idx_search_cache_expires ON search_cache(expires_at);

-- Graph photos cache table
CREATE TABLE IF NOT EXISTS graph_photos (
    user_id VARCHAR(255) PRIMARY KEY,
    user_principal_name VARCHAR(255),
    photo_data BYTEA NOT NULL,
    content_type VARCHAR(50) DEFAULT 'image/jpeg' NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Indexes for graph photos
CREATE INDEX IF NOT EXISTS idx_graph_photos_upn ON graph_photos(user_principal_name);
CREATE INDEX IF NOT EXISTS idx_graph_photos_updated ON graph_photos(updated_at);

-- Session tracking (optional)
CREATE TABLE IF NOT EXISTS user_sessions (
    id VARCHAR(255) PRIMARY KEY,
    user_email VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    warning_shown BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE
);

-- Index for sessions
CREATE INDEX IF NOT EXISTS idx_session_user_email ON user_sessions(user_email);
CREATE INDEX IF NOT EXISTS idx_session_expires ON user_sessions(expires_at);

-- Create views for common queries
CREATE OR REPLACE VIEW recent_searches AS
SELECT 
    timestamp,
    user_email,
    search_query,
    search_results_count,
    search_services,
    ip_address
FROM audit_log
WHERE event_type = 'search'
ORDER BY timestamp DESC
LIMIT 100;

CREATE OR REPLACE VIEW failed_access_attempts AS
SELECT 
    timestamp,
    user_email,
    ip_address,
    requested_path,
    denial_reason
FROM access_attempts
WHERE access_granted = FALSE
ORDER BY timestamp DESC
LIMIT 100;

-- Function to clean up old data
CREATE OR REPLACE FUNCTION cleanup_old_data() RETURNS void AS $$
BEGIN
    -- Delete audit logs older than 90 days
    DELETE FROM audit_log WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '90 days';
    
    -- Delete error logs older than 30 days
    DELETE FROM error_log WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '30 days';
    
    -- Delete access attempts older than 30 days
    DELETE FROM access_attempts WHERE timestamp < CURRENT_TIMESTAMP - INTERVAL '30 days';
    
    -- Delete expired search cache
    DELETE FROM search_cache WHERE expires_at < CURRENT_TIMESTAMP;
    
    -- Delete expired sessions
    DELETE FROM user_sessions WHERE expires_at < CURRENT_TIMESTAMP;
    
    -- Delete graph photos older than 30 days
    DELETE FROM graph_photos WHERE updated_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
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

-- Search settings
('search', 'overall_timeout', '20', 'integer', 'Overall search timeout in seconds', FALSE),
('search', 'lazy_load_photos', 'true', 'boolean', 'Enable lazy loading of user photos for better performance', FALSE),

-- Session settings
('session', 'timeout_minutes', '15', 'integer', 'Session timeout in minutes (default 15)', FALSE),
('session', 'warning_minutes', '2', 'integer', 'Minutes before timeout to show warning (default 2)', FALSE),
('session', 'check_interval_seconds', '30', 'integer', 'How often to check session validity in seconds', FALSE),

-- Sensitive settings (will be populated during migration)
('auth', 'viewers', NULL, 'string', 'Comma-separated list of viewer emails', TRUE),
('auth', 'editors', NULL, 'string', 'Comma-separated list of editor emails', TRUE),
('auth', 'admins', NULL, 'string', 'Comma-separated list of admin emails', TRUE),
('flask', 'secret_key', NULL, 'string', 'Flask session secret key', TRUE),
('ldap', 'bind_dn', NULL, 'string', 'LDAP bind distinguished name', TRUE),
('ldap', 'bind_password', NULL, 'string', 'LDAP bind password', TRUE),
('genesys', 'client_id', NULL, 'string', 'Genesys OAuth client ID', TRUE),
('genesys', 'client_secret', NULL, 'string', 'Genesys OAuth client secret', TRUE),
('graph', 'client_id', NULL, 'string', 'Microsoft Graph client ID', TRUE),
('graph', 'client_secret', NULL, 'string', 'Microsoft Graph client secret', TRUE),
('graph', 'tenant_id', NULL, 'string', 'Microsoft Graph tenant ID', TRUE)
ON CONFLICT (category, setting_key) DO NOTHING;

-- Add update trigger for updated_at columns
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update trigger to tables with updated_at
DROP TRIGGER IF EXISTS update_api_tokens_updated_at ON api_tokens;
CREATE TRIGGER update_api_tokens_updated_at BEFORE UPDATE ON api_tokens 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_users_updated_at ON users;
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_configuration_updated_at ON configuration;
CREATE TRIGGER update_configuration_updated_at BEFORE UPDATE ON configuration 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to track encrypted configuration changes
CREATE OR REPLACE FUNCTION track_encrypted_configuration_changes()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.setting_value IS DISTINCT FROM NEW.setting_value 
       OR OLD.encrypted_value IS DISTINCT FROM NEW.encrypted_value THEN
        INSERT INTO configuration_history (
            config_id, category, setting_key, 
            old_value, new_value, 
            old_encrypted, new_encrypted,
            changed_by, change_type
        ) VALUES (
            NEW.id, NEW.category, NEW.setting_key,
            CASE WHEN OLD.encrypted_value IS NOT NULL THEN '***ENCRYPTED***' ELSE OLD.setting_value END,
            CASE WHEN NEW.encrypted_value IS NOT NULL THEN '***ENCRYPTED***' ELSE NEW.setting_value END,
            OLD.encrypted_value IS NOT NULL,
            NEW.encrypted_value IS NOT NULL,
            NEW.updated_by,
            'update'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for tracking configuration changes
DROP TRIGGER IF EXISTS configuration_change_trigger ON configuration;
CREATE TRIGGER configuration_change_trigger
AFTER UPDATE ON configuration
FOR EACH ROW
EXECUTE FUNCTION track_encrypted_configuration_changes();

-- Grant permissions to whodis_user
GRANT ALL ON ALL TABLES IN SCHEMA public TO whodis_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO whodis_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO whodis_user;