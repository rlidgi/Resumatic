import { ResumeData } from '../../types/resume';

interface ProfessionalTemplateProps {
  data: ResumeData;
}

export function ProfessionalTemplate({ data }: ProfessionalTemplateProps) {
  const name = String(data.firstName || 'Your') + ' ' + String(data.lastName || 'Name');
  const nameParts = name.split(/\s+/).filter(Boolean);
  const firstName = nameParts[0] || '';
  const lastName = nameParts.slice(1).join(' ');
  const title = String(data.occupation || '').trim();
  const contactParts = [
    String(data.address || '').trim(),
    String(data.phone || '').trim(),
    String(data.email || '').trim()
  ].filter(Boolean);

  return (
    <div data-template="professional" className="bg-white overflow-hidden w-full h-full font-serif p-4">
      <div
        className="px-3 pt-2 pb-1 text-center border-b"
        style={{ backgroundColor: '#c8cbd5', borderColor: '#3d4e6e' }}
      >
        <div className="text-sm font-bold tracking-wide uppercase">
          <span style={{ color: '#3d4e6e' }}>{firstName || 'YOUR'}</span>
          {lastName ? <span style={{ color: '#3d4e6e' }}> {lastName}</span> : null}
        </div>
        {title ? (
          <div className="mt-0.5 text-[7px] text-black/70">{title}</div>
        ) : null}
        {contactParts.length > 0 ? (
          <div className="mt-0.5 text-[7px] text-black/80">
            {contactParts.join(' - ')}
          </div>
        ) : null}
      </div>

      <div className="px-3 pb-3">
        {data.summary && (
          <Section
            title="Professional Summary"
            panelTone="secondary"
            panelIncludesHeader
            panelFullBleed
          >
            <p className="text-[7px] leading-tight text-black/80">{data.summary}</p>
          </Section>
        )}

        {data.experience.length > 0 && (
          <Section title="Work History">
            <div className="space-y-1.5">
              {data.experience.map((exp) => (
                <div key={exp.id} className="grid grid-cols-12 gap-2">
                  <div className="col-span-3 text-[7px] text-black/80 whitespace-nowrap">
                    {exp.startDate} - {exp.current ? 'Present' : exp.endDate}
                  </div>
                  <div className="col-span-9">
                    <div className="text-[7px] font-bold text-black">{exp.position}</div>
                    <div className="text-[7px] font-bold text-black/80">
                      {[exp.company, exp.location].filter(Boolean).join(' — ')}
                    </div>
                    {exp.description && (
                      <div className="mt-0.5 text-[7px] leading-tight text-black/80">
                        {exp.description.split('\n').map((line, idx) => (
                          <div key={idx}>{line}</div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {data.projects.length > 0 && (
          <Section title="Projects">
            <div className="space-y-1">
              {data.projects.map((proj) => (
                <div key={proj.id}>
                  <div className="flex items-baseline justify-between gap-2">
                    <div className="text-[7px] font-bold text-black">{proj.title}</div>
                    {proj.link && (
                      <a
                        href={proj.link}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[7px] text-black/70 underline underline-offset-1 hover:text-black"
                      >
                        Link
                      </a>
                    )}
                  </div>
                  {proj.technologies && proj.technologies.length > 0 && (
                    <div className="mt-0.5 text-[7px] text-black/70">{proj.technologies.join(', ')}</div>
                  )}
                  {proj.description && (
                    <div className="mt-0.5 text-[7px] leading-tight text-black/80">
                      {proj.description}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </Section>
        )}

        {data.skills.length > 0 && (
          <Section title="Skills">
            <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 text-[7px] text-black/80">
              {data.skills.slice(0, 12).map((s, idx) => (
                <div key={idx} className="flex items-start gap-1">
                  <span className="mt-[3px] w-0.5 h-0.5 rounded-full bg-black/70" />
                  <span>{s}</span>
                </div>
              ))}
            </div>
          </Section>
        )}

        {data.languages.length > 0 && (
          <Section title="Languages">
            <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-[7px] text-black/80">
              {data.languages.map((l) => (
                <span key={l.id}>{l.name} - {l.proficiency}</span>
              ))}
            </div>
          </Section>
        )}

        {data.certifications && data.certifications.length > 0 && (
          <Section title="Certifications">
            <div className="space-y-0.5 text-[7px] text-black/80">
              {data.certifications.map((c) => (
                <div key={c.id}>
                  <div className="font-bold text-black">{c.name}</div>
                  <div className="text-black/70">
                    {[c.issuer, c.date].filter(Boolean).join(' • ')}
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}

        {data.education.length > 0 && (
          <Section title="Education">
            <div className="space-y-1">
              {data.education.map((edu) => (
                <div key={edu.id} className="grid grid-cols-12 gap-2">
                  <div className="col-span-3 text-[7px] text-black/80 whitespace-nowrap">
                    {edu.startDate} - {edu.endDate}
                  </div>
                  <div className="col-span-9 text-[7px] text-black/85">
                    <div className="font-bold">{edu.degree}</div>
                    <div className="font-bold text-black/75">{edu.institution}</div>
                    {edu.location && <div className="text-black/70">{edu.location}</div>}
                  </div>
                </div>
              ))}
            </div>
          </Section>
        )}
      </div>
    </div>
  );
}

function Section({
  title,
  children,
  panelTone = 'none',
  panelIncludesHeader = false,
  panelFullBleed = false,
}: {
  title: string;
  children: React.ReactNode;
  panelTone?: 'none' | 'secondary' | 'secondary-dark';
  panelIncludesHeader?: boolean;
  panelFullBleed?: boolean;
}) {
  const panelColor = panelTone === 'secondary-dark'
    ? '#e8eaef'
    : panelTone === 'secondary'
      ? '#f5f6f8'
      : 'transparent';

  const headerRow = (
    <div className="flex items-center gap-2">
      <h2 className="text-[8px] font-bold tracking-wide uppercase whitespace-nowrap" style={{ color: '#3d4e6e' }}>
        {title}
      </h2>
      <div className="h-px flex-1" style={{ backgroundColor: '#3d4e6e' }} />
    </div>
  );

  return (
    <section className="mb-1.5 last:mb-0">
      {panelTone !== 'none' && panelIncludesHeader ? (
        <div
          className={panelFullBleed ? '-mx-3 px-3 py-1' : 'px-1.5 py-1'}
          style={{ backgroundColor: panelColor }}
        >
          {headerRow}
          <div className="mt-1">{children}</div>
        </div>
      ) : (
        <>
          {headerRow}
          <div className="mt-1">
            {panelTone === 'none' ? (
              children
            ) : (
              <div className="px-1.5 py-1" style={{ backgroundColor: panelColor }}>
                {children}
              </div>
            )}
          </div>
        </>
      )}
    </section>
  );
}
