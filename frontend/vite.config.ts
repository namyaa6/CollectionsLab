import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev, the browser talks only to Vite (port 5173); Vite forwards /api/* to FastAPI.
// In production FastAPI serves the built dist/ itself, so the same relative URLs work.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
