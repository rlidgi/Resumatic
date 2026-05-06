import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), '');
    const devBackendUrl = env.VITE_DEV_BACKEND_URL || 'http://127.0.0.1:5000';

    return {
        plugins: [react(), tailwindcss()],
        base: '/create-resume/',
        root: 'frontend',
        server: {
            proxy: {
                '/api': {
                    target: devBackendUrl,
                    changeOrigin: true,
                },
                '/static': {
                    target: devBackendUrl,
                    changeOrigin: true,
                },
            },
        },
        build: {
            outDir: '../static/resume-builder',
            emptyOutDir: false,
            assetsDir: 'assets',
            sourcemap: false,
        },
        resolve: {
            alias: {
                '@': path.resolve(__dirname, './frontend/src'),
            },
        },
        assetsInclude: ['**/*.svg', '**/*.csv'],
    };
});
