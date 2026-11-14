from pathlib import Path
import pymupdf

PDF_PATH = Path(
    "data/novamart/documents/policies/return_refund_policy.pdf"
)

if not PDF_PATH.exists():
    raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

document = pymupdf.open(PDF_PATH)

print("=" * 60)
print("NovaMart PDF Extraction Test")
print("=" * 60)
print(f"File: {PDF_PATH}")
print(f"Pages: {len(document)}")
print()

for page_number, page in enumerate(document, start=1):
    text = page.get_text("text").strip()

    print(f"--- PAGE {page_number} ---")
    print(text[:2000])
    print()

document.close()

print("=" * 60)
print("PDF extraction completed successfully.")
print("=" * 60)