# Installation Monitoring Setup

This document explains how to set up monitoring for the `install-chromium.sh` script using Supabase to track installation success rates and debug issues on client machines.

## Quick Setup

### 1. Create Supabase Project

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Note your project URL and anon key from Settings > API

### 2. Create Database Table

Run this SQL in your Supabase SQL editor:

```sql
-- Create installation reports table
CREATE TABLE installation_reports (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL,
    os_info TEXT,
    python_version TEXT,
    python_path TEXT,
    script_version TEXT DEFAULT '1.0.0',
    install_method TEXT DEFAULT 'curl_script',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for faster queries
CREATE INDEX idx_installation_reports_timestamp ON installation_reports(timestamp);
CREATE INDEX idx_installation_reports_status ON installation_reports(status);

-- Enable Row Level Security (RLS)
ALTER TABLE installation_reports ENABLE ROW LEVEL SECURITY;

-- Allow inserts from anyone (for anonymous reporting)
CREATE POLICY "Allow anonymous inserts" ON installation_reports
    FOR INSERT TO anon
    WITH CHECK (true);

-- Allow reads only for authenticated users
CREATE POLICY "Allow authenticated reads" ON installation_reports
    FOR SELECT TO authenticated
    USING (true);
```

### 3. Update Script Configuration

Replace the placeholder values in `install-chromium.sh`:

```bash
# Replace these lines in the script:
REPORTING_ENDPOINT="${SUPABASE_URL:-https://your-project.supabase.co}/rest/v1/installation_reports"
REPORTING_API_KEY="${SUPABASE_KEY:-your-anon-key}"

# With your actual values:
REPORTING_ENDPOINT="${SUPABASE_URL:-https://xyzabc.supabase.co}/rest/v1/installation_reports"
REPORTING_API_KEY="${SUPABASE_KEY:-REMOVED...}"
```

### 4. Test Installation Reporting

Run the script with your Supabase credentials:

```bash
SUPABASE_URL="https://your-project.supabase.co" \
SUPABASE_KEY="your-anon-key-here" \
curl -fsSL https://raw.githubusercontent.com/your-username/your-repo/main/install-chromium.sh | bash
```

## Usage Options

### Environment Variables

```bash
# Skip reporting entirely
SKIP_REPORTING=1 curl -fsSL ... | bash

# Skip the demo but still report installation success
SKIP_DEMO=1 curl -fsSL ... | bash

# Force Python 3.11 installation
FORCE_PYTHON311=1 curl -fsSL ... | bash

# Custom Supabase configuration
SUPABASE_URL="https://custom.supabase.co" \
SUPABASE_KEY="custom-key" \
curl -fsSL ... | bash
```

### Report Status Values

The script sends these status values:

- `success` - Full installation and demo completed successfully
- `success_no_demo` - Installation succeeded, demo was skipped
- `example_failed` - Installation succeeded but demo failed
- `failed` - Installation failed

## Monitoring Dashboard

### Basic Queries

```sql
-- Installation success rate (last 24 hours)
SELECT 
    status,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentage
FROM installation_reports 
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY status
ORDER BY count DESC;

-- Installations by OS (last 7 days)
SELECT 
    CASE 
        WHEN os_info LIKE '%Darwin%' THEN 'macOS'
        WHEN os_info LIKE '%Linux%' THEN 'Linux'
        WHEN os_info LIKE '%Ubuntu%' THEN 'Ubuntu'
        ELSE 'Other'
    END as os_type,
    COUNT(*) as installations
FROM installation_reports 
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY os_type
ORDER BY installations DESC;

-- Python version distribution
SELECT 
    python_version,
    COUNT(*) as count
FROM installation_reports 
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY python_version
ORDER BY count DESC;

-- Recent failed installations
SELECT 
    timestamp,
    os_info,
    python_version,
    status
FROM installation_reports 
WHERE status = 'failed'
ORDER BY timestamp DESC
LIMIT 10;
```

### Dashboard Views

Create views for easier dashboard creation:

```sql
-- Daily installation stats
CREATE VIEW daily_installation_stats AS
SELECT 
    DATE(timestamp) as date,
    COUNT(*) as total_installations,
    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed,
    ROUND(
        COUNT(CASE WHEN status = 'success' THEN 1 END) * 100.0 / COUNT(*), 
        2
    ) as success_rate
FROM installation_reports
GROUP BY DATE(timestamp)
ORDER BY date DESC;
```

## Privacy & Security

### Data Collected

The script collects only technical information needed for debugging:

- Timestamp of installation
- Installation status (success/failed)
- OS information (`uname -a` output)
- Python version
- Python executable path
- Script version

### No Personal Data

The script does NOT collect:

- ❌ User names or personal information
- ❌ File contents or directory listings
- ❌ Network information
- ❌ Browser history or personal data
- ❌ API keys or credentials

### Local Logging

Installation logs are also saved locally to `~/.rebrowse_install.log` for user debugging.

## Troubleshooting

### Common Issues

1. **No reports appearing in Supabase**
   - Check your project URL and API key
   - Verify the table exists and has the correct schema
   - Check RLS policies allow anonymous inserts

2. **Installation succeeds but no report sent**
   - Check internet connectivity during installation
   - Verify curl is available on the system
   - Reports are sent in background and won't block installation

3. **Custom endpoint not working**
   - Ensure your custom endpoint accepts the same JSON schema
   - Check CORS settings if using a different service

### Debug Mode

Add debug logging to the script:

```bash
# Add this after the "set -e" line for verbose output
set -x  # Enable debug mode
```

## Alternative Monitoring

If you don't want to use Supabase, you can:

1. **Use any REST API** - Modify the `send_installation_report` function
2. **Use webhooks** - Send to Discord, Slack, or webhook services
3. **Use log aggregation** - Ship logs to Datadog, Splunk, etc.
4. **Disable completely** - Set `SKIP_REPORTING=1`

The reporting is designed to be:
- ✅ Non-blocking (won't fail installation)
- ✅ Privacy-focused (no personal data)
- ✅ Configurable (easy to disable/customize)
- ✅ Lightweight (minimal overhead) 