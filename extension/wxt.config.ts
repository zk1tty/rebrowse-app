// wxt.config.ts
import { defineConfig } from "wxt";
import baseViteConfig from "./vite.config";

import { mergeConfig } from "vite";

// See https://wxt.dev/api/config.html
export default defineConfig({
  modules: ["@wxt-dev/module-react"],
  srcDir: "src",
  publicDir: "src/public",
  vite: () =>
    mergeConfig(baseViteConfig, {
      envPrefix: "VITE_",
    }),
  manifest: {
    // See https://developer.chrome.com/docs/extensions/mv3/declare_permissions/
    permissions: [
      "storage",
      "sidePanel",
      "identity",
      "notifications",
      "tabs",
      "activeTab",
    ],
    host_permissions: [
      "<all_urls>",
      "http://127.0.0.1:8000/*", // VITE_API_URL (backend)
      "http://localhost:5173/*", // VITE_APP_ORIGIN (example)
      "https://*.supabase.co/*",   // VITE_SUPABASE_URL
    ],
    // Extension icons - shown in chrome://extensions
    icons: {
      16: "16.png",
      32: "32.png",
      48: "48.png", 
      128: "128.png",
    },
    // Action icon - shown in browser toolbar
    action: {
      default_icon: {
        16: "16.png",
        32: "32.png",
        48: "48.png",
        128: "128.png",
      },
      default_title: "Rebrowse Recorder",
    },
    oauth2: {
      client_id: "1058215711784-livolddr65rfj8a36ara0knh8ctivi3s.apps.googleusercontent.com",
      scopes: ["email", "profile", "openid"]
    }
    // options_page: "options.html",
  },
});
