-- Script to update database schema to match current model definitions
-- Run this as postgres user with: psql -U postgres -d whodis_db -f update_schema_to_current.sql

\echo 'Updating WhoDis database schema to current version...'
\echo ''

-- Fix audit_log table to match AuditableModel structure
\echo 'Updating audit_log table...'

-- Add missing columns if they don't exist
DO $$
BEGIN
    -- Add success column if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'audit_log' AND column_name = 'success'
    ) THEN
        ALTER TABLE audit_log ADD COLUMN success BOOLEAN DEFAULT TRUE;
    END IF;
    
    -- Ensure created_at and updated_at have proper defaults
    ALTER TABLE audit_log 
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
        ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
END $$;

-- Fix error_log table to match AuditableModel structure
\echo 'Updating error_log table...'

DO $$
BEGIN
    -- Add success column if missing (should always be false for errors)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'error_log' AND column_name = 'success'
    ) THEN
        ALTER TABLE error_log ADD COLUMN success BOOLEAN DEFAULT FALSE;
    END IF;
    
    -- Add session_id if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'error_log' AND column_name = 'session_id'
    ) THEN
        ALTER TABLE error_log ADD COLUMN session_id VARCHAR(255);
    END IF;
    
    -- Add additional_data if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'error_log' AND column_name = 'additional_data'
    ) THEN
        ALTER TABLE error_log ADD COLUMN additional_data JSONB;
    END IF;
    
    -- Ensure created_at and updated_at have proper defaults
    ALTER TABLE error_log 
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
        ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
END $$;

-- Fix access_attempts table to match AuditableModel structure
\echo 'Updating access_attempts table...'

DO $$
BEGIN
    -- Add success column if missing (maps to access_granted)
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'access_attempts' AND column_name = 'success'
    ) THEN
        ALTER TABLE access_attempts ADD COLUMN success BOOLEAN;
        -- Copy values from access_granted
        UPDATE access_attempts SET success = access_granted;
    END IF;
    
    -- Add session_id if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'access_attempts' AND column_name = 'session_id'
    ) THEN
        ALTER TABLE access_attempts ADD COLUMN session_id VARCHAR(255);
    END IF;
    
    -- Add additional_data if missing
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'access_attempts' AND column_name = 'additional_data'
    ) THEN
        ALTER TABLE access_attempts ADD COLUMN additional_data JSONB;
    END IF;
    
    -- Ensure created_at and updated_at have proper defaults
    ALTER TABLE access_attempts 
        ALTER COLUMN created_at SET DEFAULT CURRENT_TIMESTAMP,
        ALTER COLUMN updated_at SET DEFAULT CURRENT_TIMESTAMP;
END $$;

-- Create indexes for better performance
\echo 'Creating/updating indexes...'

-- Audit log indexes
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_email ON audit_log(user_email);
CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_ip_address ON audit_log(ip_address);

-- Error log indexes
CREATE INDEX IF NOT EXISTS idx_error_log_timestamp ON error_log(created_at);
CREATE INDEX IF NOT EXISTS idx_error_log_error_type ON error_log(error_type);
CREATE INDEX IF NOT EXISTS idx_error_log_severity ON error_log(severity);

-- Access attempts indexes
CREATE INDEX IF NOT EXISTS idx_access_attempts_timestamp ON access_attempts(created_at);
CREATE INDEX IF NOT EXISTS idx_access_attempts_ip_address ON access_attempts(ip_address);
CREATE INDEX IF NOT EXISTS idx_access_attempts_success ON access_attempts(success);

-- Final verification
\echo ''
\echo 'Schema update completed! Verifying final structure...'
\echo ''
\echo 'audit_log columns:'
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'audit_log'
AND column_name IN ('message', 'success', 'created_at', 'updated_at')
ORDER BY column_name;

\echo ''
\echo 'error_log columns:'
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'error_log'
AND column_name IN ('message', 'success', 'session_id', 'additional_data', 'created_at', 'updated_at')
ORDER BY column_name;

\echo ''
\echo 'access_attempts columns:'
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'access_attempts'
AND column_name IN ('message', 'success', 'session_id', 'additional_data', 'created_at', 'updated_at')
ORDER BY column_name;