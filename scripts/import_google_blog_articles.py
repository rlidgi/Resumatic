"""Convert the ten supplied Google Docs exports into unpublished blog templates."""

from __future__ import annotations

import html
import re
from pathlib import Path

import markdown
from docx import Document


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "temp_uploads" / "google_blog_import"
TEMPLATE_DIR = ROOT / "templates"

ARTICLES = [
    {
        "file": "article-01.docx",
        "slug": "best-ai-resume-builders-2026",
        "h2": {
            "How We Evaluated These Tools",
            "The Best AI Resume Builders in 2026",
            "How to Choose the Right AI Resume Builder",
            "FAQ",
        },
        "h3_prefixes": ("1. Resumatic AI", "2. Rezi", "3. Kickresume", "4. Jobscan", "5. Teal", "6. NeuraCV"),
        "h3": {"What stands out:", "Are AI resume builders worth it?", "Can AI-built resumes pass ATS?", "What's the difference between an AI resume builder and ChatGPT?"},
    },
    {
        "file": "article-02.docx",
        "slug": "rezi-alternative-2026",
        "h2": {"Where Resumatic AI Wins", "Where Rezi Wins", "When to Choose Resumatic AI Over Rezi", "When to Choose Rezi Over Resumatic AI", "The Bottom Line"},
        "h3": {"Deeper ATS Optimization", "Pricing", "Application Tracking", "Free Trial Model", "Broader Career Toolkit", "AI Resume Agent", "Chrome Extension", "Brand Recognition"},
    },
    {
        "file": "article-03.docx",
        "slug": "kickresume-alternative-2026",
        "h2": {"Where Resumatic AI Wins", "Where Kickresume Wins", "When to Choose Resumatic AI Over Kickresume", "When to Choose Kickresume Over Resumatic AI", "The Bottom Line"},
        "h3": {"Real ATS Optimization vs. a Checkbox", "Keyword Intelligence", "Application Tracking", "Pricing Simplicity", "Starting from Zero", "Template Library", "Cover Letters", "Mobile Apps", "LinkedIn Import", "Career Map"},
    },
    {
        "file": "article-04.docx",
        "slug": "beat-ats-2026",
        "h2": {"What Is an ATS and Why Does It Matter?", "7 Strategies to Beat ATS in 2026", "Common ATS Mistakes to Avoid", "Does ATS Still Matter in 2026?", "FAQ"},
        "h3_prefixes": ("1. Use the Exact", "2. Choose the Right", "3. Use Standard", "4. Keep Formatting", "5. Quantify", "6. Tailor", "7. Check"),
        "question_headings": True,
    },
    {
        "file": "article-05.docx",
        "slug": "ats-friendly-resume-2026",
        "h2": {"What Makes a Resume \"ATS-Friendly\"?", "ATS-Friendly Resume Format: The Rules", "ATS-Friendly Resume Template", "How to Optimize Your ATS-Friendly Resume", "What to Avoid in an ATS-Friendly Resume", "FAQ"},
        "h3": {"Use a Single-Column Layout", "Choose Standard, Readable Fonts", "Use Standard Section Headers", "Stick with Standard Bullet Points", "Save as .docx or .pdf", "Put Contact Info in the Document Body"},
        "h3_prefixes": ("1. Mirror", "2. Include", "3. Quantify", "4. Tailor", "5. Check"),
        "question_headings": True,
        "template_section": "ATS-Friendly Resume Template",
    },
    {
        "file": "article-06.docx",
        "slug": "resume-action-verbs-2026",
        "h2": {"Why Action Verbs Matter for Your Resume", "Resume Action Verbs by Category", "Power Words That Strengthen Any Resume", "Words to Remove from Your Resume", "How to Choose the Right Action Verb", "Test Your Word Choices"},
        "h3": {"Leadership & Management", "Achievement & Results", "Analysis & Research", "Creation & Development", "Communication & Collaboration", "Technical & Engineering", "Operations & Process", "Match the Job Description", "Match the Seniority Level", "Avoid Repetition", "Start Every Bullet with a Verb"},
    },
    {
        "file": "article-07.docx",
        "slug": "resume-bullet-points-2026",
        "h2": {"The Formula: Action Verb + Task + Result", "5 Rules for Effective Resume Bullet Points", "Resume Bullet Points by Experience Level", "Resume Summary vs. Resume Objective: Which to Use", "Common Bullet Point Mistakes", "Let AI Help with Your Bullet Points"},
        "h3_prefixes": ("Rule 1:", "Rule 2:", "Rule 3:", "Rule 4:", "Rule 5:"),
        "h3": {"Entry-Level (0-2 Years)", "Mid-Level (3-7 Years)", "Senior / Executive Level (8+ Years)", "Resume Summary (Use in Most Cases)", "Resume Objective (Use for Career Changes or Entry-Level)"},
    },
    {
        "file": "article-08.docx",
        "slug": "resume-format-guide-2026",
        "h2": {"The 3 Resume Formats", "How to Choose: Decision Guide", "Resume Formatting Rules for 2026", "ATS Formatting Essentials", "FAQ"},
        "h3_prefixes": ("1. Reverse-Chronological", "2. Functional", "3. Combination"),
        "question_headings": True,
    },
    {
        "file": "article-09.docx",
        "markdown_file": "content/blog/how-to-write-a-resume-2026.md",
        "slug": "how-to-write-a-resume-2026",
        "h2": {"Before You Start: Gather Your Materials", "Resume Mistakes to Avoid", "FAQ"},
        "h2_prefixes": ("Step 1:", "Step 2:", "Step 3:", "Step 4:", "Step 5:", "Step 6:", "Step 7:", "Step 8:", "Step 9:", "Step 10:"),
        "question_headings": True,
    },
    {
        "file": "article-10.docx",
        "slug": "resume-guide-by-career-level-2026",
        "h2_prefixes": ("Part 1:", "Part 2:", "Part 3:"),
        "h2": {"ATS Still Matters at Every Level"},
        "h3": {
            "The Challenge: You have experience, skills, and accomplishments - but your job titles and industry don't match your target role.",
            "The Challenge: You don't have much professional experience.",
            "Write a Bridge Summary that connects where you've been to where you're going.",
            "Write an Objective (Not a Summary) for entry-level.",
            "Turn Projects into Experience: Academic and personal projects count.",
            "Write an Executive Summary that reads like a leadership positioning statement.",
            "Two Pages Is Standard and Expected for executives.",
            "Condense Early Career: Roles from 15+ years ago get title + company + dates only.",
            "Career Change Resume Mistakes:",
            "Entry-Level Resume Mistakes:",
            "Executive Resume Mistakes:",
        },
    },
]


