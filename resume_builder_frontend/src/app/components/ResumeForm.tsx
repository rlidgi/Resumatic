import { useResume } from './ResumeContext';
import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { Button } from './ui/button';
import { Progress } from './ui/progress';
import { buildTemplateViewerResumePayload } from '../utils/buildTemplateViewerResumePayload';
import { WIZARD_STEPS } from './resumeWizardSteps';
import { WizardStepIllustration } from './WizardStepIllustration';
import { ChevronRight, PartyPopper } from 'lucide-react';
import { toast } from 'sonner';

const overlayMotion = {
  initial: { opacity: 0, x: 40 },
  animate: {
    opacity: 1,
    x: 0,
    transition: { duration: 0.58, ease: [0.22, 1, 0.36, 1] as const },
  },
  exit: {
    opacity: 0,
    x: -32,
    transition: { duration: 0.5, ease: [0.4, 0, 0.2, 1] as const },
  },
};

function stepOverlayBackdrop(stepId: string): string {
  switch (stepId) {
    case 'contact':
      return 'linear-gradient(165deg, #eff6ff 0%, #ffffff 45%, #eef2ff 100%)';
    case 'summary':
      return 'linear-gradient(165deg, #fffbeb 0%, #ffffff 50%, #fef3c7 100%)';
    case 'skills':
      return 'linear-gradient(165deg, #ecfdf5 0%, #ffffff 50%, #d1fae5 100%)';
    case 'experience':
      return 'linear-gradient(165deg, #eef2ff 0%, #ffffff 50%, #e0e7ff 100%)';
    case 'education':
      return 'linear-gradient(165deg, #fdf2f8 0%, #ffffff 50%, #fce7f3 100%)';
    case 'projects':
      return 'linear-gradient(165deg, #ecfeff 0%, #ffffff 50%, #cffafe 100%)';
    default:
      return 'linear-gradient(165deg, #f8fafc 0%, #ffffff 100%)';
  }
}

