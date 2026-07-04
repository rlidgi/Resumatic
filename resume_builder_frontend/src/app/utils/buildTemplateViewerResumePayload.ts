import type { ResumeData, WorkExperience, Education, Project } from '../types/resume';

function formatMonthYear(ym: string): string {
  const v = String(ym || '').trim();
  const m = v.match(/^(\d{4})-(\d{2})$/);
  if (!m) return v;
  const year = m[1];
  const month = m[2];
  const map: Record<string, string> = {
    '01': 'Jan',
    '02': 'Feb',
    '03': 'Mar',
    '04': 'Apr',
    '05': 'May',
    '06': 'Jun',
    '07': 'Jul',
    '08': 'Aug',
    '09': 'Sep',
    '10': 'Oct',
    '11': 'Nov',
    '12': 'Dec',
  };
  return `${map[month] || month} ${year}`;
}

function formatRange(fromYm: string, toYm: string, isCurrent: boolean): string {
  const start = formatMonthYear(fromYm);
  const end = isCurrent ? 'Present' : formatMonthYear(toYm);
  if (start && end) return `${start} – ${end}`;
  if (start && isCurrent) return `${start} – Present`;
  return start || end;
}

function mapExperienceForViewer(experience: WorkExperience[]) {
  return (Array.isArray(experience) ? experience : []).map((exp) => {
    const duration = formatRange(exp.startDate, exp.endDate, !!exp.current);
    return {
      ...exp,
      title: String(exp.position || '').trim(),
      duration: duration || undefined,
    };
  });
}

function mapEducationForViewer(education: Education[]) {
  return (Array.isArray(education) ? education : []).map((edu) => {
    const dates = formatRange(edu.startDate, edu.endDate, false);
    return {
      ...edu,
      year: dates || undefined,
      dates: dates || undefined,
    };
  });
}

function mapProjectsForViewer(projects: Project[]) {
  return (Array.isArray(projects) ? projects : []).map((p) => ({
    ...p,
    title: String(p.title || '').trim(),
  }));
}

/**
 * Shape resume data for `/api/template-data` and the main TemplateViewer templates
 * (`parseResumeContent` + ExperienceBlock expects title/duration, etc.).
 */
export function buildTemplateViewerResumePayload(resumeData: ResumeData) {
  const firstName = String(resumeData?.firstName || '').trim();
  const lastName = String(resumeData?.lastName || '').trim();
  const name = `${firstName} ${lastName}`.trim();
  const title = String(resumeData?.occupation || '').trim();
  const location = String(resumeData?.address || '').trim();

  const languages = Array.isArray(resumeData?.languages)
    ? resumeData.languages
        .filter((l: { name?: string }) => String(l?.name || '').trim())
        .map((l: { name?: string; level?: string; proficiency?: string }) => ({
          ...(l || {}),
          level: String(l?.level || l?.proficiency || '').trim(),
        }))
    : [];

  const certifications = Array.isArray((resumeData as ResumeData & { certifications?: unknown }).certifications)
    ? (resumeData as ResumeData & { certifications: Array<Record<string, unknown>> }).certifications
        .filter((c) => String(c?.name || '').trim())
        .map((c) => ({
          ...(c || {}),
          year: String(c?.year || c?.date || '').trim(),
        }))
    : undefined;

  return {
    ...(resumeData as Record<string, unknown>),
    name,
    title,
    location,
    experience: mapExperienceForViewer(resumeData.experience || []),
    education: mapEducationForViewer(resumeData.education || []),
    projects: mapProjectsForViewer(resumeData.projects || []),
    languages,
    ...(certifications && certifications.length ? { certifications } : {}),
  };
}