URL_RE = re.compile(r"(https?://[^\s)]+)")
LEADING_LABEL_RE = re.compile(r"^([^:]{2,34}:)(\s+.+)$")


def linkify(value: str) -> str:
    escaped = html.escape(value, quote=False)
    return URL_RE.sub(lambda match: f'<a href="{match.group(1)}" target="_blank" rel="noopener">{match.group(1)}</a>', escaped)


def paragraph_html(value: str) -> str:
    linked = linkify(value)
    label = LEADING_LABEL_RE.match(value)
    if label:
        safe_label = html.escape(label.group(1), quote=False)
        safe_tail = linkify(label.group(2).strip())
        return f"<p><strong>{safe_label}</strong> {safe_tail}</p>"
    return f"<p>{linked}</p>"


def matches_prefix(value: str, prefixes: tuple[str, ...]) -> bool:
    return any(value.startswith(prefix) for prefix in prefixes)


def build_markdown_body(source: Path) -> str:
    """Render a maintained Markdown article while the shared template owns its title/date."""
    source_text = source.read_text(encoding="utf-8")
    lines = source_text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines = lines[1:]
    if lines and re.fullmatch(r"\*Updated .+\*", lines[0].strip()):
        lines = lines[1:]

    rendered = markdown.markdown(
        "\n".join(lines),
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )
    rendered = re.sub(
        r'<a href="(https?://[^"]+)">',
        r'<a href="\1" target="_blank" rel="noopener">',
        rendered,
    )

    first_heading = rendered.find("<h2>")
    if first_heading > 0:
        rendered = (
            '<section class="intro">\n'
            + rendered[:first_heading].strip()
            + "\n</section>\n"
            + rendered[first_heading:]
        )
    return "\n".join(f"  {line}" for line in rendered.splitlines())


