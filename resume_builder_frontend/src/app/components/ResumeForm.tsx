import { useResume } from './ResumeContext';
import { Button } from './ui/button';
import { ContactInfoStep } from './forms/ContactInfoStep';
import { SummaryStep } from './forms/SummaryStep';
import { SkillsStep } from './forms/SkillsStep';
import { ExperienceStep } from './forms/ExperienceStep';
import { EducationStep } from './forms/EducationStep';
import { ProjectsStep } from './forms/ProjectsStep';

const steps = [
  { component: ContactInfoStep, title: 'Contact Info' },
  { component: SummaryStep, title: 'Summary' },
  { component: SkillsStep, title: 'Skills' },
  { component: ExperienceStep, title: 'Experience' },
  { component: EducationStep, title: 'Education' },
  { component: ProjectsStep, title: 'Projects' },
];

export function ResumeForm() {
  const { currentStep, setCurrentStep } = useResume();

  const CurrentStepComponent = steps[currentStep].component;

  const goNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const goPrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-auto p-8">
        <CurrentStepComponent />
      </div>

      <div className="border-t border-gray-200 p-6 flex justify-between">
        <Button
          onClick={goPrevious}
          variant="outline"
          disabled={currentStep === 0}
          className="px-6"
        >
          Previous
        </Button>
        <Button
          onClick={goNext}
          disabled={currentStep === steps.length - 1}
          className="bg-blue-600 hover:bg-blue-700 px-6"
        >
          Next
        </Button>
      </div>
    </div>
  );
}
