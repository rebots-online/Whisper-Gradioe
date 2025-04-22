-- Migration script to migrate existing data to the multi-tenant schema
-- This script assumes that the tables created in 01_create_multitenant_tables.sql exist
-- and that there are existing users and jobs in the old schema

-- Create a default reseller
INSERT INTO resellers (id, name, email, status)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'System Reseller',
    'admin@system.local',
    'active'
)
ON CONFLICT DO NOTHING;

-- Create default subscription plans
INSERT INTO subscription_plans (id, reseller_id, name, description, price_monthly, price_yearly, storage_quota_mb, processing_quota_minutes, max_users, features)
VALUES
    (
        '00000000-0000-0000-0000-000000000001',
        '00000000-0000-0000-0000-000000000001',
        'Basic',
        'Basic plan with limited features',
        9.99,
        99.99,
        5000,
        300,
        5,
        '{"whisper_models": ["tiny", "base", "small"], "diarization": false, "bgm_separation": false, "translation": false}'
    ),
    (
        '00000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000001',
        'Premium',
        'Premium plan with advanced features',
        19.99,
        199.99,
        20000,
        1000,
        20,
        '{"whisper_models": ["tiny", "base", "small", "medium"], "diarization": true, "bgm_separation": true, "translation": true}'
    ),
    (
        '00000000-0000-0000-0000-000000000003',
        '00000000-0000-0000-0000-000000000001',
        'Enterprise',
        'Enterprise plan with all features',
        49.99,
        499.99,
        100000,
        5000,
        100,
        '{"whisper_models": ["tiny", "base", "small", "medium", "large-v2"], "diarization": true, "bgm_separation": true, "translation": true}'
    )
ON CONFLICT DO NOTHING;

-- Create default branding configuration
INSERT INTO branding_configurations (id, reseller_id, name, is_default, theme, assets, texts)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001',
    'Default Branding',
    true,
    '{"primaryColor": "#3498db", "secondaryColor": "#2ecc71", "textColor": "#333333", "backgroundColor": "#ffffff", "fontFamily": "Arial, sans-serif"}',
    '{"logo": "/static/logo.png", "favicon": "/static/favicon.ico", "loginBackground": "/static/login-bg.jpg"}',
    '{"appName": "Whisper WebUI", "tagline": "Powerful Speech Recognition", "footerText": "© 2025 Whisper WebUI"}'
)
ON CONFLICT DO NOTHING;

-- Create a default tenant for existing data
INSERT INTO tenants (id, reseller_id, name, subscription_plan_id, subscription_status, branding_configuration_id)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001',
    'Default Tenant',
    '00000000-0000-0000-0000-000000000002', -- Premium plan
    'active',
    '00000000-0000-0000-0000-000000000001'  -- Default branding
)
ON CONFLICT DO NOTHING;

-- Migrate existing users to the new schema
-- This assumes there's an existing 'old_users' table with at least id, email, and password_hash
-- If your existing schema is different, adjust this query accordingly
INSERT INTO users (id, tenant_id, email, password_hash, role, status)
SELECT 
    u.id, 
    '00000000-0000-0000-0000-000000000001', -- Default tenant ID
    u.email, 
    u.password_hash, 
    CASE WHEN u.is_admin THEN 'admin' ELSE 'user' END, 
    'active'
FROM old_users u
ON CONFLICT DO NOTHING;

-- Create a default admin user if none exists
INSERT INTO users (tenant_id, email, password_hash, first_name, last_name, role, status)
SELECT 
    '00000000-0000-0000-0000-000000000001', -- Default tenant ID
    'admin@example.com',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', -- 'password'
    'Admin',
    'User',
    'admin',
    'active'
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE role = 'admin' AND tenant_id = '00000000-0000-0000-0000-000000000001'
);

-- Migrate existing jobs to the new schema
-- This assumes there's an existing 'old_jobs' table
-- If your existing schema is different, adjust this query accordingly
INSERT INTO jobs (id, tenant_id, user_id, status, file_path, result_path, error, processing_time, created_at, updated_at, completed_at)
SELECT 
    j.id,
    '00000000-0000-0000-0000-000000000001', -- Default tenant ID
    COALESCE(j.user_id, (SELECT id FROM users WHERE role = 'admin' AND tenant_id = '00000000-0000-0000-0000-000000000001' LIMIT 1)),
    j.status,
    j.file_path,
    j.result_path,
    j.error,
    j.processing_time,
    j.created_at,
    j.updated_at,
    j.completed_at
FROM old_jobs j
ON CONFLICT DO NOTHING;

-- Create default workflows for the migrated users
INSERT INTO workflows (tenant_id, user_id, name, description, config, is_template, is_public)
SELECT
    '00000000-0000-0000-0000-000000000001', -- Default tenant ID
    u.id,
    'Default Workflow',
    'Default transcription workflow',
    '{"nodes":[{"id":"1","type":"whisperTranscription","position":{"x":250,"y":150},"data":{"modelSize":"medium","whisperType":"faster-whisper"}}],"edges":[]}',
    false,
    false
FROM users u
WHERE u.tenant_id = '00000000-0000-0000-0000-000000000001'
ON CONFLICT DO NOTHING;

-- Update sequence values if using serial IDs (not needed for UUID)
-- SELECT setval('users_id_seq', (SELECT MAX(id) FROM users));
-- SELECT setval('jobs_id_seq', (SELECT MAX(id) FROM jobs));
