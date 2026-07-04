const STEP_TO_ASSET: Record<string, string> = {
  contact: 'contact-v2.png',
  summary: 'summary-v3.png',
  skills: 'skills-v2.png',
  experience: 'experience-v2.png',
  education: 'education-v2.png',
  certifications: 'certifications.png',
  projects: 'projects-v2.png',
};

const STEP_ASSET_ORDER = [
  'contact-v2.png',
  'summary-v3.png',
  'skills-v2.png',
  'experience-v2.png',
  'education-v2.png',
  'certifications.png',
  'projects-v2.png',
] as const;
const IMAGE_VERSION = '6';

export function getWizardStepArtSrc(stepId: string): string | undefined {
  const filename = STEP_TO_ASSET[stepId];
  if (!filename) return undefined;
  const base = import.meta.env.BASE_URL;
  return `${base}wizard/${filename}?v=${IMAGE_VERSION}`;
}

export function getWizardStepArtSrcByIndex(stepIndex: number): string | undefined {
  const filename = STEP_ASSET_ORDER[stepIndex];
  if (!filename) return undefined;
  const base = import.meta.env.BASE_URL;
  return `${base}wizard/${filename}?v=${IMAGE_VERSION}`;
}
