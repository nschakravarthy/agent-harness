import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The backend runs at http://localhost:8000 (see docker-compose.yml).
// We proxy /api to it in dev so the browser makes same-origin requests
// and we avoid any CORS surprises. Override with VITE_API_TARGET if needed.
const API_TARGET = process.env.VITE_API_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
});
