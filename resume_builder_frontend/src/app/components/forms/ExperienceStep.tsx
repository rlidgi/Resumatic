import { useState } from 'react';
import { useResume } from '../ResumeContext';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Button } from '../ui/button';
import { Checkbox } from '../ui/checkbox';
import { WorkExperience } from '../../types/resume';
import { Trash2, Plus, Sparkles } from 'lucide-react';
import { formatDescriptionBullets } from '../../utils/formatDescriptionBullets';
import { rewriteWithAi } from '../../utils/aiAssist';
import { toast } from 'sonner';

export function ExperienceStep() {
  const { resumeData, updateResumeData } = useResume();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Partial<WorkExperience>>({});
  const [isAiLoading, setIsAiLoading] = useState(false);

  const startNew = () => {
    setEditingId('new');
    setFormData({
      position: '',
      company: '',
      location: '',
      startDate: '',
      endDate: '',
      current: false,
      description: '',
    });
  };

  const saveExperience = () => {
    if (!formData.position || !formData.company) return;

    const experience: WorkExperience = {
      id: editingId === 'new' ? Date.now().toString() : editingId!,
      position: formData.position || '',
      company: formData.company || '',
      location: formData.location || '',
      startDate: formData.startDate || '',
      endDate: formData.endDate || '',
      current: formData.current || false,
      description: formatDescriptionBullets(formData.description || ''),
    };

    if (editingId === 'new') {
      updateResumeData({ experience: [...resumeData.experience, experience] });
    } else {
      updateResumeData({
        experience: resumeData.experience.map(exp =>
          exp.id === editingId ? experience : exp
        ),
      });
    }

    setEditingId(null);
    setFormData({});
  };

  const deleteExperience = (id: string) => {
    updateResumeData({
      experience: resumeData.experience.filter(exp => exp.id !== id),
    });
  };

  const editExperience = (exp: WorkExperience) => {
    setEditingId(exp.id);
    setFormData(exp);
  };

  const handleAiAssist = async () => {
    if (isAiLoading) return;
    try {
      setIsAiLoading(true);
      const rewritten = await rewriteWithAi(
        'experience_description',
        formData.description || '',
        {
          title: formData.position || '',
          company: formData.company || '',
          dates: `${formData.startDate || ''} - ${formData.current ? 'Present' : formData.endDate || ''}`.trim(),
        },
      );
      setFormData({ ...formData, description: rewritten });
      toast.success('Description improved with AI.');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'AI assistance failed.');
    } finally {
      setIsAiLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {resumeData.experience.length > 0 && !editingId && (
        <div className="space-y-3">
          {resumeData.experience.map((exp) => (
            <div key={exp.id} className="p-4 border border-gray-200 rounded-lg">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-semibold">{exp.position}</h3>
                  <p className="text-sm text-gray-600">{exp.company} - {exp.location}</p>
                  <p className="text-sm text-gray-500">
                    {exp.startDate} - {exp.current ? 'Present' : exp.endDate}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => editExperience(exp)}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => deleteExperience(exp.id)}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {!editingId && (
        <Button onClick={startNew} className="w-full" variant="outline">
          <Plus className="w-4 h-4 mr-2" />
          Add Work Experience
        </Button>
      )}

      {editingId && (
        <div className="space-y-4 p-4 border border-gray-200 rounded-lg">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Position</Label>
              <Input
                value={formData.position || ''}
                onChange={(e) => setFormData({ ...formData, position: e.target.value })}
                className="bg-gray-50 border-gray-200"
              />
            </div>
            <div className="space-y-2">
              <Label>Company</Label>
              <Input
                value={formData.company || ''}
                onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                className="bg-gray-50 border-gray-200"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Location</Label>
            <Input
              value={formData.location || ''}
              onChange={(e) => setFormData({ ...formData, location: e.target.value })}
              className="bg-gray-50 border-gray-200"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Start Date</Label>
              <Input
                value={formData.startDate || ''}
                onChange={(e) => setFormData({ ...formData, startDate: e.target.value })}
                placeholder="e.g., Jan 2020"
                className="bg-gray-50 border-gray-200"
              />
            </div>
            <div className="space-y-2">
              <Label>End Date</Label>
              <Input
                value={formData.endDate || ''}
                onChange={(e) => setFormData({ ...formData, endDate: e.target.value })}
                placeholder="e.g., Mar 2023"
                disabled={formData.current}
                className="bg-gray-50 border-gray-200"
              />
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <Checkbox
              id="current"
              checked={formData.current || false}
              onCheckedChange={(checked) =>
                setFormData({ ...formData, current: checked as boolean })
              }
            />
            <label htmlFor="current" className="text-sm">
              I currently work here
            </label>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between gap-2">
              <Label>Description</Label>
              <Button
                type="button"
                size="sm"
                onClick={handleAiAssist}
                disabled={isAiLoading}
                className="bg-violet-600 text-white hover:bg-violet-700 border-violet-600"
              >
                <Sparkles className="w-4 h-4 mr-1.5" />
                {isAiLoading ? 'Assisting…' : 'Assist with AI'}
              </Button>
            </div>
            <Textarea
              value={formData.description || ''}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="bg-gray-50 border-gray-200 min-h-[100px]"
              placeholder="Describe your responsibilities and achievements..."
            />
            <p className="text-xs text-gray-500">Each statement will be formatted as a bullet point.</p>
          </div>

          <div className="flex gap-2">
            <Button onClick={saveExperience} className="bg-blue-600 hover:bg-blue-700">
              Save
            </Button>
            <Button onClick={() => setEditingId(null)} variant="outline">
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
