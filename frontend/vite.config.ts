import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Convenience for /health used by the status widget (API calls use VITE_API_URL directly)
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});