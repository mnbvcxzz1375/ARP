import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';
export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        port: 5173,
        // The docs site imports repo-level docs/ and packages/ files raw, so
        // the dev server needs to serve files outside apps/web.
        fs: {
            allow: [path.resolve(__dirname, '../..')],
        },
        proxy: {
            '/v1': {
                target: 'http://localhost:8000',
                changeOrigin: true,
            },
        },
    },
    build: {
        outDir: 'dist',
        // No production sourcemaps: the bundle ships admin/enterprise code and a
        // .map would publish the full source tree under public, immutable cache.
        // (nginx also denies *.map as a second layer.)
        sourcemap: false,
        rollupOptions: {
            output: {
            // Chunk grouping note: dynamic-import targets (the lazy pages in
            // App.tsx) are Rollup chunk entries, so manualChunks cannot merge
            // them. The docs sub-site is instead funneled through one barrel
            // module (features/docs/docsSite.ts), which makes Vite emit the
            // whole sub-site - pages, docs registry and the react-markdown/
            // remark chain - as a single lazy chunk. Admin/enterprise pages are
            // per-page lazy chunks. Locale namespaces (src/i18n/locales/**)
            // deliberately keep the default chunking: each file is its own
            // on-demand chunk so loading one namespace never pulls the rest
            // (see src/i18n/core.ts).
            },
        },
    },
    test: {
        globals: true,
        environment: 'jsdom',
        setupFiles: './src/setupTests.ts',
        css: true,
        exclude: ['node_modules', 'e2e'],
    },
});
