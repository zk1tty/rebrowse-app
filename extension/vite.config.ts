// vite.config.ts
import { defineConfig } from "vite";
import path from "path";
import tailwindcss from "@tailwindcss/vite";
import { getEnvironmentConfig } from "./env.config";

export default defineConfig({
  plugins: [tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src/"),
      '@lib': path.resolve(__dirname, "./src/lib"),
    },
  },
  define: {
    // Inject environment variables at build time
    'import.meta.env.VITE_API_URL': JSON.stringify(process.env.VITE_API_URL || getEnvironmentConfig().VITE_API_URL),
    'import.meta.env.VITE_APP_ORIGIN': JSON.stringify(process.env.VITE_APP_ORIGIN || getEnvironmentConfig().VITE_APP_ORIGIN),
    'import.meta.env.VITE_SUPABASE_URL': JSON.stringify(process.env.VITE_SUPABASE_URL || getEnvironmentConfig().VITE_SUPABASE_URL),
    'import.meta.env.VITE_SUPABASE_ANON_KEY': JSON.stringify(process.env.VITE_SUPABASE_ANON_KEY || getEnvironmentConfig().VITE_SUPABASE_ANON_KEY),
  },
});