export function ResumeForm() {
  const { currentStep, setCurrentStep, resumeData, selectedTemplate } = useResume();
  const [isFinishing, setIsFinishing] = useState(false);
  const [forwardCheer, setForwardCheer] = useState<string | null>(null);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const stepMeta = WIZARD_STEPS[currentStep];
  const CurrentStepComponent = stepMeta.component;
  const totalSteps = WIZARD_STEPS.length;
  const progressPercent = Math.round(((currentStep + 1) / totalSteps) * 100);

  const isLastStep = currentStep === totalSteps - 1;

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  }, [currentStep]);

  useEffect(() => {
    const clarity = (window as any).clarity;
    if (typeof clarity === 'function') {
      clarity('set', 'resume_wizard_step', stepMeta.id);
      clarity('event', `resume_wizard_step_${stepMeta.id}`);
    }
  }, [stepMeta.id]);

  const goNext = async () => {
    if (isTransitioning) return;

    if (!isLastStep) {
      const next = currentStep + 1;
      const lines = WIZARD_STEPS[next]?.arrivalCheers ?? [];
      const cheer = lines.length ? lines[Math.floor(Math.random() * lines.length)] : '';

      setCurrentStep(next);
      setForwardCheer(cheer || ' ');
      setIsTransitioning(true);

      return;
    }

    if (isFinishing) return;
    setIsFinishing(true);

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

      if (!res.ok) {
        console.warn('Failed to initialize template editor session:', res.status);
        toast.error('Could not open the editor. Check your connection and try again.');
        return;
      }

      const data = await res.json().catch(() => ({} as any));
      const templateName = String((data as any)?.template || selectedTemplate || 'professional').trim();
      window.location.href = `/react/template-viewer/${encodeURIComponent(templateName)}?edit=1`;
    } finally {
      setIsFinishing(false);
    }
  };

  const goPrevious = () => {
    if (currentStep > 0 && !isTransitioning) {
      setForwardCheer(null);
      setCurrentStep(currentStep - 1);
    }
  };

  const continueFromTransition = () => {
    setIsTransitioning(false);
    setForwardCheer(null);
  };

  return (
    <div className="relative h-full flex flex-col min-h-0 bg-white">
      <AnimatePresence>
        {isTransitioning ? (
          <motion.div
            key={`transition-${currentStep}-${forwardCheer}`}
            role="status"
            aria-live="polite"
            variants={overlayMotion}
            initial="initial"
            animate="animate"
            exit="exit"
            className="absolute inset-0 z-40 flex min-h-0 flex-col shadow-[inset_0_1px_0_0_rgba(255,255,255,0.6)]"
            style={{ background: stepOverlayBackdrop(stepMeta.id) }}
          >
            <div className="shrink-0 px-8 pb-3 pt-7 sm:px-12 sm:pt-8">
              <div className="flex items-center justify-between gap-4">
                <p className="text-xs font-medium uppercase tracking-wide text-blue-700">
                  Step {currentStep + 1} of {totalSteps}
                  <span className="text-gray-500 font-normal normal-case tracking-normal">
                    {' '}
                    · {stepMeta.title}
                  </span>
                </p>
                <span className="text-xs tabular-nums text-gray-600">{progressPercent}%</span>
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-hidden px-8 pb-4 sm:px-12 sm:pb-5">
              <div className="mx-auto flex w-full max-w-lg flex-col items-center pt-0 sm:max-w-xl">
                <div className="mb-3 w-full">
                  <Progress
                    value={progressPercent}
                    className="h-2.5 bg-slate-200/80 [&>[data-slot=progress-indicator]]:bg-blue-600 [&>[data-slot=progress-indicator]]:transition-[transform] [&>[data-slot=progress-indicator]]:duration-700 [&>[data-slot=progress-indicator]]:ease-out"
                  />
                </div>
                <motion.div
                  initial={{ opacity: 0, x: 120 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1], delay: 0.08 }}
                  className="mt-1 w-full"
                >
                  <WizardStepIllustration stepId={stepMeta.id} stepIndex={currentStep} variant="hero" />
                </motion.div>

                {forwardCheer && forwardCheer.trim() ? (
                  <motion.div
                    initial={{ opacity: 0, y: 36 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.52, ease: [0.22, 1, 0.36, 1], delay: 0.2 }}
                    className="mt-1.5 flex flex-col items-center gap-1.5 px-2 text-center"
                  >
                    {currentStep === 1 ? (
                      <motion.span
                        aria-hidden
                        initial={{ rotate: -14, scale: 0.82, y: 12 }}
                        animate={{ rotate: [0, -8, 8, -4, 0], scale: 1, y: 0 }}
                        transition={{ duration: 0.75, ease: [0.22, 1, 0.36, 1], delay: 0.18 }}
                        className="text-rose-500"
                      >
                        <PartyPopper className="size-10 sm:size-12" />
                      </motion.span>
                    ) : null}
                    <p className="text-balance text-sm font-semibold leading-snug text-gray-900 sm:text-base">
                      {forwardCheer}
                    </p>
                  </motion.div>
                ) : null}

                <motion.div
                  initial={{ opacity: 0, y: 32 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1], delay: 0.34 }}
                  className="mt-2 max-w-lg space-y-1 px-2 text-center sm:max-w-xl"
                >
                  <h2 className="text-lg font-semibold tracking-tight text-gray-900 sm:text-xl">
                    {stepMeta.headline}
                  </h2>
                  <p className="text-xs leading-relaxed text-gray-600 sm:text-sm">{stepMeta.guidance}</p>
                </motion.div>
                <div className="mt-3 flex flex-col items-center">
                  <Button
                    type="button"
                    onClick={continueFromTransition}
                    className="mt-1 bg-blue-600 hover:bg-blue-700 px-8 min-w-44"
                  >
                    Continue
                  </Button>
                </div>
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div
        className={`shrink-0 border-b border-gray-100 bg-white px-8 pt-5 pb-4 ${isTransitioning ? 'invisible' : ''}`}
        aria-hidden={isTransitioning}
      >
        <div className="flex items-center justify-between gap-4 mb-2">
          <p className="text-xs font-medium uppercase tracking-wide text-blue-600">
            Step {currentStep + 1} of {totalSteps}
            <span className="text-gray-400 font-normal normal-case tracking-normal">
              {' '}
              · {stepMeta.title}
            </span>
          </p>
          <span className="text-xs tabular-nums text-gray-500">{progressPercent}%</span>
        </div>
        <Progress value={progressPercent} className="h-1.5 bg-blue-100 [&>[data-slot=progress-indicator]]:bg-blue-600" />
        <div className="mt-4 space-y-1">
          <h1 className="text-lg font-semibold text-gray-900 leading-snug">{stepMeta.headline}</h1>
          <p className="text-sm text-gray-600 leading-relaxed">{stepMeta.guidance}</p>
        </div>
      </div>

      <div
        ref={scrollRef}
        className={`flex-1 overflow-auto p-8 min-h-0 ${isTransitioning ? 'invisible pointer-events-none' : ''}`}
        aria-hidden={isTransitioning}
      >
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={stepMeta.id}
            role="region"
            aria-labelledby="wizard-step-title"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
          >
            <span id="wizard-step-title" className="sr-only">
              {stepMeta.headline}
            </span>
            <CurrentStepComponent />
          </motion.div>
        </AnimatePresence>
      </div>

      <div
        className={`shrink-0 border-t border-gray-200 bg-gray-50/50 px-6 py-4 ${isTransitioning ? 'invisible pointer-events-none' : ''}`}
        aria-hidden={isTransitioning}
      >
        <p className="text-xs text-gray-500 text-center mb-3 leading-relaxed">{stepMeta.footerHint}</p>
        <div className="flex justify-between items-center gap-3">
          <Button
            type="button"
            onClick={goPrevious}
            variant="outline"
            disabled={currentStep === 0 || isTransitioning}
            className="px-6"
          >
            Back
          </Button>
          <Button
            type="button"
            onClick={goNext}
            disabled={isFinishing || isTransitioning}
            className="bg-blue-600 hover:bg-blue-700 px-6 gap-1.5"
          >
            {isFinishing ? 'Opening editor…' : isLastStep ? 'Finish & open editor' : 'Continue'}
            {!isFinishing && !isLastStep ? <ChevronRight className="size-4" aria-hidden /> : null}
          </Button>
        </div>
      </div>
    </div>
  );
}
