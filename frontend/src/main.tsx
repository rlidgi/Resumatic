import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

function isLikelyChunkLoadError(reason: unknown): boolean {
    const msg = String(
        // unhandledrejection often uses { reason: Error }
        (reason as any)?.message ??
        (reason as any)?.reason?.message ??
        // window.onerror (ErrorEvent) has message
        (reason as any)?.message ??
        reason ??
        ''
    ).toLowerCase();

    // Vite / native ESM dynamic import failures
    if (msg.includes('failed to fetch dynamically imported module')) return true;
    if (msg.includes('importing a module script failed')) return true;

    // Common legacy chunk failure strings (helps if infra swaps bundlers)
    if (msg.includes('loading chunk') && msg.includes('failed')) return true;

    return false;
}

function installOneTimeChunkAutoReload() {
    const KEY = 'resumatic_chunk_reload_once';
    const alreadyReloaded = (() => {
        try {
            return window.sessionStorage.getItem(KEY) === '1';
        } catch {
            return false;
        }
    })();

    const attemptReload = (trigger: unknown) => {
        if (!isLikelyChunkLoadError(trigger)) return;
        if (alreadyReloaded) return;

        try {
            window.sessionStorage.setItem(KEY, '1');
        } catch {
            // ignore
        }

        try {
            const url = new URL(window.location.href);
            // Cache-bust the SPA shell request so we get a fresh index.html.
            url.searchParams.set('__reload', '1');
            url.searchParams.set('__ts', String(Date.now()));
            window.location.replace(url.toString());
        } catch {
            window.location.reload();
        }
    };

    window.addEventListener(
        'unhandledrejection',
        (e) => {
            attemptReload((e as any)?.reason ?? e);
        },
        { capture: true }
    );

    window.addEventListener(
        'error',
        (e) => {
            // ErrorEvent.message is usually enough; keep the whole event just in case.
            attemptReload((e as any)?.error ?? (e as any)?.message ?? e);
        },
        { capture: true }
    );
}

installOneTimeChunkAutoReload();

ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
        <App />
    </React.StrictMode>
);

