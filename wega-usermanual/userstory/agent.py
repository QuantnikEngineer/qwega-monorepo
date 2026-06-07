"""Root composition for the User Manual Writer pipeline.

The pipeline is a chain with a parallel fan-out in the middle. Once the
ingestion + extraction stages have populated session state, the four
content-writing agents (common-sections, role-based, faq, glossary) have
no data dependencies on each other – each only reads ``extraction_json``,
the image lists, and other ingestion-time state. They are therefore run
concurrently inside a ParallelAgent. The Markdown renderer then joins
their outputs.

Stage order:
    1. folder_reader_agent        – Ingests source documents and images.
    2. extraction_agent           – Extracts grounded structured facts.
    3. content_generation_group   – PARALLEL fan-out:
         a. common_sections_agent – Overview + Getting Started
         b. role_based_agent      – Per-role sections + per-role images
         c. faq_agent             – FAQs & Troubleshooting
         d. glossary_agent        – Glossary
    4. markdown_renderer_agent    – Assembles the final Markdown manual.

The four parallel agents are safe to run concurrently because:
  * Each reads only from session state populated by stage 1 + 2 (read-only).
  * Each writes to its own distinct ``output_key``
    (common_sections / role_sections / faq_section / glossary_section).
  * Only role_based_agent additionally writes to ``state["role_images"]``
    via its tool, which no sibling reads from.
"""

from google.adk.agents import ParallelAgent, SequentialAgent

from .common_sections_agent import common_sections_agent
from .extract_agent import extraction_agent
from .faq_agent import faq_agent
from .file_reader_agent import folder_reader_agent
from .glossary_agent import glossary_agent
from .role_based_agent import role_based_agent

content_generation_group = ParallelAgent(
    name="content_generation_group",
    description=(
        "Runs the four content-writing User Manual Writer stages in "
        "parallel: Overview/Getting Started, Role sections, FAQs, "
        "Glossary."
    ),
    sub_agents=[
        common_sections_agent,
        role_based_agent,
        faq_agent,
        glossary_agent,
    ],
)

root_agent = SequentialAgent(
    name="user_manual_writer_pipeline",
    description=(
        "USER MANUAL WRITER pipeline. Generates a complete, grounded, "
        "end-user user manual from source documents and embeds extracted "
        "architecture diagrams and Figma/UI images where relevant."
    ),
    sub_agents=[
        folder_reader_agent,
        extraction_agent,
        content_generation_group,
        # NOTE: markdown assembly is done in Python (main.py:_assemble_manual_from_state)
        # instead of an LLM agent — saves 30-60 s per run with no quality loss.
    ],
)
