import { useState } from 'react';
import { ResumeProvider } from './components/ResumeContext';
import { ResumeForm } from './components/ResumeForm';
import { ResumePreview } from './components/ResumePreview';
import { TemplateCarousel } from './components/TemplateCarousel';

export default function App() {
  const [templateSelected, setTemplateSelected] = useState(false);

  return (
    <ResumeProvider>
      <div className="h-screen w-full flex flex-col overflow-hidden bg-white">
        {!templateSelected ? (
          <div className="min-h-0 flex-1 flex flex-col overflow-hidden bg-gray-50">
            <TemplateCarousel onSelect={() => setTemplateSelected(true)} />
          </div>
        ) : (
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="flex min-h-0 flex-1 overflow-hidden">
              <div className="flex min-h-0 w-1/2 flex-col border-r border-gray-200">
                <ResumeForm />
              </div>
              <div className="min-h-0 w-1/2 overflow-hidden">
                <ResumePreview />
              </div>
            </div>
          </div>
        )}
      </div>
    </ResumeProvider>
  );
}