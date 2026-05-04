import { useState } from 'react';
import { useResume } from '../ResumeContext';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Button } from '../ui/button';
import { Education } from '../../types/resume';
import { Trash2, Plus } from 'lucide-react';

export function EducationStep() {
  const { resumeData, updateResumeData } = useResume();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Partial<Education>>({});

  const startNew = () => {
    setEditingId('new');
    setFormData({
      degree: '',
      institution: '',
      location: '',
      startDate: '',
      endDate: '',
      description: '',
    });
  };

  const saveEducation = () => {
    if (!formData.degree || !formData.institution) return;

    const education: Education = {
      id: editingId === 'new' ? Date.now().toString() : editingId!,
      degree: formData.degree || '',
      institution: formData.institution || '',
      location: formData.location || '',
      startDate: formData.startDate || '',
      endDate: formData.endDate || '',
      description: formData.description,
    };

    if (editingId === 'new') {
      updateResumeData({ education: [...resumeData.education, education] });
    } else {
      updateResumeData({
        education: resumeData.education.map(edu =>
          edu.id === editingId ? education : edu
        ),
      });
    }

    setEditingId(null);
    setFormData({});
  };

  const deleteEducation = (id: string) => {
    updateResumeData({
      education: resumeData.education.filter(edu => edu.id !== id),
    });
  };

  const editEducation = (edu: Education) => {
    setEditingId(edu.id);
    setFormData(edu);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold mb-2">Education</h2>
        <p className="text-gray-600 text-sm">
          Add your educational background, including degrees, institutions, and relevant coursework.
        </p>
      </div>

      {resumeData.education.length > 0 && !editingId && (
        <div className="space-y-3">
          {resumeData.education.map((edu) => (
            <div key={edu.id} className="p-4 border border-gray-200 rounded-lg">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-semibold">{edu.degree}</h3>
                  <p className="text-sm text-gray-600">{edu.institution} - {edu.location}</p>
                  <p className="text-sm text-gray-500">
                    {edu.startDate} - {edu.endDate}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => editEducation(edu)}
                  >
                    Edit
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => deleteEducation(edu.id)}
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
          Add Education
        </Button>
      )}

      {editingId && (
        <div className="space-y-4 p-4 border border-gray-200 rounded-lg">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Degree / Program</Label>
              <Input
                value={formData.degree || ''}
                onChange={(e) => setFormData({ ...formData, degree: e.target.value })}
                className="bg-gray-50 border-gray-200"
                placeholder="e.g., Bachelor of Science in Computer Science"
              />
            </div>
            <div className="space-y-2">
              <Label>Institution</Label>
              <Input
                value={formData.institution || ''}
                onChange={(e) => setFormData({ ...formData, institution: e.target.value })}
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
                placeholder="e.g., Sep 2018"
                className="bg-gray-50 border-gray-200"
              />
            </div>
            <div className="space-y-2">
              <Label>End Date</Label>
              <Input
                value={formData.endDate || ''}
                onChange={(e) => setFormData({ ...formData, endDate: e.target.value })}
                placeholder="e.g., Jun 2022"
                className="bg-gray-50 border-gray-200"
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Description (Optional)</Label>
            <Textarea
              value={formData.description || ''}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="bg-gray-50 border-gray-200 min-h-[80px]"
              placeholder="Awards, honors, relevant coursework..."
            />
          </div>

          <div className="flex gap-2">
            <Button onClick={saveEducation} className="bg-blue-600 hover:bg-blue-700">
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
