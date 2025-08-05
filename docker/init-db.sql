-- Rebrowse Database Initialization Script
-- This script creates the necessary tables for self-hosted deployment

-- Enable UUID extension for generating UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create workflows table
CREATE TABLE IF NOT EXISTS workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id UUID,
    name VARCHAR(255) NOT NULL,
    version VARCHAR(50) DEFAULT '1.0',
    description TEXT,
    workflow_analysis TEXT,
    steps JSONB DEFAULT '[]',
    input_schema JSONB DEFAULT '[]',
    json JSONB, -- For backward compatibility
    title VARCHAR(255), -- For backward compatibility
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create workflow_executions table for execution history tracking
CREATE TABLE IF NOT EXISTS workflow_executions (
    execution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id UUID NOT NULL,
    user_id UUID,
    status VARCHAR(20) CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    mode VARCHAR(20) CHECK (mode IN ('cloud-run', 'local-run')),
    visual_enabled BOOLEAN DEFAULT FALSE,
    visual_streaming_enabled BOOLEAN DEFAULT FALSE,
    visual_quality VARCHAR(20),
    session_id VARCHAR(255),
    inputs JSONB DEFAULT '{}',
    result JSONB,
    error TEXT,
    logs JSONB,
    execution_time_seconds DECIMAL(10,3),
    visual_events_captured INTEGER,
    visual_stream_duration DECIMAL(10,3),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_workflows_owner_id ON workflows(owner_id);
CREATE INDEX IF NOT EXISTS idx_workflows_created_at ON workflows(created_at);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_workflow_id ON workflow_executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_user_id ON workflow_executions(user_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_created_at ON workflow_executions(created_at);

-- Set up Row Level Security (RLS) for multi-tenancy (optional - can be enabled later)
-- ALTER TABLE workflows ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE workflow_executions ENABLE ROW LEVEL SECURITY;

-- Insert a sample workflow for testing (optional)
INSERT INTO workflows (
    id,
    owner_id,
    name,
    description,
    steps,
    input_schema
) VALUES (
    uuid_generate_v4(),
    uuid_generate_v4(),
    'Sample Workflow',
    'A sample workflow for testing the self-hosted setup',
    '[{"id": "1", "type": "action", "content": "Welcome to Rebrowse!"}]'::jsonb,
    '[]'::jsonb
) ON CONFLICT DO NOTHING;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Rebrowse database initialized successfully!';
    RAISE NOTICE 'Tables created: workflows, workflow_executions';
    RAISE NOTICE 'Sample data inserted for testing';
END $$; 