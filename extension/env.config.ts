// Environment configuration for different build targets
interface EnvConfig {
  VITE_API_URL: string;
  VITE_APP_ORIGIN: string;
  VITE_SUPABASE_URL: string;
  VITE_SUPABASE_ANON_KEY?: string;
}

export const envConfigs: Record<string, EnvConfig> = {
  dev: {
    VITE_API_URL: 'http://127.0.0.1:8000',
    VITE_APP_ORIGIN: 'localhost:5173',
    VITE_SUPABASE_URL: 'https://dmgtsseqqsiyuuzhdxnn.supabase.co',
    VITE_SUPABASE_ANON_KEY: 'REMOVED.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRtZ3Rzc2VxcXNpeXV1emhkeG5uIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk3MzE4ODIsImV4cCI6MjA2NTMwNzg4Mn0.e5bQXtdRsPY31fEp2xextWC4QKYUcAvj77hEDVZHuZw'
  },
  prod: {
    VITE_API_URL: 'https://wf-be.up.railway.app',
    VITE_APP_ORIGIN: 'https://app.rebrowse.me',
    VITE_SUPABASE_URL: 'https://dmgtsseqqsiyuuzhdxnn.supabase.co',
    VITE_SUPABASE_ANON_KEY: 'REMOVED.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRtZ3Rzc2VxcXNpeXV1emhkeG5uIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDk3MzE4ODIsImV4cCI6MjA2NTMwNzg4Mn0.e5bQXtdRsPY31fEp2xextWC4QKYUcAvj77hEDVZHuZw'
  }
};

// Get environment based on NODE_ENV or BUILD_ENV
export function getEnvironmentConfig(): EnvConfig {
  const env = process.env.BUILD_ENV || process.env.NODE_ENV || 'dev';
  return envConfigs[env] || envConfigs.dev;
} 