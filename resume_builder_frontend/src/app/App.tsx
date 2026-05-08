import { useState } from 'react';
import { Toaster } from 'sonner';
import { ResumeProvider } from './components/ResumeContext';
import { ResumeForm } from './components/ResumeForm';
import { ResumePreview } from './components/ResumePreview';
import { TemplateCarousel } from './components/TemplateCarousel';

export default function App() {
  const [templateSelected, setTemplateSelected] = useState(false);

  return (
    <ResumeProvider>
      <Toaster richColors position="top-center" closeButton />
      {!templateSelected ? (
        <TemplateCarousel onSelect={() => setTemplateSelected(true)} />
      ) : (
        <div className="size-full flex flex-col bg-white overflow-hidden">
          <div className="flex-1 flex overflow-hidden min-h-0">
            <div className="w-1/2 border-r border-gray-200 overflow-hidden">
              <ResumeForm />
            </div>
            <div className="w-1/2 overflow-hidden bg-gray-100">
              <ResumePreview onChangeTemplate={() => setTemplateSelected(false)} />
            </div>
          </div>
        </div>
      )}
    </ResumeProvider>
  );
}
