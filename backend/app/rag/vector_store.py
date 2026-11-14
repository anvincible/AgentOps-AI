
from typing import Any

import psycopg
from pgvector.psycopg import register_vector


class VectorStore:
    """
    Stores document chunks and embeddings in PostgreSQL + pgvector.

    Supports:
    - Inserting new chunks
    - Updating existing chunks
    - Refreshing all chunks for specific documents
    - Removing stale chunks after document re-ingestion
    - Counting stored chunks
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "novamart",
        user: str = "postgres",
        password: str = "",
    ):
        self.connection_string = (
            f"host={host} "
            f"port={port} "
            f"dbname={database} "
            f"user={user} "
            f"password={password}"
        )

    @staticmethod
    def _prepare_chunk(chunk: dict[str, Any]) -> tuple:
        """Convert a chunk dictionary into database-ready values."""

        related_entity_ids = chunk.get("related_entity_ids", [])

        if related_entity_ids is None:
            related_entity_ids = []

        return (
            chunk["chunk_id"],
            chunk["document_id"],
            chunk["filename"],
            chunk["file_type"],
            chunk.get("title"),
            chunk.get("document_type"),
            chunk.get("department"),
            chunk.get("date"),
            chunk.get("version"),
            chunk.get("region"),
            psycopg.types.json.Jsonb(related_entity_ids),
            chunk.get("page_number"),
            chunk.get("paragraph_number"),
            chunk["text"],
            chunk["embedding"],
        )

    @staticmethod
    def _upsert_query() -> str:
        """Return the insert-or-update query."""

        return """
            INSERT INTO document_chunks (
                chunk_id,
                document_id,
                filename,
                file_type,
                title,
                document_type,
                department,
                document_date,
                version,
                region,
                related_entity_ids,
                page_number,
                paragraph_number,
                content,
                embedding
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (chunk_id)
            DO UPDATE SET
                document_id = EXCLUDED.document_id,
                filename = EXCLUDED.filename,
                file_type = EXCLUDED.file_type,
                title = EXCLUDED.title,
                document_type = EXCLUDED.document_type,
                department = EXCLUDED.department,
                document_date = EXCLUDED.document_date,
                version = EXCLUDED.version,
                region = EXCLUDED.region,
                related_entity_ids = EXCLUDED.related_entity_ids,
                page_number = EXCLUDED.page_number,
                paragraph_number = EXCLUDED.paragraph_number,
                content = EXCLUDED.content,
                embedding = EXCLUDED.embedding;
        """

    def insert_chunks(
        self,
        chunks: list[dict[str, Any]],
    ) -> int:
        """
        Insert or update chunks.

        This method does not delete stale chunks. Use
        refresh_document_chunks() when replacing a document's chunks.
        """

        if not chunks:
            return 0

        query = self._upsert_query()

        with psycopg.connect(self.connection_string) as connection:
            register_vector(connection)

            with connection.cursor() as cursor:
                for chunk in chunks:
                    cursor.execute(
                        query,
                        self._prepare_chunk(chunk),
                    )

        return len(chunks)

    def refresh_document_chunks(
        self,
        chunks: list[dict[str, Any]],
    ) -> int:
        """
        Replace stored chunks for every document represented in `chunks`.

        The deletion and inserts run in one transaction. If an insert fails,
        the transaction rolls back, preserving the previous stored chunks.

        Important:
        Pass the complete, newly generated chunk set for the documents
        being refreshed. Do not pass only a partial set of their chunks.
        """

        if not chunks:
            return 0

        document_ids = {
            chunk["document_id"]
            for chunk in chunks
        }

        if not document_ids:
            return 0

        query = self._upsert_query()

        with psycopg.connect(self.connection_string) as connection:
            register_vector(connection)

            with connection.cursor() as cursor:
                # Remove the old chunks for these documents first.
                cursor.execute(
                    """
                    DELETE FROM document_chunks
                    WHERE document_id = ANY(%s);
                    """,
                    (list(document_ids),),
                )

                # Insert the complete newly generated chunk set.
                for chunk in chunks:
                    cursor.execute(
                        query,
                        self._prepare_chunk(chunk),
                    )

        return len(chunks)

    def delete_document_chunks(
        self,
        document_id: str,
    ) -> int:
        """Delete all stored chunks for one document."""

        with psycopg.connect(self.connection_string) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM document_chunks
                    WHERE document_id = %s;
                    """,
                    (document_id,),
                )

                return cursor.rowcount

    def count_chunks(self) -> int:
        """Return the total number of stored document chunks."""

        with psycopg.connect(self.connection_string) as connection:
            register_vector(connection)

            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM document_chunks;"
                )

                result = cursor.fetchone()
                return result[0] if result else 0

    def count_chunks_for_document(
        self,
        document_id: str,
    ) -> int:
        """Return the number of stored chunks for one document."""

        with psycopg.connect(self.connection_string) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT COUNT(*)
                    FROM document_chunks
                    WHERE document_id = %s;
                    """,
                    (document_id,),
                )

                result = cursor.fetchone()
                return result[0] if result else 0
