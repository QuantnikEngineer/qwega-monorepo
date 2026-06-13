import os
import re
from datetime import datetime

from google.adk.agents import LlmAgent
from google.adk.tools import ToolContext
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage


def get_rendered_markdown(tool_context: ToolContext) -> str:
    markdown = tool_context.state.get("rendered_markdown")
    if not markdown:
        raise ValueError("No rendered_markdown found in session state")
    return markdown



def markdown_to_pdf(markdown_text: str, tool_context: ToolContext, output_dir: str = "outputs") -> str:
    """Convert markdown_text to a PDF and return the file path.

    - Headings rendered as bold Helvetica.
    - **bold** removed and rendered as bold font.
    - Lines like **Key Responsibilities** become a bold-label paragraph.
    """
    os.makedirs(output_dir, exist_ok=True)

    file_name = f"user_manual_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
    file_path = os.path.join(output_dir, file_name)

    styles = getSampleStyleSheet()

    BASE_FONT = "Helvetica"
    BOLD_FONT = "Helvetica-Bold"

    styles.add(ParagraphStyle(name="TitleStyle", fontSize=18, leading=22, spaceAfter=14, fontName=BOLD_FONT))
    styles.add(ParagraphStyle(name="HeadingStyle", fontSize=14, leading=18, spaceAfter=10, fontName=BOLD_FONT))
    styles.add(ParagraphStyle(name="SubHeadingStyle", fontSize=12, leading=16, spaceAfter=8, fontName=BOLD_FONT))
    styles.add(ParagraphStyle(name="BoldLabelStyle", fontSize=11, leading=14, spaceAfter=6, fontName=BOLD_FONT))
    styles.add(ParagraphStyle(name="BodyStyle", fontSize=10.5, leading=14, spaceAfter=6, fontName=BASE_FONT))

    story = []

    def md_inline_to_rl(text: str) -> str:
        """Convert markdown inline bold: **text** -> <b>text</b>.

        Also escapes basic XML chars to avoid ReportLab parse issues.
        """
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        return text

    for line in markdown_text.split("\n"):
        stripped = line.strip()

        if not stripped:
            story.append(Spacer(1, 6))
            continue

        image_match = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if image_match:
            alt_text, image_path = image_match.groups()
            image_path = image_path.strip()

            if os.path.exists(image_path):
                pil_img = PILImage.open(image_path)
                w, h = pil_img.size
                aspect = h / float(w)

                target_width = 5 * inch
                target_height = target_width * aspect

                story.append(RLImage(image_path, width=target_width, height=target_height))
            else:
                story.append(
                    Paragraph(md_inline_to_rl(f"[Image missing: {alt_text} ({image_path})]"), styles["BodyStyle"])
                )

            story.append(Spacer(1, 8))
            continue

        bold_label_match = re.match(r"^\*\*(.+?)\*\*$", stripped)
        if bold_label_match:
            label_text = bold_label_match.group(1).strip()
            story.append(Paragraph(md_inline_to_rl(label_text), styles["BoldLabelStyle"]))
            continue

        if stripped.startswith("# "):
            story.append(Paragraph(md_inline_to_rl(stripped[2:]), styles["TitleStyle"]))
            continue

        if stripped.startswith("## "):
            story.append(Paragraph(md_inline_to_rl(stripped[3:]), styles["HeadingStyle"]))
            continue

        if stripped.startswith("### "):
            story.append(Paragraph(md_inline_to_rl(stripped[4:]), styles["SubHeadingStyle"]))
            continue

        if stripped.startswith("- "):
            story.append(Paragraph("• " + md_inline_to_rl(stripped[2:]), styles["BodyStyle"]))
            continue

        story.append(Paragraph(md_inline_to_rl(stripped), styles["BodyStyle"]))

    doc = SimpleDocTemplate(
        file_path,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    doc.build(story)
    return file_path



def store_pdf_path(file_path: str, tool_context: ToolContext) -> str:
    """Store generated PDF path in session state."""
    tool_context.state["pdf_path"] = file_path
    return f"PDF stored at: {file_path}"


PDF_EXPORTER_INSTRUCTION = """
You are a PDF Export Agent.

CRITICAL:
You MUST ALWAYS execute the steps below, regardless of input text.

STEPS:
1. Call get_rendered_markdown() to fetch markdown from session state.
2. Call markdown_to_pdf(markdown_text=<returned markdown>).
3. Call store_pdf_path(file_path=<returned file path>).
4. Return a short success message.

DO NOT skip any step.
DO NOT output markdown.
"""

pdf_export_agent = LlmAgent(
    name="pdf_export_agent",
    model=os.getenv("GEMINI_MODEL"),
    description="Exports rendered Markdown documentation to PDF and stores the path.",
    instruction=PDF_EXPORTER_INSTRUCTION,
    tools=[get_rendered_markdown, markdown_to_pdf, store_pdf_path],
)
