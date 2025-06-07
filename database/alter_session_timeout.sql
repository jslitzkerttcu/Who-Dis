-- Add session timeout columns to existing user_sessions table
-- Run this migration if you already have the user_sessions table without these columns

-- Add warning_shown column
ALTER TABLE user_sessions 
ADD COLUMN IF NOT EXISTS warning_shown BOOLEAN DEFAULT FALSE;

-- Add is_active column
ALTER TABLE user_sessions 
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- Insert session configuration settings if they don't exist
INSERT INTO configuration (category, setting_key, setting_value, data_type, description, is_sensitive) VALUES
('session', 'timeout_minutes', '15', 'integer', 'Session timeout in minutes (default 15)', FALSE),
('session', 'warning_minutes', '2', 'integer', 'Minutes before timeout to show warning (default 2)', FALSE),
('session', 'check_interval_seconds', '30', 'integer', 'How often to check session validity in seconds', FALSE)
ON CONFLICT (category, setting_key) DO NOTHING;