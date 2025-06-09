-- Script to check and fix audit_log table schema
-- Run this as postgres user with: psql -U postgres -d whodis_db -f check_and_fix_audit_log.sql

-- First, check what columns exist in audit_log
\echo 'Checking existing columns in audit_log table...'
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'audit_log'
ORDER BY ordinal_position;

-- Check if message column exists
\echo ''
\echo 'Checking if message column exists...'
SELECT COUNT(*) as message_column_exists
FROM information_schema.columns
WHERE table_name = 'audit_log' AND column_name = 'message';

-- Add message column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'audit_log' AND column_name = 'message'
    ) THEN
        RAISE NOTICE 'Adding missing message column to audit_log table...';
        ALTER TABLE audit_log ADD COLUMN message TEXT;
    ELSE
        RAISE NOTICE 'Message column already exists in audit_log table.';
    END IF;
END $$;

-- Also check error_log table
\echo ''
\echo 'Checking existing columns in error_log table...'
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'error_log'
ORDER BY ordinal_position;

-- Check if message column exists in error_log
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'error_log' AND column_name = 'message'
    ) THEN
        RAISE NOTICE 'Adding missing message column to error_log table...';
        ALTER TABLE error_log ADD COLUMN message TEXT;
    ELSE
        RAISE NOTICE 'Message column already exists in error_log table.';
    END IF;
END $$;

-- Check access_attempts table
\echo ''
\echo 'Checking existing columns in access_attempts table...'
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'access_attempts'
ORDER BY ordinal_position;

-- Check if message column exists in access_attempts
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name = 'access_attempts' AND column_name = 'message'
    ) THEN
        RAISE NOTICE 'Adding missing message column to access_attempts table...';
        ALTER TABLE access_attempts ADD COLUMN message TEXT;
    ELSE
        RAISE NOTICE 'Message column already exists in access_attempts table.';
    END IF;
END $$;

-- Final verification
\echo ''
\echo 'Final verification - all tables should now have message column:'
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE column_name = 'message' 
AND table_name IN ('audit_log', 'error_log', 'access_attempts')
ORDER BY table_name;