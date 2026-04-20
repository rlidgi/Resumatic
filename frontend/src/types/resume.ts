export interface ResumeData {
    name?: string;
    title?: string;
    email?: string;
    phone?: string;
    location?: string;
    summary?: string;
    skills?: string[];
    experience?: Array<{
        id?: string;
        title?: string;
        company?: string;
        duration?: string;
        description?: string;
    }>;
    education?: Array<{
        id?: string;
        degree?: string;
        field?: string;
        school?: string;
        graduationDate?: string;
    }>;
    projects?: Array<{
        id?: string;
        title?: string;
        description?: string;
        technologies?: string;
        link?: string;
    }>;
    certifications?: Array<{
        id?: string;
        name?: string;
        issuer?: string;
        issueDate?: string;
        expiryDate?: string;
    }>;
    style?: {
        accentColor?: string;
    };
    template?: string;
}

