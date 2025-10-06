// vite.config.ts
import { defineConfig } from "vite";
import path from "path";
import tailwindcss from "@tailwindcss/vite";
import { getEnvironmentConfig } from "./env.config";

export default defineConfig({
  plugins: [
    tailwindcss(),
    {
      name: 'stub-rrweb-image-bitmap-worker',
      enforce: 'pre',
      resolveId(id) {
        // Intercept rrweb's virtual worker module regardless of path base
        if (id.endsWith('image-bitmap-data-url-worker.js')) {
          return id;
        }
      },
      load(id) {
        if (id.endsWith('image-bitmap-data-url-worker.js')) {
          // Provide a tiny factory to avoid embedding base64 worker code
          return `export default function WorkerFactory() {
            const workerCode = "self.onmessage = (e) => { const { id } = e.data || {}; self.postMessage({ id }); };";
            const blob = new Blob([workerCode], { type: 'application/javascript' });
            return new Worker(URL.createObjectURL(blob));
          }`;
        }
      },
    },
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src/"),
      '@lib': path.resolve(__dirname, "./src/lib"),
      // Replace rrweb's inline base64 worker with our local factory to avoid embedding large base64 in bundle
      'rrweb/es/rrweb/_virtual/image-bitmap-data-url-worker.js': path.resolve(
        __dirname,
        './src/vendor/rrweb/image-bitmap-data-url-worker-factory.ts'
      ),
    },
  },
  build: {
    minify: false,        // ⛔ prevent obfuscation
    sourcemap: true       // ✅ Generated .map files for debugging
  },
  define: {
    // Inject environment variables at build time
    'import.meta.env.VITE_API_URL': JSON.stringify(process.env.VITE_API_URL || getEnvironmentConfig().VITE_API_URL),
    'import.meta.env.VITE_APP_ORIGIN': JSON.stringify(process.env.VITE_APP_ORIGIN || getEnvironmentConfig().VITE_APP_ORIGIN),
    'import.meta.env.VITE_SUPABASE_URL': JSON.stringify(process.env.VITE_SUPABASE_URL || getEnvironmentConfig().VITE_SUPABASE_URL),
    'import.meta.env.VITE_SUPABASE_ANON_KEY': JSON.stringify(process.env.VITE_SUPABASE_ANON_KEY || getEnvironmentConfig().VITE_SUPABASE_ANON_KEY),
  },
});
