-- Analyze all tables to update PostgreSQL statistics
-- This will fix the -1 row count issue

-- First check which tables exist
SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename;

-- Analyze existing tables
DO $$
DECLARE
    tbl RECORD;
BEGIN
    FOR tbl IN 
        SELECT tablename 
        FROM pg_tables 
        WHERE schemaname = 'public'
    LOOP
        EXECUTE format('ANALYZE %I', tbl.tablename);
        RAISE NOTICE 'Analyzed table: %', tbl.tablename;
    END LOOP;
END $$;

-- Show updated statistics
SELECT 
    relname as table_name,
    n_live_tup as row_count,
    last_analyze
FROM pg_stat_user_tables 
WHERE schemaname = 'public'
ORDER BY relname;