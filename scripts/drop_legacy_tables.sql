-- ============================================================================
-- Drop Legacy Tables Script
-- ============================================================================
-- This script removes legacy tables that have been consolidated into 
-- the employee_profiles table as part of the architecture cleanup.
--
-- Tables being dropped:
-- - graph_photos: Consolidated into employee_profiles.photo_data
-- - data_warehouse_cache: Consolidated into employee_profiles main table
--
-- Run as postgres user for administrative privileges
-- ============================================================================

-- Enable detailed logging
\set ECHO all
\set ON_ERROR_STOP on

BEGIN;

-- Check current table sizes before dropping
\echo '============================================================================'
\echo 'PRE-DROP TABLE STATISTICS'
\echo '============================================================================'

SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_stat_get_tuples_returned(c.oid) as rows_read,
    pg_stat_get_tuples_inserted(c.oid) as rows_inserted
FROM pg_tables t
JOIN pg_class c ON c.relname = t.tablename
WHERE tablename IN ('graph_photos', 'data_warehouse_cache')
AND schemaname = 'public';

-- Verify employee_profiles table exists and has data
\echo '============================================================================'
\echo 'VERIFYING CONSOLIDATED TABLE STATUS'
\echo '============================================================================'

SELECT 
    'employee_profiles' as table_name,
    COUNT(*) as total_records,
    COUNT(photo_data) as records_with_photos,
    pg_size_pretty(pg_total_relation_size('employee_profiles')) as table_size
FROM employee_profiles;

-- Drop legacy tables
\echo '============================================================================'
\echo 'DROPPING LEGACY TABLES'
\echo '============================================================================'

-- Drop graph_photos table
DROP TABLE IF EXISTS graph_photos CASCADE;
\echo 'Dropped table: graph_photos'

-- Drop data_warehouse_cache table  
DROP TABLE IF EXISTS data_warehouse_cache CASCADE;
\echo 'Dropped table: data_warehouse_cache'

-- Update table statistics for query planner optimization
\echo '============================================================================'
\echo 'OPTIMIZING QUERY PLANNER STATISTICS'
\echo '============================================================================'

ANALYZE employee_profiles;
\echo 'Analyzed table: employee_profiles'

-- Verify tables are dropped
\echo '============================================================================'
\echo 'VERIFICATION - REMAINING TABLES'
\echo '============================================================================'

SELECT tablename 
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('graph_photos', 'data_warehouse_cache', 'employee_profiles')
ORDER BY tablename;

-- Final statistics
\echo '============================================================================'
\echo 'POST-DROP DATABASE STATISTICS'
\echo '============================================================================'

SELECT 
    pg_size_pretty(pg_database_size(current_database())) as total_db_size,
    (SELECT COUNT(*) FROM employee_profiles) as employee_profiles_count;

\echo '============================================================================'
\echo 'LEGACY TABLE DROP COMPLETED SUCCESSFULLY'
\echo '============================================================================'

COMMIT;