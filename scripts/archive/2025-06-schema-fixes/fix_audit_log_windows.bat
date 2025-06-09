@echo off
echo ========================================
echo WhoDis Database Schema Fix Script
echo ========================================
echo.
echo This script will check and fix the audit_log, error_log, and access_attempts tables
echo to ensure they have the required 'message' column.
echo.
echo You will be prompted for the postgres user password.
echo.
pause

cd /d "%~dp0"
psql -U postgres -d whodis_db -h localhost -f check_and_fix_audit_log.sql

echo.
echo ========================================
echo Script completed!
echo ========================================
pause