import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.app.rag.document_loader import DocumentLoader
from backend.app.rag.document_cleaner import DocumentCleaner
from backend.app.rag.chunker import DocumentChunker
from backend.app.rag.embedder import DocumentEmbedder


loader = DocumentLoader()
cleaner = DocumentCleaner()
chunker = DocumentChunker(
    chunk_size=500,
    chunk_overlap=100,
)

embedder = DocumentEmbedder()

file_path = (
    "data/novamart/documents/marketing/"
    "campaign_postmortem_CMP-021.docx"
)

print("\nLoading document...")
document = loader.load(file_path)

print("Cleaning document...")
cleaned_document = cleaner.clean_document(document)

print("Creating chunks...")
chunks = chunker.chunk_document(cleaned_document)

print(f"Total chunks: {len(chunks)}")

print("\nCreating embeddings...")
embedded_chunks = embedder.embed_chunks(chunks)

print(f"Embedded chunks: {len(embedded_chunks)}")

first_embedding = embedded_chunks[0]["embedding"]

print("\nEmbedding information:")
print(f"Vector type: {type(first_embedding)}")
print(f"Vector dimensions: {len(first_embedding)}")
print(f"First 10 values: {first_embedding[:10]}")

print("\nChecking all chunks...")

for chunk in embedded_chunks:
    assert "embedding" in chunk
    assert len(chunk["embedding"]) == 384

print("All chunks contain 384-dimensional embeddings.")

print("\nEmbedding test completed successfully.")