import { useEffect, useRef, useState } from 'react';
import { Palette } from 'lucide-react';
import { useResume } from './ResumeContext';
import { buildTemplateViewerResumePayload } from '../utils/buildTemplateViewerResumePayload';

/** Match template viewer typography; short debounce keeps typing feel responsive without spamming POST. */
const DEBOUNCE_MS = 220;

const SESSION_REFRESH_MSG = 'RESUMATIC_TEMPLATE_SESSION_REFRESH';

type ResumePreviewProps = {
  onChangeTemplate?: () => void;
};

export function ResumePreview({ onChangeTemplate }: ResumePreviewProps) {
  const { resumeData, selectedTemplate } = useResume();
  const [iframeSrc, setIframeSrc] = useState('');
  const [previewError, setPreviewError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);
  const seqRef = useRef(0);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const embeddedCanonicalRef = useRef<string | null>(null);

  const resumeKey = `${selectedTemplate}:${JSON.stringify(resumeData)}`;

  const notifyEmbedRefresh = () => {
    const win = iframeRef.current?.contentWindow;
    if (!win) return;
    try {
      win.postMessage({ type: SESSION_REFRESH_MSG }, window.location.origin);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    if (timerRef.current) window.clearTimeout(timerRef.current);

    timerRef.current = window.setTimeout(async () => {
      const seq = ++seqRef.current;
      setPreviewError(null);

      try {
        const resumePayload = buildTemplateViewerResumePayload(resumeData);
        const res = await fetch('/api/template-data', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({
            resume: resumePayload,
            template: selectedTemplate,
            preview: true,
          }),
        });

        if (!res.ok) throw new Error('preview_sync_failed');

        const data = (await res.json().catch(() => ({}))) as { template?: string };
        if (seq !== seqRef.current) return;

        const canonical = String(data?.template || selectedTemplate || 'professional').trim();
        const nextSrc = `/react/template-viewer/${encodeURIComponent(canonical)}?embed=1`;

        if (embeddedCanonicalRef.current !== canonical) {
          embeddedCanonicalRef.current = canonical;
          setIframeSrc(nextSrc);
        } else {
          notifyEmbedRefresh();
        }
      } catch {
        if (seq === seqRef.current) {
          setPreviewError('Preview could not be updated.');
        }
      }
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [resumeKey, resumeData, selectedTemplate]);

  return (
    <div className="relative w-full h-full bg-gray-100 overflow-hidden flex flex-col">
      <div className="shrink-0 px-4 pt-4 pb-2 flex items-center justify-end">
        <button
          type="button"
          onClick={onChangeTemplate}
          className="inline-flex items-center gap-1.5 text-sm font-medium text-blue-600 hover:text-blue-700 underline underline-offset-2"
        >
          <Palette className="h-4 w-4" />
          Change template
        </button>
      </div>
      <div className="flex-1 min-h-0 px-4 pb-4 flex flex-col gap-2">
        {previewError && (
          <div className="shrink-0 text-xs text-red-600 px-1">{previewError}</div>
        )}
        {!iframeSrc && !previewError && (
          <div className="flex-1 flex items-center justify-center text-sm text-gray-500">Loading preview…</div>
        )}
        {iframeSrc ? (
          <iframe
            ref={iframeRef}
            title="Resume preview"
            src={iframeSrc}
            className="w-full flex-1 min-h-[480px] rounded-lg border border-gray-200 bg-white"
          />
        ) : null}
      </div>
    </div>
  );
}
