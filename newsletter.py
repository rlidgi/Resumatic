"""
Monthly Newsletter System for ResumaticAI
Generates and sends AI-powered newsletters to subscribers
"""

import os
import json
import csv
import smtplib
import logging
import ast
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone
from typing import List, Dict, Optional
from dataclasses import dataclass
from jinja2 import Template
from email_audit import record_email_event

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class NewsletterConfig:
    """Configuration for newsletter system"""
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    sender_email: str = os.getenv("NEWSLETTER_EMAIL", "")
    sender_password: str = os.getenv("NEWSLETTER_PASSWORD", "")
    sender_name: str = "ResumaticAI Team"
    subject_prefix: str = "ResumaticAI Newsletter"
    unsubscribe_url: str = "https://resumaticai.com/unsubscribe"

class NewsletterGenerator:
    """Generates newsletter content using OpenAI"""
    
    def __init__(self):
        # Import lazily to avoid slowing or blocking overall app startup
        # when newsletter functionality is not being used.
        from openai import OpenAI

        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        # Configure timeout and retry for Azure reliability
        self.client = OpenAI(
            api_key=api_key,
            timeout=60.0,
            max_retries=3
        )

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        raw = (text or '').strip()
        if not raw:
            return ''
        if raw.startswith('```'):
            raw = re.sub(r'^```(?:json)?\s*\n?', '', raw, flags=re.IGNORECASE)
            raw = re.sub(r'\n?```\s*$', '', raw)
        return raw.strip()

    @staticmethod
    def _extract_first_json_object(text: str) -> str:
        """Extract the first top-level JSON object from a blob (best-effort)."""
        s = text or ''
        start = s.find('{')
        if start < 0:
            return ''

        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(s)):
            ch = s[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == '"':
                    in_string = False
                continue

            if ch == '"':
                in_string = True
                continue
            if ch == '{':
                depth += 1
                continue
            if ch == '}':
                depth -= 1
                if depth == 0:
                    return s[start:i + 1].strip()

        # Unbalanced braces; return tail as last resort.
        return s[start:].strip()

    @staticmethod
    def _cleanup_jsonish(text: str) -> str:
        """Clean up common JSON formatting issues (best-effort)."""
        s = (text or '').strip()
        if not s:
            return ''

        # Remove BOM / zero-width
        s = s.replace('\ufeff', '').replace('\u200b', '')

        # Fix smart quotes that break JSON
        s = s.replace('“', '"').replace('”', '"').replace('’', "'").replace('‘', "'")

        # Remove trailing commas before closing braces/brackets
        s = re.sub(r',\s*([}\]])', r'\1', s)
        return s.strip()

    @classmethod
    def _parse_llm_json(cls, raw_content: str) -> Dict:
        """Parse JSON from an LLM response with graceful repair/fallback."""
        candidates: list[str] = []

        raw = (raw_content or '').strip()
        if raw:
            candidates.append(raw)

        no_fences = cls._strip_code_fences(raw)
        if no_fences and no_fences != raw:
            candidates.append(no_fences)

        extracted = cls._extract_first_json_object(no_fences or raw)
        if extracted:
            candidates.append(extracted)

        # Cleanup pass for each candidate
        cleaned_candidates = []
        for c in candidates:
            cleaned_candidates.append(cls._cleanup_jsonish(c))
        candidates.extend([c for c in cleaned_candidates if c])

        seen: set[str] = set()
        unique_candidates: list[str] = []
        for c in candidates:
            if c and c not in seen:
                seen.add(c)
                unique_candidates.append(c)

        last_err: Exception | None = None
        for c in unique_candidates:
            try:
                obj = json.loads(c)
                if isinstance(obj, dict):
                    return obj
            except Exception as e:
                last_err = e

            # Fallback: tolerate single quotes / python-literal output
            try:
                py_obj = ast.literal_eval(c)
                if isinstance(py_obj, dict):
                    return py_obj
            except Exception as e:
                last_err = e

        raise ValueError(f"Invalid JSON response from OpenAI") from last_err

    @staticmethod
    def _strip_bullet_prefix(text: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        for prefix in ("•", "-", "–", "—", "*", "+"):
            if text.startswith(prefix):
                return text[len(prefix):].lstrip()
        # Handle numeric bullets like "1. foo" or "2) bar"
        if len(text) >= 3 and text[0].isdigit() and text[1] in (".", ")"):
            return text[2:].lstrip()
        return text

    @classmethod
    def _normalize_bullets_to_string(cls, value) -> str:
        """Ensure bullet content is a string using the '• ' delimiter."""
        if value is None:
            return ""

        if isinstance(value, (list, tuple)):
            items = [cls._strip_bullet_prefix(str(v)) for v in value]
            items = [v for v in items if v]
            return ("• " + "\n• ".join(items)) if items else ""

        # If it's a plain string, attempt to normalize common bullet formats
        text = str(value).strip()
        if not text:
            return ""

        # Already in preferred delimiter format
        if "• " in text:
            return text

        # Convert newline-based bullets to preferred delimiter
        lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]
        bulletish = [ln for ln in lines if ln.startswith(("•", "-", "–", "—", "*", "+")) or (len(ln) >= 3 and ln[0].isdigit() and ln[1] in (".", ")"))]
        if len(lines) >= 2 and bulletish:
            items = [cls._strip_bullet_prefix(ln) for ln in lines]
            items = [v for v in items if v]
            return ("• " + "\n• ".join(items)) if items else ""

        return text

    @staticmethod
    def _normalize_text(value) -> str:
        """Coerce any JSON value into a human-readable string."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (list, tuple)):
            parts = [str(v).strip() for v in value if str(v).strip()]
            return "\n\n".join(parts)
        if isinstance(value, dict):
            # Best-effort: keep it compact but readable
            try:
                return json.dumps(value, ensure_ascii=False)
            except Exception:
                return str(value)
        return str(value).strip()

    @classmethod
    def _normalize_newsletter_content(cls, content: Dict) -> Dict[str, str]:
        """Normalize LLM JSON so templates always receive strings."""
        if not isinstance(content, dict):
            return {
                "executive_summary": "",
                "featured_article": "",
                "quick_tips": "",
                "tool_spotlight": "",
                "industry_insights": "",
                "success_story": "",
                "upcoming_trends": "",
                "call_to_action": "",
            }

        normalized = {
            "executive_summary": cls._normalize_text(content.get("executive_summary")),
            "featured_article": cls._normalize_text(content.get("featured_article")),
            "quick_tips": cls._normalize_bullets_to_string(content.get("quick_tips")),
            "tool_spotlight": cls._normalize_text(content.get("tool_spotlight")),
            "industry_insights": cls._normalize_text(content.get("industry_insights")),
            "success_story": cls._normalize_text(content.get("success_story")),
            "upcoming_trends": cls._normalize_text(content.get("upcoming_trends")),
            "call_to_action": cls._normalize_text(content.get("call_to_action")),
        }

        return normalized
        
    def generate_newsletter_content(self, month: str, year: int, custom_topics: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Generate newsletter content using LLM
        
        Args:
            month: Month name (e.g., "January")
            year: Year (e.g., 2025)
            custom_topics: Optional list of specific topics to cover
            
        Returns:
            Dictionary with newsletter sections
        """
        try:
            # Build custom topics section
            topics_section = ""
            if custom_topics:
                topics_section = f"""
                
Specific topics to include:
{', '.join(custom_topics)}
"""
            
            prompt = f"""You are a career expert and content writer for ResumaticAI, an AI-powered resume optimization platform. 

Generate a comprehensive monthly newsletter for {month} {year} that provides value to job seekers. The newsletter should be professional, engaging, and actionable.

Include the following sections:

1. **Executive Summary** (2-3 sentences highlighting the key theme for this month)

2. **Featured Article** (400-500 words on a timely career topic - choose from: job market trends, resume optimization strategies, interview tips, career pivoting, salary negotiation, LinkedIn optimization, or industry-specific advice)

3. **Quick Tips** (3-4 actionable bullet points, each 1-2 sentences)

4. **Tool Spotlight** (150-200 words featuring a specific ResumaticAI feature or career tool)

5. **Industry Insights** (200-250 words on current job market trends, hiring patterns, or industry changes)

6. **Success Story** (Create a realistic but anonymized success story of someone improving their resume and landing a job - 150-200 words)

7. **Upcoming Trends** (100-150 words on what to expect in the job market next month)

8. **Call to Action** (Encouraging readers to use ResumaticAI or engage with our content)

{topics_section}

Guidelines:
- Write in a friendly but professional tone
- Include specific, actionable advice
- Make content relevant to job seekers at all levels
- Avoid overly promotional language
- Include relevant statistics or data points where appropriate
- Make sure the content feels fresh and timely for {month} {year}

Return the content in JSON format with keys: "executive_summary", "featured_article", "quick_tips", "tool_spotlight", "industry_insights", "success_story", "upcoming_trends", "call_to_action"

Respond with ONLY the JSON object, no markdown formatting or additional text."""

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            raw_content = response.choices[0].message.content

            try:
                content = self._parse_llm_json(raw_content)
                content = self._normalize_newsletter_content(content)
                logger.info(f"Successfully generated newsletter content for {month} {year}")
                return content
            except Exception as e:
                logger.error(f"Failed to parse newsletter JSON: {type(e).__name__}: {str(e)}")
                # Keep logs safe-ish: include a truncated payload for debugging.
                try:
                    snippet = (raw_content or '')
                    logger.error("Raw content (first 2000 chars): %s", snippet[:2000])
                except Exception:
                    pass
                raise
                
        except Exception as e:
            logger.error(f"Error generating newsletter content: {str(e)}")
            raise

    def generate_subject_line(self, month: str, year: int) -> str:
        """Generate an engaging subject line for the newsletter"""
        try:
            prompt = f"""Generate an engaging email subject line for a career/resume newsletter for {month} {year}. 

The subject line should be:
- Attention-grabbing but professional
- 6-8 words maximum
- Include the month/year
- Relevant to job seekers and career advancement
- Not overly salesy

Examples of good subject lines:
- "Your January 2025 Career Boost"
- "February Job Market Insights"
- "March Resume Tips Inside"

Generate ONE subject line only, no quotes or extra text."""

            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8
            )
            
            subject = response.choices[0].message.content.strip().strip('"\'')
            logger.info(f"Generated subject line: {subject}")
            return subject
            
        except Exception as e:
            logger.error(f"Error generating subject line: {str(e)}")
            # Fallback subject line
            return f"Your {month} {year} Career Newsletter"

