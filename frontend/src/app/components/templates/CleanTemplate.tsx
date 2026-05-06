import { ResumeData } from '../../types/resume';

interface CleanTemplateProps {
  data: ResumeData;
}

export function CleanTemplate({ data }: CleanTemplateProps) {
  const fullName = `${data.firstName || 'Your'} ${data.lastName || 'Name'}`.trim();
  const nameParts = fullName.split(/\s+/).filter(Boolean);
  const firstName = nameParts[0] || '';
  const lastName = nameParts.slice(1).join(' ');

  return (
    <div className="w-full h-full bg-white text-black overflow-auto">
      <div className="grid grid-cols-12 min-h-full">
        {/* LEFT COLUMN */}
        <aside className="col-span-4 p-3 bg-[#f5f3f0] border-r border-[#8b7d6b]">
          <div className="-mx-3 -mt-3 mb-3 px-3 pt-3 pb-3 bg-[#e8e3dd] border-b border-[#8b7d6b]">
            <h1 className="text-base font-bold uppercase tracking-tight text-black leading-tight">
              <span className="text-black">{(firstName || 'Your').toUpperCase()}</span>
              {lastName && <span className="text-black/50"> {(lastName || '').toUpperCase()}</span>}
            </h1>
            <div className="mt-0.5 text-[9px] font-normal text-black">
              {data.occupation || 'Professional Title'}
            </div>
          </div>

          {/* Contact Info */}
          {(data.address || data.phone || data.email) && (
            <SectionBlock title="INFO">
              {data.address && <InfoRow label="ADDRESS" value={data.address} />}
              {data.phone && <InfoRow label="PHONE" value={data.phone} />}
              {data.email && <InfoRow label="EMAIL" value={data.email} />}
            </SectionBlock>
          )}

          {/* Skills */}
          {data.skills.length > 0 && (
            <SectionBlock title="SKILLS" panelTone="secondary-dark">
              <div className="space-y-2">
                {data.skills.slice(0, 10).map((skill, idx) => (
                  <SkillBarRow key={idx} name={skill} />
                ))}
              </div>
            </SectionBlock>
          )}

          {/* Languages */}
          {data.languages.length > 0 && (
            <SectionBlock title="LANGUAGES">
              <div className="space-y-2">
                {data.languages.slice(0, 5).map((lang) => (
                  <LanguageBarRow key={lang.id} name={lang.name} level={lang.proficiency} />
                ))}
              </div>
            </SectionBlock>
          )}
        </aside>

        {/* RIGHT COLUMN */}
        <main className="col-span-8 p-3">
          {/* Summary */}
          {data.summary && (
            <SectionBlock title="PROFILE">
              <p className="text-[9px] leading-tight text-black text-justify">{data.summary}</p>
            </SectionBlock>
          )}

          {/* Experience */}
          {data.experience.length > 0 && (
            <SectionBlock title="EMPLOYMENT HISTORY">
              <div className="space-y-3">
                {data.experience.map((exp) => (
                  <div key={exp.id}>
                    <div className="flex justify-between items-baseline gap-2">
                      <div className="text-[9px] font-bold text-black">
                        {exp.position}, {exp.company}
                      </div>
                      {exp.location && <span className="text-[8px] text-black shrink-0">{exp.location}</span>}
                    </div>
                    <div className="text-[8px] text-black mt-0">
                      {exp.startDate} - {exp.current ? 'Present' : exp.endDate}
                    </div>
                    {exp.description && (
                      <div className="mt-1 text-[9px] leading-tight text-black">
                        {exp.description.split('\n').map((line, idx) => (
                          <div key={idx}>{line}</div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </SectionBlock>
          )}

          {/* Education */}
          {data.education.length > 0 && (
            <SectionBlock title="EDUCATION">
              <div className="space-y-2">
                {data.education.map((edu) => (
                  <div key={edu.id}>
                    <div className="flex items-baseline justify-between gap-2">
                      <div className="text-[9px] font-bold text-black">
                        {edu.degree}
                        {edu.institution && ` — ${edu.institution}`}
                      </div>
                      <span className="text-[8px] text-black shrink-0">
                        {edu.startDate} - {edu.endDate}
                      </span>
                    </div>
                    {edu.location && (
                      <div className="text-[8px] text-slate-600 mt-0">{edu.location}</div>
                    )}
                  </div>
                ))}
              </div>
            </SectionBlock>
          )}

          {/* Projects */}
          {data.projects.length > 0 && (
            <SectionBlock title="PROJECTS">
              <div className="space-y-3">
                {data.projects.map((proj) => (
                  <div key={proj.id}>
                    <div className="flex justify-between items-baseline gap-2">
                      <div className="text-[9px] font-bold text-black">{proj.title}</div>
                      {proj.link && (
                        <a href={proj.link} target="_blank" rel="noreferrer" className="text-[8px] text-slate-600 underline shrink-0">
                          Link
                        </a>
                      )}
                    </div>
                    {proj.technologies && proj.technologies.length > 0 && (
                      <div className="text-[8px] text-slate-600 mt-0">{proj.technologies.join(', ')}</div>
                    )}
                    {proj.description && (
                      <div className="mt-1 text-[9px] leading-tight text-black">{proj.description}</div>
                    )}
                  </div>
                ))}
              </div>
            </SectionBlock>
          )}

          {/* Certifications */}
          {data.certifications && data.certifications.length > 0 && (
            <SectionBlock title="CERTIFICATIONS" panelTone="secondary">
              <div className="space-y-1">
                {data.certifications.map((cert) => (
                  <div key={cert.id} className="text-[9px] text-black">
                    <span className="font-bold">{cert.name}</span>
                    {cert.issuer && <span className="text-slate-600"> — {cert.issuer}</span>}
                    {cert.date && <span className="text-slate-500"> ({cert.date})</span>}
                  </div>
                ))}
              </div>
            </SectionBlock>
          )}
        </main>
      </div>
    </div>
  );
}

function SectionBlock({
  title,
  children,
  panelTone = 'none',
}: {
  title: string;
  children: React.ReactNode;
  panelTone?: 'none' | 'secondary' | 'secondary-dark';
}) {
  return (
    <section className="mb-3 last:mb-0">
      <h2 className="text-[10px] font-bold uppercase tracking-wide text-[#8b7d6b]">{title}</h2>
      <div className="h-px mt-0.5 mb-1.5 w-12 bg-[#8b7d6b]" />
      {panelTone === 'none' ? (
        children
      ) : (
        <div
          className="rounded-md p-2"
          style={{
            backgroundColor: panelTone === 'secondary-dark' ? '#e8e3dd' : '#f5f3f0',
          }}
        >
          {children}
        </div>
      )}
    </section>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="mb-1.5">
      <span className="text-[8px] font-bold text-black block">{label}</span>
      <span className="text-[8px] text-black block mt-0">{value || '—'}</span>
    </div>
  );
}

function levelToPercent(level: string): number {
  const s = String(level || "").toLowerCase();
  if (s.includes("native") || s.includes("fluent")) return 100;
  if (s.includes("advanced") || s.includes("proficient")) return 90;
  if (s.includes("intermediate")) return 75;
  if (s.includes("basic") || s.includes("beginner")) return 50;
  return 80;
}

function SkillBarRow({ name }: { name: string }) {
  const pct = levelToPercent("proficient");
  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-0.5">
        <span className="text-[8px] text-black flex-1">{name}</span>
        <div className="flex-1 min-w-[60px] h-1 rounded overflow-hidden bg-[#f5f3f0]">
          <div className="h-full rounded bg-[#8b7d6b]" style={{ width: `${pct}%` }} />
        </div>
      </div>
    </div>
  );
}

function LanguageBarRow({ name, level }: { name: string; level: string }) {
  const pct = levelToPercent(level);
  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-0.5">
        <span className="text-[8px] text-black flex-1">{name}</span>
        <div className="flex-1 min-w-[60px] h-1 rounded overflow-hidden bg-[#f5f3f0]">
          <div className="h-full rounded bg-[#8b7d6b]" style={{ width: `${pct}%` }} />
        </div>
      </div>
    </div>
  );
}
