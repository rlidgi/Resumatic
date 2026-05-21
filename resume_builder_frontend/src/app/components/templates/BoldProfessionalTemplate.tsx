import { ResumeData } from '../../types/resume';

interface BoldProfessionalTemplateProps {
  data: ResumeData;
}

export function BoldProfessionalTemplate({ data }: BoldProfessionalTemplateProps) {
  console.log('BoldProfessionalTemplate - data:', data);
  console.log('BoldProfessionalTemplate - experience:', data.experience);
  console.log('BoldProfessionalTemplate - education:', data.education);

  const name = `${data.firstName || 'Your'} ${data.lastName || 'Name'}`.trim();
  const initials = getInitials(name);
  const contactParts = [data.address, data.phone, data.email].filter(Boolean);

  return (
    <div className="w-full h-full bg-white text-black overflow-auto p-4">
      {/* Header */}
      <div className="border-b border-[#e5a87c] pb-3 mb-1.5">
        <div className="flex items-center gap-2">
          <div className="w-10 h-10 border-2 border-black grid place-items-center font-extrabold tracking-wide text-base leading-none">
            {initials}
          </div>
          <div className="flex items-baseline gap-2 flex-wrap">
            <div className="text-sm font-extrabold tracking-tight text-black uppercase">
              {data.firstName || 'YOUR'}
            </div>
            <div className="text-sm font-extrabold tracking-tight text-[#e5a87c] uppercase">
              {data.lastName || 'NAME'}
            </div>
          </div>
        </div>

        {contactParts.length > 0 && (
          <div className="mt-1 text-black text-[7px] px-2 py-1 font-semibold">
            {contactParts.join(" | ")}
          </div>
        )}
      </div>

      {/* Summary */}
      {data.summary && (
        <Section title="Professional Summary">
          <p className="text-[7px] leading-tight text-black/80">{data.summary}</p>
        </Section>
      )}

      {/* Experience */}
      {data.experience.length > 0 && (
        <Section title="Work History">
          <div className="space-y-1.5">
            {data.experience.map((exp) => (
              <div key={exp.id}>
                <div className="flex items-baseline justify-between gap-4">
                  <div className="font-semibold text-[7px] text-black">{exp.position}</div>
                  <div className="text-[7px] text-black/70 whitespace-nowrap">
                    {exp.startDate} - {exp.current ? 'Present' : exp.endDate}
                  </div>
                </div>
                <div className="text-[7px] text-black/80 font-semibold">
                  {exp.company}
                  {exp.location && <span className="font-semibold text-black/70"> – {exp.location}</span>}
                </div>
                {exp.description && (
                  <div className="mt-1 text-[7px] leading-tight text-black/80">
                    {exp.description.split('\n').map((line, idx) => (
                      <div key={idx}>{line}</div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Projects */}
      {data.projects.length > 0 && (
        <Section title="Projects">
          <div className="space-y-1.5">
            {data.projects.map((proj) => (
              <div key={proj.id}>
                <div className="flex items-baseline justify-between gap-4">
                  <div className="font-semibold text-[7px] text-black">{proj.title}</div>
                  {proj.link && (
                    <a
                      href={proj.link}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[7px] text-black/70 whitespace-nowrap underline underline-offset-2 hover:text-black"
                    >
                      Link
                    </a>
                  )}
                </div>
                {proj.technologies && proj.technologies.length > 0 && (
                  <div className="text-[7px] text-black/70">{proj.technologies.join(', ')}</div>
                )}
                {proj.description && (
                  <div className="mt-1 text-[7px] leading-tight text-black/80">
                    {proj.description}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Skills */}
      {data.skills.length > 0 && (
        <Section title="Skills">
          <div className="grid grid-cols-2 gap-x-6 gap-y-2">
            {data.skills.slice(0, 10).map((skill, idx) => (
              <SkillRow key={idx} name={skill} level={guessLevel(skill)} />
            ))}
          </div>
        </Section>
      )}

      {/* Languages */}
      {data.languages.length > 0 && (
        <Section title="Languages">
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[7px] text-black/80">
            {data.languages.map((lang) => (
              <span key={lang.id}>{lang.name} - {lang.proficiency}</span>
            ))}
          </div>
        </Section>
      )}

      {/* Education */}
      {data.education.length > 0 && (
        <Section title="Education">
          <div className="space-y-1">
            {data.education.map((edu) => (
              <div key={edu.id} className="flex items-baseline justify-between gap-4">
                <div className="text-[7px] text-black/85">
                  <span className="font-semibold">{edu.degree}</span>
                  <span className="text-black/70"> — {edu.institution}</span>
                  {edu.location && <span className="text-black/70"> • {edu.location}</span>}
                </div>
                <div className="text-[7px] text-black/70 whitespace-nowrap">
                  {edu.startDate} - {edu.endDate}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Certifications */}
      {data.certifications && data.certifications.length > 0 && (
        <Section title="Certifications">
          <ul className="list-disc pl-5 text-[7px] text-black/80 space-y-1">
            {data.certifications.slice(0, 6).map((cert) => (
              <li key={cert.id}>
                {cert.name}
                {cert.issuer && <span className="text-black/70"> — {cert.issuer}</span>}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-1.5 last:mb-0">
      <div className="flex items-end justify-between gap-4">
        <h2 className="text-[7px] font-bold text-black uppercase tracking-wide">{title}</h2>
      </div>
      <div className="h-1 mt-1 mb-1.5 bg-[#e5a87c]" />
      {children}
    </section>
  );
}

function SkillRow({ name, level }: { name: string; level: number }) {
  const normalized = level > 1 ? (level / 8) : level;
  const count = Math.max(0, Math.min(8, Math.round(normalized * 8)));

  return (
    <div className="flex items-center justify-between gap-2">
      <div className="min-w-0 flex-1 text-[7px] font-semibold text-black/85">{name}</div>
      <div className="flex items-center gap-0.5">
        {Array.from({ length: 8 }).map((_, idx) => (
          <div
            key={idx}
            className="w-2 h-2 shrink-0"
            style={{ backgroundColor: idx < count ? '#e5a87c' : '#d9d9d9' }}
          />
        ))}
      </div>
    </div>
  );
}

function getInitials(name: string): string {
  const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "YN";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
}

function guessLevel(name: string): number {
  const s = (name || "").toLowerCase().trim();
  let acc = 0;
  for (let i = 0; i < s.length; i++) acc = (acc * 31 + s.charCodeAt(i)) >>> 0;
  return 0.45 + ((acc % 46) / 100);
}
