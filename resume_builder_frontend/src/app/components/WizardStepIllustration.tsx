import { motion } from 'motion/react';
import {
  Briefcase,
  FileText,
  GraduationCap,
  Mail,
  Rocket,
  Sparkles,
  UserRound,
  Wrench,
} from 'lucide-react';
import { getWizardStepArtSrc, getWizardStepArtSrcByIndex } from './wizardStepArt';

type Props = { stepId: string; stepIndex?: number; variant?: 'inline' | 'hero' };

const floatTransition = {
  duration: 2.8,
  repeat: Infinity,
  ease: [0.45, 0, 0.55, 1] as const,
};

export function WizardStepIllustration({ stepId, stepIndex, variant = 'inline' }: Props) {
  const isHero = variant === 'hero';
  const artSrc =
    typeof stepIndex === 'number' ? getWizardStepArtSrcByIndex(stepIndex) : getWizardStepArtSrc(stepId);

  if (artSrc) {
    return (
      <div
        className={
          isHero
            ? 'relative mx-auto h-[min(87vh,748px)] w-[min(87vh,748px)] max-h-[calc(100vh-350px)] max-w-[min(99vw,748px)]'
            : 'relative mx-auto h-[112px] w-[112px] shrink-0 sm:mx-0'
        }
        aria-hidden
      >
        <motion.div
          className="relative h-full w-full border-0 bg-transparent shadow-none outline-none"
        >
          <img
            src={artSrc}
            alt=""
            draggable={false}
            className="block h-full w-full border-0 bg-transparent object-contain shadow-none outline-none"
          />
        </motion.div>
      </div>
    );
  }

  return (
    <div
      className={
        isHero
          ? 'relative mx-auto h-[min(87vh,748px)] w-[min(87vh,748px)] max-h-[calc(100vh-350px)] max-w-[min(99vw,748px)]'
          : 'relative mx-auto h-[112px] w-[112px] shrink-0 sm:mx-0'
      }
      aria-hidden
    >
      <motion.div
        className={`absolute inset-0 bg-gradient-to-br shadow-sm ring-1 ring-black/5 ${isHero ? 'rounded-3xl' : 'rounded-2xl'}`}
        animate={{
          scale: [1, 1.02, 1],
          rotate: [0, 1.5, -1.5, 0],
        }}
        transition={{ duration: 5, repeat: Infinity, ease: 'easeInOut' }}
        style={{
          background:
            stepId === 'contact'
              ? 'linear-gradient(145deg, #dbeafe 0%, #e0e7ff 100%)'
              : stepId === 'summary'
                ? 'linear-gradient(145deg, #fef3c7 0%, #fde68a 55%, #fcd34d 100%)'
                : stepId === 'skills'
                  ? 'linear-gradient(145deg, #d1fae5 0%, #a7f3d0 100%)'
                  : stepId === 'experience'
                    ? 'linear-gradient(145deg, #e0e7ff 0%, #c7d2fe 100%)'
                    : stepId === 'education'
                      ? 'linear-gradient(145deg, #fce7f3 0%, #fbcfe8 100%)'
                      : 'linear-gradient(145deg, #cffafe 0%, #a5f3fc 100%)',
        }}
      />

      <motion.span
        className="absolute right-2 top-2 h-8 w-8 rounded-full bg-white/50 blur-md"
        animate={{ opacity: [0.35, 0.65, 0.35], scale: [1, 1.15, 1] }}
        transition={{ duration: 3.2, repeat: Infinity }}
      />
      <motion.span
        className="absolute bottom-3 left-2 h-6 w-6 rounded-full bg-white/40 blur-sm"
        animate={{ opacity: [0.25, 0.55, 0.25] }}
        transition={{ duration: 2.4, repeat: Infinity, delay: 0.5 }}
      />

      <div
        className={`relative flex h-full items-center justify-center ${isHero ? 'scale-[1.72] sm:scale-[1.95]' : ''}`}
        style={{ transformOrigin: 'center' }}
      >
        {stepId === 'contact' && (
          <>
            <motion.div
              className="flex flex-col items-center gap-0.5 text-blue-700"
              animate={{ y: [0, -5, 0] }}
              transition={floatTransition}
            >
              <UserRound className="size-9 stroke-[1.5]" />
              <Mail className="size-5 opacity-90" />
            </motion.div>
            <motion.div
              className="absolute -right-1 top-3 text-amber-500"
              animate={{ rotate: [0, 12, -8, 0], scale: [1, 1.1, 1] }}
              transition={{ duration: 2.2, repeat: Infinity }}
            >
              <Sparkles className="size-5" />
            </motion.div>
          </>
        )}

        {stepId === 'summary' && (
          <motion.div
            className="relative text-amber-800"
            animate={{ y: [0, -6, 0] }}
            transition={floatTransition}
          >
            <motion.div
              animate={{ rotate: [0, -3, 3, 0] }}
              transition={{ duration: 3.5, repeat: Infinity }}
            >
              <FileText className="size-11 stroke-[1.35]" />
            </motion.div>
            <motion.div
              className="absolute -bottom-0.5 left-1/2 h-1 w-10 -translate-x-1/2 rounded-full bg-amber-600/25"
              animate={{ scaleX: [0.85, 1, 0.85], opacity: [0.5, 0.85, 0.5] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
          </motion.div>
        )}

        {stepId === 'skills' && (
          <>
            <motion.div
              className="text-emerald-800"
              animate={{ y: [0, -5, 0] }}
              transition={floatTransition}
            >
              <Wrench className="size-10 stroke-[1.35]" />
            </motion.div>
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                className="absolute text-emerald-600/90"
                style={{
                  left: `${18 + i * 22}%`,
                  top: `${12 + (i % 2) * 28}%`,
                }}
                animate={{
                  y: [0, -4, 0],
                  opacity: [0.4, 1, 0.4],
                  scale: [0.9, 1, 0.9],
                }}
                transition={{
                  duration: 1.8,
                  repeat: Infinity,
                  delay: i * 0.25,
                }}
              >
                <Sparkles className="size-3.5" />
              </motion.div>
            ))}
          </>
        )}

        {stepId === 'experience' && (
          <>
            <motion.div
              className="text-indigo-800"
              animate={{ y: [0, -5, 0] }}
              transition={floatTransition}
            >
              <Briefcase className="size-11 stroke-[1.35]" />
            </motion.div>
            <motion.div
              className="absolute bottom-4 right-4 h-2 w-2 rounded-full bg-indigo-500"
              animate={{ scale: [1, 1.4, 1], opacity: [0.6, 1, 0.6] }}
              transition={{ duration: 1.5, repeat: Infinity }}
            />
            <motion.div
              className="absolute bottom-5 left-5 h-1.5 w-1.5 rounded-full bg-violet-400"
              animate={{ scale: [1, 1.5, 1], opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 1.7, repeat: Infinity, delay: 0.3 }}
            />
          </>
        )}

        {stepId === 'education' && (
          <motion.div
            className="text-pink-900"
            animate={{ y: [0, -6, 0] }}
            transition={floatTransition}
          >
            <motion.div
              animate={{ rotate: [-2, 2, -2] }}
              transition={{ duration: 3, repeat: Infinity }}
            >
              <GraduationCap className="size-12 stroke-[1.25]" />
            </motion.div>
          </motion.div>
        )}

        {stepId === 'projects' && (
          <>
            <motion.div
              className="text-cyan-900"
              animate={{ y: [0, -7, 0] }}
              transition={floatTransition}
            >
              <Rocket className="size-11 stroke-[1.35]" />
            </motion.div>
            <motion.div
              className="absolute -left-0.5 bottom-2 w-10 rounded-full bg-cyan-400/30 blur-[6px]"
              animate={{ opacity: [0.35, 0.7, 0.35], scaleX: [0.8, 1.05, 0.8] }}
              transition={{ duration: 1.6, repeat: Infinity }}
            />
          </>
        )}
      </div>
    </div>
  );
}
