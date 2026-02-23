import { create } from 'zustand';
import { ResumeData } from '../types/resume';

interface ResumeStore {
    resume: ResumeData;
    updatePersonal: (data: Partial<ResumeData>) => void;
    importParsed: (data: Partial<ResumeData>) => void;
    addSkill: (skill: string) => void;
    removeSkill: (index: number) => void;
    addExperience: () => void;
    updateExperience: (index: number, data: Partial<ResumeData['experience'][0]>) => void;
    removeExperience: (index: number) => void;
    addEducation: () => void;
    updateEducation: (index: number, data: Partial<ResumeData['education'][0]>) => void;
    removeEducation: (index: number) => void;
    addProject: () => void;
    updateProject: (index: number, data: Partial<ResumeData['projects'][0]>) => void;
    removeProject: (index: number) => void;
    addCertification: () => void;
    updateCertification: (index: number, data: Partial<ResumeData['certifications'][0]>) => void;
    removeCertification: (index: number) => void;
    setTemplate: (template: string) => void;
    loadFromLocalStorage: () => void;
    saveToLocalStorage: () => void;
}

const defaultResume: ResumeData = {
    name: '',
    title: '',
    email: '',
    phone: '',
    location: '',
    summary: '',
    skills: [],
    experience: [],
    education: [],
    projects: [],
    certifications: [],
    template: 'professional',
};

const canonicalizeTemplateId = (rawTemplate: unknown): string => {
    const template = typeof rawTemplate === 'string' ? rawTemplate.trim() : '';
    if (!template) return 'professional';

    const key = template.toLowerCase();
    switch (key) {
        case 'lavenderclassic':
        case 'lavender-classic':
        case 'lavender_classic':
            return 'elegant';
        case 'popart':
        case 'pop-art':
        case 'pop_art':
            return 'creative';
        case 'orangeheader':
        case 'orange-header':
        case 'orange_header':
            return 'boldProfessional';
        case 'boldprofessional':
        case 'bold-professional':
        case 'bold_professional':
            return 'boldProfessional';
        case 'bluelineclassic':
        case 'blue-line-classic':
        case 'blue_line_classic':
            return 'traditional';
        case 'cleansidebar':
        case 'clean-sidebar':
        case 'clean_sidebar':
            return 'modern';
        case 'timelineblue':
        case 'timeline-blue':
        case 'timeline_blue':
            return 'executive';
        case 'dark-sidebar-progress':
        case 'dark_sidebar_progress':
            return 'darkSidebarProgress';
        default:
            return template;
    }
};

const SUPPORTED_TEMPLATES = new Set([
    'professional',
    'classic',
    'elegant',
    'creative',
    'boldProfessional',
    'traditional',
    'modern',
    'executive',
    'minimal',
    'darkSidebarProgress',
]);

export const useResumeStore = create<ResumeStore>((set, get) => ({
    resume: defaultResume,

    updatePersonal: (data) => set((state) => {
        const incomingTemplate = (data as any)?.template;
        const template = incomingTemplate !== undefined
            ? (SUPPORTED_TEMPLATES.has(canonicalizeTemplateId(incomingTemplate)) ? canonicalizeTemplateId(incomingTemplate) : 'professional')
            : state.resume.template;
        return {
            resume: { ...state.resume, ...data, template }
        };
    }),

    importParsed: (data) => {
        const incomingTemplate = (data as any)?.template;
        const canonical = incomingTemplate !== undefined ? canonicalizeTemplateId(incomingTemplate) : 'professional';
        const template = SUPPORTED_TEMPLATES.has(canonical) ? canonical : 'professional';
        set({ resume: { ...defaultResume, ...data, template } });
    },

    addSkill: (skill) => set((state) => ({
        resume: {
            ...state.resume,
            skills: [...(state.resume.skills || []), skill]
        }
    })),

    removeSkill: (index) => set((state) => ({
        resume: {
            ...state.resume,
            skills: state.resume.skills?.filter((_, i) => i !== index) || []
        }
    })),

    addExperience: () => set((state) => ({
        resume: {
            ...state.resume,
            experience: [...(state.resume.experience || []), { id: Date.now().toString() }]
        }
    })),

    updateExperience: (index, data) => set((state) => {
        const experience = [...(state.resume.experience || [])];
        experience[index] = { ...experience[index], ...data };
        return { resume: { ...state.resume, experience } };
    }),

    removeExperience: (index) => set((state) => ({
        resume: {
            ...state.resume,
            experience: state.resume.experience?.filter((_, i) => i !== index) || []
        }
    })),

    addEducation: () => set((state) => ({
        resume: {
            ...state.resume,
            education: [...(state.resume.education || []), { id: Date.now().toString() }]
        }
    })),

    updateEducation: (index, data) => set((state) => {
        const education = [...(state.resume.education || [])];
        education[index] = { ...education[index], ...data };
        return { resume: { ...state.resume, education } };
    }),

    removeEducation: (index) => set((state) => ({
        resume: {
            ...state.resume,
            education: state.resume.education?.filter((_, i) => i !== index) || []
        }
    })),

    addProject: () => set((state) => ({
        resume: {
            ...state.resume,
            projects: [...(state.resume.projects || []), { id: Date.now().toString() }]
        }
    })),

    updateProject: (index, data) => set((state) => {
        const projects = [...(state.resume.projects || [])];
        projects[index] = { ...projects[index], ...data };
        return { resume: { ...state.resume, projects } };
    }),

    removeProject: (index) => set((state) => ({
        resume: {
            ...state.resume,
            projects: state.resume.projects?.filter((_, i) => i !== index) || []
        }
    })),

    addCertification: () => set((state) => ({
        resume: {
            ...state.resume,
            certifications: [...(state.resume.certifications || []), { id: Date.now().toString() }]
        }
    })),

    updateCertification: (index, data) => set((state) => {
        const certifications = [...(state.resume.certifications || [])];
        certifications[index] = { ...certifications[index], ...data };
        return { resume: { ...state.resume, certifications } };
    }),

    removeCertification: (index) => set((state) => ({
        resume: {
            ...state.resume,
            certifications: state.resume.certifications?.filter((_, i) => i !== index) || []
        }
    })),

    setTemplate: (template) => set((state) => {
        const canonical = canonicalizeTemplateId(template);
        return {
            resume: {
                ...state.resume,
                template: SUPPORTED_TEMPLATES.has(canonical) ? canonical : 'professional'
            }
        };
    }),

    loadFromLocalStorage: () => {
        try {
            const stored = localStorage.getItem('resumeData');
            if (stored) {
                const parsed = JSON.parse(stored);
                const canonical = canonicalizeTemplateId(parsed?.template);
                const template = SUPPORTED_TEMPLATES.has(canonical) ? canonical : 'professional';
                set({ resume: { ...defaultResume, ...parsed, template } });
            }
        } catch (e) {
            console.error('Failed to load from localStorage:', e);
        }
    },

    saveToLocalStorage: () => {
        try {
            localStorage.setItem('resumeData', JSON.stringify(get().resume));
        } catch (e) {
            console.error('Failed to save to localStorage:', e);
        }
    },
}));

