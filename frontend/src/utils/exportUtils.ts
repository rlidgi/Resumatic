import { ResumeData } from '../types/resume';

export function exportToJSON(resume: ResumeData) {
    const dataStr = JSON.stringify(resume, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'resume.json';
    link.click();
    URL.revokeObjectURL(url);
}

export function exportToPDF(elementId: string, resume: ResumeData) {
    // This would require html2pdf or similar library
    // For now, just log or show a message
    console.log('PDF export not implemented yet');
    alert('PDF export functionality will be added soon');
}

export function exportToCSV(resume: ResumeData) {
    let csv = 'Field,Value\n';
    csv += `Name,${resume.name || ''}\n`;
    csv += `Title,${resume.title || ''}\n`;
    csv += `Email,${resume.email || ''}\n`;
    csv += `Phone,${resume.phone || ''}\n`;
    csv += `Location,${resume.location || ''}\n`;
    csv += `Summary,${(resume.summary || '').replace(/,/g, ';')}\n`;

    if (resume.skills && resume.skills.length > 0) {
        csv += `Skills,${resume.skills.join(';')}\n`;
    }

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'resume.csv';
    link.click();
    URL.revokeObjectURL(url);
}

