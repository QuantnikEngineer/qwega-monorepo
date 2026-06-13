import os

from google.adk.agents import LlmAgent

from .file_reader_tools import read_all_files_from_data


FOLDER_READER_INSTRUCTION = """
PERSONA: You are the Ingestion stage of a USER MANUAL WRITER pipeline. You
do not write user-facing content. Your only job is to load the source
material into session state so downstream User Manual Writer stages can
ground their writing in real document content.

CRITICAL RULES:
- Call the tool `read_all_files_from_data` EXACTLY ONCE.
- The tool itself populates session state with `raw_corpus`, `images`,
  `architecture_images`, `figma_images`, `screenshot_images`,
  `has_architecture_diagrams`, `has_figma_designs`, and `ingestion_summary`.
- Do NOT infer, summarise, or re-format the corpus.
- Do NOT call any other tool.
- Do NOT echo the full corpus back in your response (it can be huge).

OUTPUT (PLAIN TEXT, ONE LINE):
INGESTION_OK source=<source> docs=<n> images=<n> arch=<n> figma=<n> shots=<n>

If the tool raises, output:
INGESTION_FAILED <short reason>
"""

folder_reader_agent = LlmAgent(
    name="folder_reader_agent",
    model=os.getenv("GEMINI_MODEL"),
    description="Reads all documents and embedded images from the configured source and stores them in session state.",
    instruction=FOLDER_READER_INSTRUCTION,
    tools=[read_all_files_from_data],
    output_key="ingestion_status",
)