class NewsletterTemplate:
    """Handles newsletter template rendering"""
    
    @staticmethod
    def get_html_template() -> str:
        """Return HTML email template"""
        return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ subject }}</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif; 
            line-height: 1.6; 
            color: #333; 
            max-width: 600px; 
            margin: 0 auto; 
            padding: 20px; 
            background-color: #f8fafc;
        }
        .header { 
            background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%); 
            color: white; 
            padding: 30px 20px; 
            text-align: center; 
            border-radius: 10px 10px 0 0; 
        }
        .content { 
            background: white; 
            padding: 30px; 
            border-radius: 0 0 10px 10px; 
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1); 
        }
        .section { 
            margin-bottom: 30px; 
            padding-bottom: 20px; 
            border-bottom: 1px solid #e5e7eb; 
        }
        .section:last-child { 
            border-bottom: none; 
        }
        .section-title { 
            color: #1f2937; 
            font-size: 18px; 
            font-weight: 600; 
            margin-bottom: 15px; 
            display: flex; 
            align-items: center; 
        }
        .section-title::before { 
            content: "▶"; 
            color: #3B82F6; 
            margin-right: 8px; 
        }
        .tips-list { 
            list-style: none; 
            padding: 0; 
        }
        .tips-list li { 
            padding: 8px 0; 
            padding-left: 20px; 
            position: relative; 
        }
        .tips-list li::before { 
            content: "✓"; 
            color: #10b981; 
            font-weight: bold; 
            position: absolute; 
            left: 0; 
        }
        .highlight-box { 
            background: #f0f9ff; 
            border-left: 4px solid #3B82F6; 
            padding: 15px; 
            margin: 15px 0; 
            border-radius: 0 5px 5px 0; 
        }
        .cta-button { 
            display: inline-block; 
            background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%); 
            color: white; 
            padding: 12px 24px; 
            text-decoration: none; 
            border-radius: 6px; 
            font-weight: 600; 
            margin: 10px 0; 
        }
        .footer { 
            text-align: center; 
            padding: 20px; 
            color: #6b7280; 
            font-size: 12px; 
            background: #f9fafb; 
            margin-top: 30px; 
            border-radius: 5px; 
        }
        .unsubscribe { 
            color: #6b7280; 
            text-decoration: none; 
            font-size: 11px; 
        }
        @media only screen and (max-width: 600px) {
            body { padding: 10px; }
            .header, .content { padding: 20px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1 style="margin: 0; font-size: 24px;">🚀 ResumaticAI Newsletter</h1>
        <p style="margin: 10px 0 0 0; opacity: 0.9;">{{ month }} {{ year }} - Your Career Advancement Partner</p>
    </div>
    
    <div class="content">
        <!-- Executive Summary -->
        <div class="section">
            <div class="highlight-box">
                <strong>This Month's Focus:</strong> {{ content.executive_summary }}
            </div>
        </div>
        
        <!-- Featured Article -->
        <div class="section">
            <h2 class="section-title">Featured Article</h2>
            <div>{{ content.featured_article | replace('\n', '<br>') }}</div>
        </div>
        
        <!-- Quick Tips -->
        <div class="section">
            <h2 class="section-title">Quick Career Tips</h2>
            <ul class="tips-list">
                {% for tip in content.quick_tips.split('• ') if tip.strip() %}
                <li>{{ tip.strip() }}</li>
                {% endfor %}
            </ul>
        </div>
        
        <!-- Tool Spotlight -->
        <div class="section">
            <h2 class="section-title">Tool Spotlight</h2>
            <div>{{ content.tool_spotlight | replace('\n', '<br>') }}</div>
        </div>
        
        <!-- Industry Insights -->
        <div class="section">
            <h2 class="section-title">Industry Insights</h2>
            <div>{{ content.industry_insights | replace('\n', '<br>') }}</div>
        </div>
        
        <!-- Success Story -->
        <div class="section">
            <h2 class="section-title">Success Story</h2>
            <div class="highlight-box">
                {{ content.success_story | replace('\n', '<br>') }}
            </div>
        </div>
        
        <!-- Upcoming Trends -->
        <div class="section">
            <h2 class="section-title">What's Coming Next Month</h2>
            <div>{{ content.upcoming_trends | replace('\n', '<br>') }}</div>
        </div>
        
        <!-- Call to Action -->
        <div class="section" style="text-align: center;">
            <h2 class="section-title" style="justify-content: center;">Ready to Boost Your Career?</h2>
            <div>{{ content.call_to_action | replace('\n', '<br>') }}</div>
            <br>
            <a href="https://resumaticai.com" class="cta-button">Optimize Your Resume Now</a>
        </div>
    </div>
    
    <div class="footer">
        <p>You're receiving this because you subscribed to ResumaticAI updates.</p>
        <p>ResumaticAI - AI-Powered Resume Optimization</p>
        <p><a href="{{ unsubscribe_url }}" class="unsubscribe">Unsubscribe</a></p>
    </div>
</body>
</html>
"""

    @staticmethod
    def get_text_template() -> str:
        """Return plain text email template"""
        return """
🚀 RESUMATIC AI NEWSLETTER - {{ month|upper }} {{ year }}
===============================================

{{ content.executive_summary }}

FEATURED ARTICLE
================
{{ content.featured_article }}

QUICK CAREER TIPS
=================
{{ content.quick_tips }}

TOOL SPOTLIGHT
==============
{{ content.tool_spotlight }}

INDUSTRY INSIGHTS
=================
{{ content.industry_insights }}

SUCCESS STORY
=============
{{ content.success_story }}

WHAT'S COMING NEXT MONTH
========================
{{ content.upcoming_trends }}

READY TO BOOST YOUR CAREER?
============================
{{ content.call_to_action }}

Visit us at: https://resumaticai.com

---
You're receiving this because you subscribed to ResumaticAI updates.
To unsubscribe, visit: {{ unsubscribe_url }}
"""

class NewsletterSender:
    """Handles sending newsletters via email"""
    
    def __init__(self, config: NewsletterConfig):
        self.config = config
        
    def get_subscribers(self) -> List[str]:
        """Read subscribers from CSV file"""
        subscribers = []
        try:
            if os.path.exists("subscribers.csv"):
                with open("subscribers.csv", "r") as f:
                    reader = csv.reader(f)
                    next(reader, None)  # Skip header if present
                    for row in reader:
                        if row and row[0].strip():
                            subscribers.append(row[0].strip())
            logger.info(f"Found {len(subscribers)} subscribers")
        except Exception as e:
            logger.error(f"Error reading subscribers: {str(e)}")
        return subscribers
    
    def send_newsletter(self, subject: str, html_content: str, text_content: str, 
                       subscribers: Optional[List[str]] = None) -> Dict[str, int]:
        """
        Send newsletter to subscribers
        
        Returns:
            Dictionary with send statistics
        """
        if not self.config.sender_email or not self.config.sender_password:
            raise ValueError("Email credentials not configured. Set NEWSLETTER_EMAIL and NEWSLETTER_PASSWORD environment variables.")
        
        if subscribers is None:
            subscribers = self.get_subscribers()
        
        if not subscribers:
            logger.warning("No subscribers found")
            return {"sent": 0, "failed": 0, "total": 0}
        
        sent_count = 0
        failed_count = 0
        
        try:
            # Connect to SMTP server
            server = smtplib.SMTP(self.config.smtp_server, self.config.smtp_port)
            server.starttls()
            server.login(self.config.sender_email, self.config.sender_password)
            
            for email in subscribers:
                try:
                    # Create message
                    msg = MIMEMultipart('alternative')
                    msg['Subject'] = subject
                    msg['From'] = f"{self.config.sender_name} <{self.config.sender_email}>"
                    msg['To'] = email
                    
                    # Add text and HTML versions
                    text_part = MIMEText(text_content, 'plain')
                    html_part = MIMEText(html_content, 'html')
                    
                    msg.attach(text_part)
                    msg.attach(html_part)
                    
                    # Send email
                    server.send_message(msg)
                    sent_count += 1
                    logger.info(f"Newsletter sent to {email}")
                    try:
                        record_email_event(
                            email_type="newsletter",
                            recipient=email,
                            subject=subject,
                            status="sent",
                            source="admin_newsletter",
                        )
                    except Exception:
                        pass
                    
                except Exception as e:
                    logger.error(f"Failed to send newsletter to {email}: {str(e)}")
                    failed_count += 1
                    try:
                        record_email_event(
                            email_type="newsletter",
                            recipient=email,
                            subject=subject,
                            status="failed",
                            source="admin_newsletter",
                            error=str(e),
                        )
                    except Exception:
                        pass
            
            server.quit()
            
        except Exception as e:
            logger.error(f"SMTP connection failed: {str(e)}")
            raise
        
        logger.info(f"Newsletter sending complete. Sent: {sent_count}, Failed: {failed_count}")
        return {
            "sent": sent_count,
            "failed": failed_count,
            "total": len(subscribers)
        }

class NewsletterManager:
    """Main class for managing newsletter operations"""
    
    def __init__(self, config: Optional[NewsletterConfig] = None):
        self.config = config or NewsletterConfig()
        self.generator = NewsletterGenerator()
        self.sender = NewsletterSender(self.config)
        
    def create_and_send_newsletter(self, month: str = None, year: int = None, 
                                 custom_topics: Optional[List[str]] = None,
                                 preview_only: bool = False) -> Dict[str, any]:
        """
        Generate and send monthly newsletter
        
        Args:
            month: Month name (defaults to current month)
            year: Year (defaults to current year)
            custom_topics: Optional topics to include
            preview_only: If True, generate content but don't send
            
        Returns:
            Dictionary with newsletter data and send results
        """
        # Default to current month/year
        if not month or not year:
            now = datetime.now()
            month = month or now.strftime("%B")
            year = year or now.year
        
        try:
            # Generate content
            logger.info(f"Generating newsletter content for {month} {year}")
            content = self.generator.generate_newsletter_content(month, year, custom_topics)
            
            # Generate subject line
            subject = self.generator.generate_subject_line(month, year)
            
            # Render templates
            html_template = Template(NewsletterTemplate.get_html_template())
            text_template = Template(NewsletterTemplate.get_text_template())
            
            html_content = html_template.render(
                subject=subject,
                month=month,
                year=year,
                content=content,
                unsubscribe_url=self.config.unsubscribe_url
            )
            
            text_content = text_template.render(
                month=month,
                year=year,
                content=content,
                unsubscribe_url=self.config.unsubscribe_url
            )
            
            result = {
                "month": month,
                "year": year,
                "subject": subject,
                "content": content,
                "html_content": html_content,
                "text_content": text_content,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
            
            if not preview_only:
                # Send newsletter
                logger.info("Sending newsletter to subscribers")
                send_stats = self.sender.send_newsletter(subject, html_content, text_content)
                result["send_stats"] = send_stats
            else:
                logger.info("Preview mode - newsletter generated but not sent")
                result["send_stats"] = {"preview_mode": True}
            
            # Save newsletter archive
            self._save_newsletter_archive(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating newsletter: {str(e)}")
            raise

    def _save_newsletter_archive(self, newsletter_data: Dict[str, any]):
        """Save newsletter to archive for record keeping"""
        try:
            # Create newsletters directory if it doesn't exist
            os.makedirs("newsletters", exist_ok=True)
            
            # Save as JSON
            filename = f"newsletters/newsletter_{newsletter_data['month']}_{newsletter_data['year']}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(newsletter_data, f, indent=2, ensure_ascii=False)
            
            # Save HTML version
            html_filename = f"newsletters/newsletter_{newsletter_data['month']}_{newsletter_data['year']}.html"
            with open(html_filename, "w", encoding="utf-8") as f:
                f.write(newsletter_data["html_content"])
            
            logger.info(f"Newsletter archived: {filename}")
            
        except Exception as e:
            logger.error(f"Error saving newsletter archive: {str(e)}")

# CLI interface for testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        # Preview mode for testing
        manager = NewsletterManager()
        result = manager.create_and_send_newsletter(preview_only=True)
        print(f"\nNewsletter Preview Generated!")
        print(f"Subject: {result['subject']}")
        print(f"Archived to: newsletters/newsletter_{result['month']}_{result['year']}.html")
        print("\nFirst 500 characters of content:")
        print(result['text_content'][:500] + "...")
    else:
        print("Usage: python newsletter.py preview")
