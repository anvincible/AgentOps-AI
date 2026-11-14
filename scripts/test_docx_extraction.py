from pathlib import Path
from docx import Document

DOCX_PATH = Path(
    "data/novamart/documents/marketing/campaign_postmortem_CMP-021.docx"
)

if not DOCX_PATH.exists():
    raise FileNotFoundError(f"DOCX not found: {DOCX_PATH}")

document = Document(DOCX_PATH)

print("=" * 60)
print("NovaMart DOCX Extraction Test")
print("=" * 60)
print(f"File: {DOCX_PATH}")
print(f"Paragraphs: {len(document.paragraphs)}")
print()

for paragraph_number, paragraph in enumerate(document.paragraphs, start=1):
    text = paragraph.text.strip()

    if text:
        print(f"--- PARAGRAPH {paragraph_number} ---")
        print(text)
        print()

print("=" * 60)
print("DOCX extraction completed successfully.")
print("=" * 60)