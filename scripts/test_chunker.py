import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.app.rag.document_loader import DocumentLoader
from backend.app.rag.document_cleaner import DocumentCleaner
from backend.app.rag.chunker import DocumentChunker


loader = DocumentLoader()
cleaner = DocumentCleaner()
chunker = DocumentChunker(
    chunk_size=500,
    chunk_overlap=100,
)

documents = [
    "data/novamart/documents/policies/return_refund_policy.pdf",
    "data/novamart/documents/marketing/campaign_postmortem_CMP-021.docx",
]


for file_path in documents:
    print("\n" + "=" * 70)
    print(f"TESTING: {file_path}")
    print("=" * 70)

    # Load document
    document = loader.load(file_path)

    # Clean document
    cleaned_document = cleaner.clean_document(document)

    # Create chunks
    chunks = chunker.chunk_document(cleaned_document)

    print(f"\nDocument ID: {document['document_id']}")
    print(f"Total chunks: {len(chunks)}")

    print("\nFirst chunks:")
    print("-" * 70)

    for chunk in chunks[:5]:
        print(f"\nChunk ID: {chunk['chunk_id']}")
        print(f"Document ID: {chunk['document_id']}")
        print(f"Filename: {chunk['filename']}")
        print(f"Related entities: {chunk['related_entity_ids']}")

        if "page_number" in chunk:
            print(f"Page number: {chunk['page_number']}")

        if "paragraph_number" in chunk:
            print(f"Paragraph number: {chunk['paragraph_number']}")

        print(f"Text:\n{chunk['text']}")
        print("-" * 70)

    print("\nChunking completed successfully.")