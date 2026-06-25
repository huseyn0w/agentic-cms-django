import { defineConfig } from "vite";

// django-vite serves built assets under Django's STATIC_URL ("/static/").
// In dev, the Vite dev server runs on 5173 and Django proxies the tags to it.
export default defineConfig({
  base: "/static/",
  build: {
    manifest: true,
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: "src/main.js",
        admin: "src/admin.js",
      },
      output: {
        // Emit web fonts at a stable, hash-free path so the critical latin
        // weights can be <link rel=preload>ed from templates (U7). Fonts change
        // far less often than code, so dropping the content hash is a safe
        // long-cache tradeoff; everything else keeps its hashed filename.
        assetFileNames: (info) =>
          info.name && info.name.endsWith(".woff2")
            ? "assets/fonts/[name][extname]"
            : "assets/[name]-[hash][extname]",
      },
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    origin: "http://localhost:5173",
  },
});
