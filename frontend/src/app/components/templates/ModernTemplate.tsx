import { ResumeData } from '../../types/resume';

interface ModernTemplateProps {
  data: ResumeData;
}

export function ModernTemplate({ data }: ModernTemplateProps) {
  const fullName = `${data.firstName || 'Your'} ${data.lastName || 'Name'}`.trim();
  const nameParts = fullName.split(/\s+/).filter(Boolean);
  const firstName = nameParts[0] || '';
  const lastName = nameParts.slice(1).join(' ');

  return (
    <div className="w-full h-full bg-white text-black overflow-auto">
      {/* Header */}
      <div className="px-3 pt-2 pb-1.5 border-b" style={{ backgroundColor: '#e8e9ed', borderColor: '#b4b8c5' }}>
        <div className="text-sm font-extrabold tracking-tight">
          <span className="text-slate-900">{firstName || 'Your'}</span>
          {lastName && <span className="text-slate-600"> {lastName}</span>}
        </div>
        <div className="mt-0.5 text-[7px] text-slate-700 font-medium">
          {data.occupation || 'Professional Title'}
        </div>

        <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[7px] text-slate-600">
          {data.address && <span>{data.address}</span>}
          {data.phone && <span>{data.phone}</span>}
          {data.email && <span>{data.email}</span>}
          {data.linkedin && <span>{data.linkedin}</span>}
        </div>
      </div>

      <div className="grid grid-cols-12 gap-0">
        {/* MAIN */}
        <main className="col-span-7 px-2 pt-2 pb-2">
          {/* Summary */}
          {data.summary && (
            <MainSection title="Summary">
              <p className="text-[7px] leading-tight text-slate-700">{data.summary}</p>
            </MainSection>
          )}

          {/* Experience */}
          {data.experience.length > 0 && (
            <MainSection title="Experience">
              <div className="space-y-1.5">
                {data.experience.map((exp) => (
                  <div key={exp.id}>
                    <div className="text-[7px] font-semibold text-slate-900">{exp.position}</div>
                    <div className="mt-0.5 text-[7px] text-slate-600 flex flex-wrap items-center gap-x-1">
                      <span className="font-medium text-slate-700">{exp.company}</span>
                      <span className="text-slate-300">•</span>
                      <span>{exp.startDate} - {exp.current ? 'Present' : exp.endDate}</span>
                      {exp.location && <><span className="text-slate-300">•</span><span>{exp.location}</span></>}
                    </div>
                    {exp.description && (
                      <div className="mt-1 text-[7px] leading-tight text-slate-700">
                        {exp.description.split('\n').map((line, idx) => (
                          <div key={idx}>{line}</div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </MainSection>
          )}

          {/* Projects */}
          {data.projects.length > 0 && (
            <MainSection title="Projects">
              <div className="space-y-1.5">
                {data.projects.map((proj) => (
                  <div key={proj.id}>
                    <div className="text-[7px] font-semibold text-slate-900">{proj.title}</div>
                    {proj.technologies && proj.technologies.length > 0 && (
                      <div className="mt-0.5 text-[7px] text-slate-600">{proj.technologies.join(', ')}</div>
                    )}
                    {proj.description && (
                      <div className="mt-1 text-[7px] leading-tight text-slate-700">{proj.description}</div>
                    )}
                  </div>
                ))}
              </div>
            </MainSection>
          )}
        </main>

        {/* SIDEBAR */}
        <aside className="col-span-5 -mr-0 px-2 py-2" style={{ backgroundColor: '#f5f6f8' }}>
          {/* Education */}
          {data.education.length > 0 && (
            <SideSection title="Education">
              <div className="space-y-2">
                {data.education.map((edu) => (
                  <div key={edu.id}>
                    <div className="text-[7px] font-semibold text-slate-900">{edu.degree}</div>
                    <div className="text-[7px] text-slate-700 font-medium">{edu.institution}</div>
                    <div className="mt-0.5 text-[7px] text-slate-500">
                      {edu.startDate} - {edu.endDate}
                      {edu.location && <span> • {edu.location}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </SideSection>
          )}

          {/* Skills */}
          {data.skills.length > 0 && (
            <SideSection title="Skills">
              <div className="grid grid-cols-3 gap-x-2 gap-y-1 text-[7px] text-slate-700">
                {data.skills.slice(0, 18).map((skill, idx) => (
                  <div key={idx} className="font-medium">{skill}</div>
                ))}
              </div>
            </SideSection>
          )}

          {/* Languages */}
          {data.languages.length > 0 && (
            <SideSection title="Languages">
              <div className="space-y-2">
                {data.languages.map((lang) => (
                  <LanguageRow key={lang.id} name={lang.name} level={lang.proficiency} />
                ))}
              </div>
            </SideSection>
          )}

          {/* Certifications */}
          {data.certifications && data.certifications.length > 0 && (
            <SideSection title="Certifications">
              <div className="space-y-2">
                {data.certifications.map((cert) => (
                  <div key={cert.id}>
                    <div className="text-[7px] font-semibold text-slate-900">{cert.name}</div>
                    <div className="mt-0 text-[7px] text-slate-600">
                      {[cert.issuer, cert.date].filter(Boolean).join(' • ')}
                    </div>
                  </div>
                ))}
              </div>
            </SideSection>
          )}
        </aside>
      </div>
    </div>
  );
}

function MainSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-3 last:mb-0">
      <h2 className="text-[7px] font-bold tracking-wide uppercase text-[#4a5c8c]">{title}</h2>
      <div className="h-px mt-1 mb-2" style={{ backgroundColor: '#b4b8c5' }} />
      {children}
    </section>
  );
}

function SideSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-3 last:mb-0">
      <h2 className="text-[7px] font-bold tracking-wide uppercase text-[#4a5c8c]">{title}</h2>
      <div className="h-px mt-1 mb-2" style={{ backgroundColor: '#b4b8c5' }} />
      {children}
    </section>
  );
}

function LanguageRow({ name, level }: { name: string; level: string }) {
  const dots = levelToDots(level);
  return (
    <div className="flex items-center justify-between gap-2">
      <div>
        <div className="text-[7px] font-semibold text-slate-900">{name}</div>
        <div className="text-[7px] text-slate-500">{level}</div>
      </div>
      <div className="flex items-center gap-0.5">
        {Array.from({ length: 5 }).map((_, idx) => (
          <span
            key={idx}
            className={`w-1.5 h-1.5 rounded-full ${idx < dots ? "bg-slate-600" : "bg-slate-200"}`}
          />
        ))}
      </div>
    </div>
  );
}

function levelToDots(level: string): number {
  const s = String(level || "").toLowerCase();
  if (s.includes("native")) return 5;
  if (s.includes("fluent")) return 5;
  if (s.includes("advanced")) return 4;
  if (s.includes("proficient")) return 4;
  if (s.includes("intermediate")) return 3;
  if (s.includes("basic") || s.includes("beginner")) return 2;
  return 3;
}
