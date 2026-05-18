import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api/ingest": {
        target: process.env.INGESTION_URL ?? "http://localhost:8001",
        rewrite: (path) => path.replace(/^\/api\/ingest/, ""),
      },
      "/api/aggregation": {
        target: process.env.AGGREGATION_URL ?? "http://localhost:8002",
        rewrite: (path) => path.replace(/^\/api\/aggregation/, ""),
      },
      "/api/ml": {
        target: process.env.ML_URL ?? "http://localhost:8003",
        rewrite: (path) => path.replace(/^\/api\/ml/, ""),
      },
    },
  },
});
