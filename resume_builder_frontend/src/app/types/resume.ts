export interface ResumeData {
  // Contact Information
  firstName: string;
  lastName: string;
  occupation: string;
  address: string;
  phone: string;
  email: string;
  linkedin?: string;
  website?: string;
  nationality?: string;
  dateOfBirth?: string;

  // Summary
  summary: string;

  // Skills
  skills: string[];

  // Work Experience
  experience: WorkExperience[];

  // Education
  education: Education[];

  // Projects
  projects: Project[];

  // Languages
  languages: Language[];

  // Additional
  certifications?: Certification[];
  volunteer?: VolunteerExperience[];
}

export interface WorkExperience {
  id: string;
  position: string;
  company: string;
  location: string;
  startDate: string;
  endDate: string;
  current: boolean;
  description: string;
}

export interface Education {
  id: string;
  degree: string;
  institution: string;
  location: string;
  startDate: string;
  endDate: string;
  description?: string;
}

export interface Project {
  id: string;
  title: string;
  description: string;
  technologies?: string[];
  link?: string;
  startDate?: string;
  endDate?: string;
}

export interface Language {
  id: string;
  name: string;
  proficiency: string;
}

export interface Certification {
  id: string;
  name: string;
  issuer: string;
  date: string;
}

export interface VolunteerExperience {
  id: string;
  role: string;
  organization: string;
  startDate: string;
  endDate: string;
  description: string;
}

export type ResumeTemplate = 'modern' | 'classic' | 'creative' | 'boldprofessional' | 'contemporary' | 'executive' | 'stylish' | 'professional';
