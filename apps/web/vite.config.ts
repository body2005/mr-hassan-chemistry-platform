import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  base: "./",
  plugins: [
    react(),
    tailwindcss(),
    {
      name: "extend-http-server-timeouts",
      configureServer(server) {
        if (server.httpServer) {
          const s = server.httpServer as any;
          s.requestTimeout = 0;
          s.timeout = 0;
          s.headersTimeout = 0;
          s.keepAliveTimeout = 300000;
        }
      },
      configurePreviewServer(server) {
        if (server.httpServer) {
          const s = server.httpServer as any;
          s.requestTimeout = 0;
          s.timeout = 0;
          s.headersTimeout = 0;
          s.keepAliveTimeout = 300000;
        }
      },
    },
  ],
  server: {
    port: 5173,
    host: true,
    allowedHosts: true,
    proxy: {
      "/static": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
      },
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
        timeout: 0,
        proxyTimeout: 0,
      },
    },
  },
  // `vite preview` serves the production build; same API proxy as dev so the
  // site can be served on the LAN without a separate reverse proxy.
  preview: {
    port: 4173,
    host: true,
    // Allow any host so ngrok/cloudflare tunnel domains work for client demos.
    allowedHosts: true,
    proxy: {
      "/static": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
      },
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
        timeout: 0,
        proxyTimeout: 0,
      },
    },
  },
});
