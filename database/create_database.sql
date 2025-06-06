-- Create the WhoDis database
-- Run this as a PostgreSQL superuser

-- Create database
CREATE DATABASE whodis_db;

-- Connect to the database
\c whodis_db;

-- Create user for the application
CREATE USER whodis_user WITH PASSWORD 'your_secure_password_here';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE whodis_db TO whodis_user;
GRANT ALL ON SCHEMA public TO whodis_user;