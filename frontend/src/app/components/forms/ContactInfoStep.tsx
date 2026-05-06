import { useState } from 'react';
import { useResume } from '../ResumeContext';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Button } from '../ui/button';
import { ChevronDown } from 'lucide-react';

export function ContactInfoStep() {
  const { resumeData, updateResumeData } = useResume();
  const [showAdditional, setShowAdditional] = useState(false);

  const handleChange = (field: string, value: string) => {
    updateResumeData({ [field]: value });
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold mb-2">Tell us a little about yourself</h2>
        <p className="text-gray-600 text-sm">
          Let us know who you are, how employers can get in touch with you, and what your profession is.
        </p>
      </div>

      <div>
        <div className="flex items-center gap-2 mb-4">
          <h3 className="font-medium">Contact Information</h3>
          <button className="text-gray-400 hover:text-gray-600">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
            </svg>
          </button>
        </div>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="firstName" className="text-gray-600">First name</Label>
              <Input
                id="firstName"
                value={resumeData.firstName}
                onChange={(e) => handleChange('firstName', e.target.value)}
                className="bg-gray-50 border-gray-200"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="lastName" className="text-gray-600">Last name</Label>
              <Input
                id="lastName"
                value={resumeData.lastName}
                onChange={(e) => handleChange('lastName', e.target.value)}
                className="bg-gray-50 border-gray-200"
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="occupation" className="text-gray-600">Occupation</Label>
              <button className="text-gray-400 hover:text-gray-600">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </button>
            </div>
            <Input
              id="occupation"
              value={resumeData.occupation}
              onChange={(e) => handleChange('occupation', e.target.value)}
              className="bg-gray-50 border-gray-200"
            />
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Label htmlFor="address" className="text-gray-600">Address</Label>
              <button className="text-gray-400 hover:text-gray-600">
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </button>
            </div>
            <Input
              id="address"
              value={resumeData.address}
              onChange={(e) => handleChange('address', e.target.value)}
              className="bg-gray-50 border-gray-200"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="phone" className="text-gray-600">Phone</Label>
              <Input
                id="phone"
                value={resumeData.phone}
                onChange={(e) => handleChange('phone', e.target.value)}
                className="bg-gray-50 border-gray-200"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email" className="text-gray-600">Email</Label>
              <Input
                id="email"
                type="email"
                value={resumeData.email}
                onChange={(e) => handleChange('email', e.target.value)}
                className="bg-gray-50 border-gray-200"
              />
            </div>
          </div>

          {showAdditional && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="linkedin" className="text-gray-600">LinkedIn</Label>
                  <Input
                    id="linkedin"
                    value={resumeData.linkedin || ''}
                    onChange={(e) => handleChange('linkedin', e.target.value)}
                    className="bg-gray-50 border-gray-200"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="website" className="text-gray-600">Website</Label>
                  <Input
                    id="website"
                    value={resumeData.website || ''}
                    onChange={(e) => handleChange('website', e.target.value)}
                    className="bg-gray-50 border-gray-200"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="nationality" className="text-gray-600">Nationality</Label>
                  <Input
                    id="nationality"
                    value={resumeData.nationality || ''}
                    onChange={(e) => handleChange('nationality', e.target.value)}
                    className="bg-gray-50 border-gray-200"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="dateOfBirth" className="text-gray-600">Date of Birth</Label>
                  <Input
                    id="dateOfBirth"
                    value={resumeData.dateOfBirth || ''}
                    onChange={(e) => handleChange('dateOfBirth', e.target.value)}
                    className="bg-gray-50 border-gray-200"
                  />
                </div>
              </div>
            </>
          )}

          <button
            onClick={() => setShowAdditional(!showAdditional)}
            className="text-blue-600 hover:text-blue-700 text-sm font-medium flex items-center gap-1"
          >
            {showAdditional ? 'Hide additional fields' : 'Show additional fields'}
            <ChevronDown className={`w-4 h-4 transition-transform ${showAdditional ? 'rotate-180' : ''}`} />
          </button>
        </div>
      </div>
    </div>
  );
}
