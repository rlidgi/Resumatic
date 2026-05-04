import { useResume } from './ResumeContext';
import { ModernTemplate } from './templates/ModernTemplate';
import { ClassicTemplate } from './templates/ClassicTemplate';
import { CreativeTemplate } from './templates/CreativeTemplate';
import { BoldProfessionalTemplate } from './templates/BoldProfessionalTemplate';
import { ContemporaryTemplate } from './templates/ContemporaryTemplate';
import { ExecutiveTemplate } from './templates/ExecutiveTemplate';
import { StylishTemplate } from './templates/StylishTemplate';
import { ProfessionalTemplate } from './templates/ProfessionalTemplate';

export function ResumePreview() {
  const { resumeData, selectedTemplate } = useResume();

  // Debug logging
  console.log('ResumePreview - resumeData:', resumeData);
  console.log('ResumePreview - experience count:', resumeData.experience?.length);
  console.log('ResumePreview - education count:', resumeData.education?.length);

  const renderTemplate = () => {
    switch (selectedTemplate) {
      case 'modern':
        return <ModernTemplate data={resumeData} />;
      case 'classic':
        return <ClassicTemplate data={resumeData} />;
      case 'creative':
        return <CreativeTemplate data={resumeData} />;
      case 'boldprofessional':
        return <BoldProfessionalTemplate data={resumeData} />;
      case 'contemporary':
        return <ContemporaryTemplate data={resumeData} />;
      case 'executive':
        return <ExecutiveTemplate data={resumeData} />;
      case 'stylish':
        return <StylishTemplate data={resumeData} />;
      case 'professional':
        return <ProfessionalTemplate data={resumeData} />;
      default:
        return <ModernTemplate data={resumeData} />;
    }
  };

  return (
    <div className="w-full h-full bg-gray-100 p-8 overflow-auto">
      <div className="max-w-[210mm] mx-auto bg-white shadow-lg" style={{ aspectRatio: '210/297' }}>
        {renderTemplate()}
      </div>
    </div>
  );
}
