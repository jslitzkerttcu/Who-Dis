-- Add user notes feature
-- Allows admins to add internal notes about users

-- Create user_notes table
CREATE TABLE IF NOT EXISTS user_notes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    note TEXT NOT NULL,
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Create indexes for performance
CREATE INDEX idx_user_notes_user_id ON user_notes(user_id);
CREATE INDEX idx_user_notes_created_by ON user_notes(created_by);
CREATE INDEX idx_user_notes_created_at ON user_notes(created_at DESC);

-- Add trigger to update updated_at
CREATE OR REPLACE FUNCTION update_user_notes_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER user_notes_updated_at_trigger
BEFORE UPDATE ON user_notes
FOR EACH ROW
EXECUTE FUNCTION update_user_notes_updated_at();

-- Grant permissions
GRANT ALL PRIVILEGES ON TABLE user_notes TO whodis_user;
GRANT USAGE, SELECT ON SEQUENCE user_notes_id_seq TO whodis_user;

-- Analyze table for query optimization
ANALYZE user_notes;