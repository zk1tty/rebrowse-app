import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react-swc';
import path from 'path';

// https://vitejs.dev/config/
export default ({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  return defineConfig({
    base: '/',
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        // Proxy API calls to backend to avoid CORS issues
        '/api': {
          target: env.VITE_PUBLIC_API_URL || 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
          ws: false, // Don't proxy WebSocket connections through this route
        },
        // Proxy workflow-related calls to backend
        '/workflows': {
          target: env.VITE_PUBLIC_API_URL || 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
          ws: true, // Enable WebSocket proxying for DevTools
        },
        // Proxy WebSocket logs endpoint
        '/ws': {
          target: env.VITE_PUBLIC_API_URL || 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
          ws: true,
        },
        // Proxy Run Events WebSocket endpoint (Snapshot + Events)
        '/runs': {
          target: env.VITE_PUBLIC_API_URL || 'http://localhost:8000',
          changeOrigin: true,
          secure: false,
          ws: true,
        },
      },
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    define: {
      // Ensure client gets the exact values from .env files
      'import.meta.env.VITE_PUBLIC_API_URL': JSON.stringify(env.VITE_PUBLIC_API_URL || ''),
      'import.meta.env.VITE_PUBLIC_SUPABASE_ANON_KEY': JSON.stringify(env.VITE_PUBLIC_SUPABASE_ANON_KEY || ''),
      'import.meta.env.VITE_PUBLIC_SUPABASE_URL': JSON.stringify(env.VITE_PUBLIC_SUPABASE_URL || ''),
      // Also expose process.env fallbacks for code that checks process.env
      'process.env.VITE_PUBLIC_SUPABASE_ANON_KEY': JSON.stringify(env.VITE_PUBLIC_SUPABASE_ANON_KEY || ''),
      'process.env.VITE_PUBLIC_SUPABASE_URL': JSON.stringify(env.VITE_PUBLIC_SUPABASE_URL || ''),
    },
  });
};