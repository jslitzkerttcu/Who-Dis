@echo off
echo ========================================
echo WhoDis Database Schema Update Script
echo ========================================
echo.
echo This script will update your database schema to match the current model definitions.
echo It will add any missing columns and create performance indexes.
echo.
echo You will be prompted for the postgres user password.
echo.
pause

cd /d "%~dp0"
psql -U postgres -d whodis_db -h localhost -f update_schema_to_current.sql

echo.
echo ========================================
echo Schema update completed!
echo ========================================
echo.
echo Please restart the WhoDis application to use the updated schema.
echo.
pause