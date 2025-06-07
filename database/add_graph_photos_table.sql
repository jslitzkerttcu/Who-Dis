-- Migration script to add graph_photos table for caching user photos
-- Run this script if you get "relation graph_photos does not exist" error

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

-- Add lazy loading configuration if not exists
INSERT INTO configuration (category, setting_key, setting_value, data_type, description, is_sensitive) 
VALUES ('search', 'lazy_load_photos', 'true', 'boolean', 'Enable lazy loading of user photos for better performance', FALSE)
ON CONFLICT (category, setting_key) DO NOTHING;

-- Update cleanup function to include graph photos
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

-- Grant permissions to the application user
GRANT ALL ON graph_photos TO whodis_user;

-- Show success message
SELECT 'Graph photos table created successfully!' as status;