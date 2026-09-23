import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, API calls go to /api and Vite forwards them to FastAPI.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000",
    },
  },
});