def build_body(config: dict, paragraphs: list[str]) -> str:
    output: list[str] = []
    list_type: str | None = None
    intro_open = False
    template_open = False
    current_h2 = ""

    def close_list() -> None:
        nonlocal list_type
        if list_type:
            output.append(f"</{list_type}>")
            list_type = None

    def close_intro() -> None:
        nonlocal intro_open
        if intro_open:
            output.append("</section>")
            intro_open = False

    def close_template() -> None:
        nonlocal template_open
        if template_open:
            output.append("</div>")
            template_open = False

    output.append('<section class="intro">')
    intro_open = True
    seen_title = False
    seen_date = False

    for value in paragraphs:
        if value == "---":
            close_list()
            continue
        if not seen_title:
            seen_title = True
            continue
        if value.startswith("Updated ") and not seen_date:
            seen_date = True
            continue
        # One source repeats its title/date block midway through the introduction.
        if value == paragraphs[0] or value.startswith("Updated "):
            continue

        is_h2 = value in config.get("h2", set()) or matches_prefix(value, config.get("h2_prefixes", ()))
        is_h3 = value in config.get("h3", set()) or matches_prefix(value, config.get("h3_prefixes", ()))
        if config.get("question_headings") and current_h2 == "FAQ" and value.endswith("?"):
            is_h3 = True

        if is_h2:
            close_list()
            close_intro()
            close_template()
            current_h2 = value
            output.append(f"<h2>{html.escape(value)}</h2>")
            if value == config.get("template_section"):
                output.append('<div class="article-template">')
                template_open = True
            continue
        if is_h3:
            close_list()
            close_intro()
            output.append(f"<h3>{html.escape(value)}</h3>")
            continue

        bullet_match = re.match(r"^[•●▪]\s*(.+)$", value)
        numbered_match = re.match(r"^\d+\.\s+(.+)$", value)
        if bullet_match or numbered_match:
            close_intro()
            desired = "ul" if bullet_match else "ol"
            if list_type != desired:
                close_list()
                output.append(f"<{desired}>")
                list_type = desired
            item = bullet_match.group(1) if bullet_match else numbered_match.group(1)
            output.append(f"<li>{linkify(item)}</li>")
            continue

        close_list()
        if template_open:
            output.append(linkify(value))
        else:
            output.append(paragraph_html(value))

    close_list()
    close_intro()
    close_template()
    return "\n".join(f"  {line}" for line in output)


def main() -> None:
    for config in ARTICLES:
        if config.get("markdown_file"):
            body = build_markdown_body(ROOT / config["markdown_file"])
        else:
            source = SOURCE_DIR / config["file"]
            doc = Document(source)
            paragraphs = [paragraph.text.strip() for paragraph in doc.paragraphs if paragraph.text.strip()]
            body = build_body(config, paragraphs)
        target = TEMPLATE_DIR / f"{config['slug']}.html"
        target.write_text(
            '{% extends "_unpublished_blog_post.html" %}\n'
            "{% block article_content %}\n"
            f"{body}\n"
            "{% endblock %}\n",
            encoding="utf-8",
        )
        print(f"Created {target.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
