import { useState } from 'react';
import { useResume } from '../ResumeContext';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Button } from '../ui/button';
import { X } from 'lucide-react';

export function SkillsStep() {
  const { resumeData, updateResumeData } = useResume();
  const [newSkill, setNewSkill] = useState('');

  const addSkill = () => {
    if (newSkill.trim()) {
      updateResumeData({ skills: [...resumeData.skills, newSkill.trim()] });
      setNewSkill('');
    }
  };

  const removeSkill = (index: number) => {
    updateResumeData({
      skills: resumeData.skills.filter((_, i) => i !== index)
    });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold mb-2">Skills</h2>
        <p className="text-gray-600 text-sm">
          List your professional skills, technical abilities, and areas of expertise.
        </p>
      </div>

      <div className="space-y-4">
        <div className="flex gap-2">
          <div className="flex-1 space-y-2">
            <Label htmlFor="skill" className="text-gray-600">Add skill</Label>
            <Input
              id="skill"
              value={newSkill}
              onChange={(e) => setNewSkill(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && addSkill()}
              className="bg-gray-50 border-gray-200"
              placeholder="e.g., Customer Assistance, Sales, Team Management"
            />
          </div>
          <div className="flex items-end">
            <Button onClick={addSkill} className="bg-blue-600 hover:bg-blue-700">
              Add
            </Button>
          </div>
        </div>

        {resumeData.skills.length > 0 && (
          <div className="space-y-2">
            <Label className="text-gray-600">Your skills</Label>
            <div className="flex flex-wrap gap-2">
              {resumeData.skills.map((skill, index) => (
                <div
                  key={index}
                  className="flex items-center gap-2 bg-gray-100 px-3 py-1.5 rounded-md text-sm"
                >
                  <span>{skill}</span>
                  <button
                    onClick={() => removeSkill(index)}
                    className="text-gray-500 hover:text-gray-700"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
