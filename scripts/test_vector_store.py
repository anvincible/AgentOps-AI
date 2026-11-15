import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.app.rag.document_loader import DocumentLoader
from backend.app.rag.document_cleaner import DocumentCleaner
from backend.app.rag.chunker import DocumentChunker
from backend.app.rag.embedder import DocumentEmbedder
from backend.app.rag.vector_store import VectorStore
from backend.app.database_config import load_database_config


db_config = load_database_config(require_explicit=True)


# Initialize pipeline components
loader = DocumentLoader()
cleaner = DocumentCleaner()

chunker = DocumentChunker(
    chunk_size=500,
    chunk_overlap=100,
)

embedder = DocumentEmbedder()

vector_store = VectorStore(
    **db_config,
)


# Test document
file_path = (
    "data/novamart/documents/marketing/"
    "campaign_postmortem_CMP-021.docx"
)


print("\n" + "=" * 70)
print("TESTING VECTOR STORE")
print("=" * 70)


# Step 1 — Load
print("\n1. Loading document...")
document = loader.load(file_path)

print(f"Document ID: {document['document_id']}")
print(f"Filename: {document['filename']}")


# Step 2 — Clean
print("\n2. Cleaning document...")
cleaned_document = cleaner.clean_document(document)


# Step 3 — Chunk
print("\n3. Creating chunks...")
chunks = chunker.chunk_document(cleaned_document)

print(f"Total chunks: {len(chunks)}")


# Step 4 — Embed
print("\n4. Creating embeddings...")
embedded_chunks = embedder.embed_chunks(chunks)

print(f"Embedded chunks: {len(embedded_chunks)}")


# Step 5 — Store
print("\n5. Storing chunks in PostgreSQL...")

inserted_count = vector_store.insert_chunks(
    embedded_chunks
)

print(f"Chunks inserted/updated: {inserted_count}")


# Step 6 — Verify count
print("\n6. Checking database...")

total_chunks = vector_store.count_chunks()

print(f"Total chunks currently in database: {total_chunks}")


# Final validation
assert inserted_count == len(embedded_chunks)

assert total_chunks >= len(embedded_chunks)

print("\n" + "=" * 70)
print("VECTOR STORE TEST COMPLETED SUCCESSFULLY")
print("=" * 70)
