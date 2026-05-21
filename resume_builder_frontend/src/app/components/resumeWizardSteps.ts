import type { ComponentType } from 'react';
import { ContactInfoStep } from './forms/ContactInfoStep';
import { SummaryStep } from './forms/SummaryStep';
import { SkillsStep } from './forms/SkillsStep';
import { ExperienceStep } from './forms/ExperienceStep';
import { EducationStep } from './forms/EducationStep';
import { CertificationsStep } from './forms/CertificationsStep';
import { ProjectsStep } from './forms/ProjectsStep';

export type WizardStepDefinition = {
  id: string;
  title: string;
  headline: string;
  guidance: string;
  encouragement: string;
  /** Short lines shown when you land on this step (forward nav); one is picked at random. */
  arrivalCheers: string[];
  footerHint: string;
  component: ComponentType;
};

export const WIZARD_STEPS: WizardStepDefinition[] = [
  {
    id: 'contact',
    title: 'Contact',
    headline: "Let's start with the basics",
    guidance:
      'Add how employers can reach you and a clear professional title. This anchors the top of your resume.',
    encouragement: 'Rough drafts are fine—you can polish every field before you export.',
    arrivalCheers: [
      'Great choice starting here—clear contact info gets more replies.',
      'You’ve got this. A strong header makes the whole resume feel professional.',
    ],
    footerHint: 'Use a professional email you check regularly.',
    component: ContactInfoStep,
  },
  {
    id: 'summary',
    title: 'Summary',
    headline: 'Your elevator pitch',
    guidance:
      'In a few sentences, say who you are, what you do best, and what you are looking for next.',
    encouragement: 'Think outcomes: strengths, scope, and the value you bring—not a full career story.',
    arrivalCheers: [
      'Nice progress—your summary is the hook that keeps recruiters reading.',
      'Welcome to the summary: a few sharp lines beat a long paragraph every time.',
    ],
    footerHint: 'Aim for about 3–5 sentences; you can tighten the wording in the editor.',
    component: SummaryStep,
  },
  {
    id: 'skills',
    title: 'Skills',
    headline: 'What you bring to the table',
    guidance:
      'Mix hard skills (tools, methods) with soft skills (leadership, communication) that match your target role.',
    encouragement: 'Start with what you are strongest at—you can reorder later in the template.',
    arrivalCheers: [
      'Skills time—recruiters often scan this section first. Lead with your strengths.',
      'You’re building a clear picture of what you can do on day one.',
    ],
    footerHint: 'Specific beats vague: “SQL reporting” helps more than “computer skills.”',
    component: SkillsStep,
  },
  {
    id: 'experience',
    title: 'Experience',
    headline: 'Show your impact',
    guidance:
      'For each role, lead with title and company, then use bullets that highlight results, scale, or ownership.',
    encouragement: 'If you are early in your career, internships and part-time work count—include them.',
    arrivalCheers: [
      'Experience is where your resume really shines—one solid bullet beats ten vague ones.',
      'Keep going: each role is a chance to show impact, not just job titles.',
    ],
    footerHint: 'Use numbers when you can (%, $, time saved, team size). Estimates are OK if honest.',
    component: ExperienceStep,
  },
  {
    id: 'education',
    title: 'Education',
    headline: 'Credentials and training',
    guidance:
      'List degrees, institutions, and dates. Add honors, coursework, or certifications that strengthen your story.',
    encouragement: 'Skipping optional details is fine; you can always add more before you apply.',
    arrivalCheers: [
      'Education adds credibility—degrees, certs, and training all belong here.',
      'Almost there: this section rounds out your professional story nicely.',
    ],
    footerHint: 'Recent grads: relevant coursework or projects can go in descriptions.',
    component: EducationStep,
  },
  {
    id: 'certifications',
    title: 'Certifications',
    headline: 'Show verified expertise',
    guidance:
      'Add relevant certifications, licenses, or credentials that strengthen trust and fit your target role.',
    encouragement: 'Even one strong certification can boost credibility quickly.',
    arrivalCheers: [
      'Great progress—certifications help your profile stand out fast.',
      'Nice work. Verified credentials can become a recruiter tie-breaker.',
    ],
    footerHint: 'Use official certification names and issuers for better ATS matching.',
    component: CertificationsStep,
  },
  {
    id: 'projects',
    title: 'Projects',
    headline: 'Proof of what you can build',
    guidance:
      'Side projects, open source, or portfolio work show initiative—especially for technical and creative roles.',
    encouragement: 'This step is optional; if it does not apply, you can move on.',
    arrivalCheers: [
      'Final stretch—projects can set you apart when experience is thin or you’re pivoting.',
      'Home stretch! Add anything that proves you ship real work.',
    ],
    footerHint: 'Links to demos or repos make it easy for recruiters to see your work.',
    component: ProjectsStep,
  },
];
