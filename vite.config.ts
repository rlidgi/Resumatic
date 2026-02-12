import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), '');
    const devBackendUrl = env.VITE_DEV_BACKEND_URL || 'http://127.0.0.1:5000';

    return {
        plugins: [react()],
        base: '/static/react/',  // Set base path for asset URLs
        root: 'frontend',  // Set frontend as the root directory
        server: {
            // When running `npm run dev`, proxy API calls to Flask so relative `/api/...` fetches work.
            proxy: {
                '/api': {
                    target: devBackendUrl,
                    changeOrigin: true,
                },
            },
        },
        build: {
            outDir: '../static/react',  // Output to static/react folder
            emptyOutDir: true,  // Clear the output directory before building
            assetsDir: 'assets',  // Put assets in assets subfolder
            sourcemap: false,  // Disable source maps for production
        },
        resolve: {
            alias: {
                '@': path.resolve(__dirname, './frontend/src'),  // Optional: for @/ imports
            },
        },
    };
});