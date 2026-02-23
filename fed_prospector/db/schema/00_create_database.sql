-- 00_create_database.sql
-- Creates the database and application user (run as root if not already done)
-- This is idempotent - safe to run multiple times

CREATE DATABASE IF NOT EXISTS fed_contracts
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- Create the application user manually (see QUICKSTART.md Step 1c):
--   CREATE USER 'fed_app'@'localhost' IDENTIFIED BY '<your_app_password>';
--   GRANT ALL PRIVILEGES ON fed_contracts.* TO 'fed_app'@'localhost';
--   GRANT FILE ON *.* TO 'fed_app'@'localhost';
--   FLUSH PRIVILEGES;
