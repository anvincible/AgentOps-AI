import sys
from pathlib import Path
from pprint import pprint

sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.app.rag.document_loader import DocumentLoader
from backend.app.rag.document_cleaner import DocumentCleaner


loader = DocumentLoader()
cleaner = DocumentCleaner()

documents = [
    "data/novamart/documents/policies/return_refund_policy.pdf",
    "data/novamart/documents/marketing/campaign_postmortem_CMP-021.docx",
]

for file_path in documents:
    print("\n" + "=" * 70)
    print(f"TESTING: {file_path}")
    print("=" * 70)

    document = loader.load(file_path)

    print("\nBEFORE CLEANING:")
    print("-" * 70)

    for item in document["content"][:1]:
        print(item["text"])

    cleaned_document = cleaner.clean_document(document)

    print("\nAFTER CLEANING:")
    print("-" * 70)

    for item in cleaned_document["content"][:1]:
        print(item["text"])

    print("\nCleaning completed successfully.")