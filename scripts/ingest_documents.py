
from pathlib import Path
import os
import sys

from dotenv import load_dotenv

# ------------------------------------------------------------
# Project configuration
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from backend.app.rag.document_loader import DocumentLoader
from backend.app.rag.document_cleaner import DocumentCleaner
from backend.app.rag.chunker import DocumentChunker
from backend.app.rag.embedder import DocumentEmbedder
from backend.app.rag.vector_store import VectorStore


DATASET_ROOT = PROJECT_ROOT / "data" / "novamart"

DOCUMENTS_DIR = DATASET_ROOT / "documents"
METADATA_FILE = DATASET_ROOT / "metadata" / "document_metadata.csv"
ENTITY_LINKS_FILE = DATASET_ROOT / "metadata" / "document_entity_links.csv"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


def main():
    print("=" * 70)
    print("AGENTOPS AI - DOCUMENT INGESTION")
    print("=" * 70)

    # --------------------------------------------------------
    # Validate input paths
    # --------------------------------------------------------

    print("\nChecking dataset paths...")

    required_paths = [
        DOCUMENTS_DIR,
        METADATA_FILE,
        ENTITY_LINKS_FILE,
    ]

    for path in required_paths:
        if not path.exists():
            raise FileNotFoundError(
                f"Required path not found: {path}"
            )

    print(f"Documents directory : {DOCUMENTS_DIR}")
    print(f"Metadata file       : {METADATA_FILE}")
    print(f"Entity links file   : {ENTITY_LINKS_FILE}")

    # --------------------------------------------------------
    # Initialize components
    # --------------------------------------------------------

    print("\nInitializing RAG components...")

    loader = DocumentLoader(
        metadata_path=str(METADATA_FILE),
        entity_links_path=str(ENTITY_LINKS_FILE),
    )

    cleaner = DocumentCleaner()

    chunker = DocumentChunker(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    embedder = DocumentEmbedder(
        model_name="all-MiniLM-L6-v2"
    )

    db_password = os.getenv("DB_PASSWORD")

    if not db_password:
        raise ValueError(
            "DB_PASSWORD is missing from the project .env file."
        )

    vector_store = VectorStore(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "novamart"),
        user=os.getenv("DB_USER", "postgres"),
        password=db_password,
    )

    # --------------------------------------------------------
    # Discover documents
    # --------------------------------------------------------

    document_files = sorted(
        path
        for path in DOCUMENTS_DIR.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".pdf", ".docx"}
    )

    print(f"\nDocuments found: {len(document_files)}")

    if not document_files:
        print("No PDF or DOCX documents found.")
        return

    # --------------------------------------------------------
    # Process documents
    # --------------------------------------------------------

    total_chunks = 0
    total_refreshed = 0
    successful_documents = 0
    failed_documents = 0

    for index, document_path in enumerate(
        document_files,
        start=1,
    ):
        print("\n" + "-" * 70)
        print(
            f"[{index}/{len(document_files)}] "
            f"{document_path.name}"
        )
        print("-" * 70)

        try:
            # 1. Load document and metadata
            document = loader.load(document_path)
            document_id = document["document_id"]

            print(f"Document ID: {document_id}")

            # 2. Clean document
            cleaned_document = cleaner.clean_document(document)

            # 3. Generate improved chunks
            chunks = chunker.chunk_document(cleaned_document)

            print(f"Chunks created: {len(chunks)}")

            if not chunks:
                print(
                    "WARNING: No chunks generated. "
                    "Existing database chunks were left unchanged."
                )
                failed_documents += 1
                continue

            # 4. Generate embeddings
            embedded_chunks = embedder.embed_chunks(chunks)

            if len(embedded_chunks) != len(chunks):
                raise RuntimeError(
                    "Embedding count does not match chunk count."
                )

            embedding_dimension = len(
                embedded_chunks[0]["embedding"]
            )

            print(
                f"Embeddings created: {len(embedded_chunks)} "
                f"(dimension: {embedding_dimension})"
            )

            # 5. Replace stored chunks for this document.
            # The refresh method uses a database transaction.
            refreshed = vector_store.refresh_document_chunks(
                embedded_chunks
            )

            print(f"Chunks refreshed: {refreshed}")

            total_chunks += len(embedded_chunks)
            total_refreshed += refreshed
            successful_documents += 1

        except Exception as error:
            failed_documents += 1
            print(f"ERROR processing {document_path.name}")
            print(f"Reason: {error}")

    # --------------------------------------------------------
    # Verify database
    # --------------------------------------------------------

    try:
        database_chunk_count = vector_store.count_chunks()
        print(f"\nChunks currently in database: {database_chunk_count}")
    except Exception as error:
        database_chunk_count = None
        print(f"\nDatabase count failed: {error}")

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("INGESTION SUMMARY")
    print("=" * 70)

    print(f"Documents found       : {len(document_files)}")
    print(f"Documents successful  : {successful_documents}")
    print(f"Documents failed      : {failed_documents}")
    print(f"Chunks generated      : {total_chunks}")
    print(f"Chunks refreshed      : {total_refreshed}")

    if database_chunk_count is not None:
        print(f"Chunks in database    : {database_chunk_count}")

    print("=" * 70)

    if failed_documents:
        print(
            "\nSome documents failed. Review their errors above "
            "before relying on the refreshed index."
        )


if __name__ == "__main__":
    main()
