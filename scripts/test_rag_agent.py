from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from backend.app.rag.rag_agent import RAGAgent
from backend.app.database_config import load_database_config


def main():
    print("=" * 70)
    print("TESTING RAG AGENT - PHASE 4.3")
    print("=" * 70)

    db_config = load_database_config(require_explicit=True)
    agent = RAGAgent(
        **db_config,
        top_k=5,
    )

    # ================================================================
    # TEST 1 — RETRIEVAL QUALITY
    # ================================================================

    question = "What were the results of campaign CMP-021?"

    print("\n" + "=" * 70)
    print("TEST 1 — RETRIEVAL QUALITY")
    print("=" * 70)

    print("\nQuestion:")
    print(question)

    response = agent.retrieve(question)

    print("\nNumber of final evidence chunks:")
    print(response["result_count"])

    print("\nRanked Evidence:")
    print("-" * 70)

    for index, evidence in enumerate(
        response["evidence"],
        start=1,
    ):
        print(f"\nEvidence {index}")
        print("-" * 70)

        print(f"Chunk ID: {evidence['chunk_id']}")
        print(f"Document ID: {evidence['document_id']}")
        print(f"Filename: {evidence['filename']}")
        print(f"Title: {evidence['title']}")
        print(f"Document Type: {evidence['document_type']}")
        print(f"Page: {evidence['page_number']}")
        print(f"Paragraph: {evidence['paragraph_number']}")
        print(f"Related Entities: {evidence['related_entity_ids']}")
        print(f"Similarity: {evidence['similarity']:.4f}")
        print(f"Evidence Score: {evidence['evidence_score']:.4f}")
        print(f"Entity Match: {evidence['entity_match']}")

        print("\nContent:")
        print(evidence["content"])

    # ------------------------------------------------
    # Basic validation
    # ------------------------------------------------

    assert response["result_count"] > 0

    assert response["result_count"] == len(
        response["evidence"]
    )

    assert response["result_count"] == len(
        response["sources"]
    )

    # ------------------------------------------------
    # Check whether actual campaign result information
    # was retrieved.
    # ------------------------------------------------

    combined_content = " ".join(
        evidence["content"].lower()
        for evidence in response["evidence"]
    )

    expected_terms = [
        "1,840,000",
        "5,270,000",
        "3812",
        "47,919",
    ]

    print("\n" + "=" * 70)
    print("CHECKING FOR CAMPAIGN RESULT INFORMATION")
    print("=" * 70)

    for term in expected_terms:
        if term.lower() in combined_content:
            print(f"FOUND: {term}")
        else:
            print(f"NOT FOUND: {term}")

    assert "1,840,000" in combined_content
    assert "5,270,000" in combined_content
    assert "3812" in combined_content
    assert "47,919" in combined_content

    print("\nPASS")

    # ================================================================
    # TEST 2 — SOURCE INFORMATION
    # ================================================================

    print("\n" + "=" * 70)
    print("TEST 2 — SOURCE INFORMATION")
    print("=" * 70)

    for index, source in enumerate(
        response["sources"],
        start=1,
    ):
        print(f"\nSource {index}")
        print("-" * 70)

        print(f"Document ID: {source['document_id']}")
        print(f"Filename: {source['filename']}")
        print(f"Title: {source['title']}")
        print(f"Document Type: {source['document_type']}")
        print(f"Chunk ID: {source['chunk_id']}")
        print(f"Page: {source['page_number']}")
        print(f"Paragraph: {source['paragraph_number']}")

    assert len(response["sources"]) > 0

    print("\nPASS")

    # ================================================================
    # TEST 3 — EMPTY QUESTION
    # ================================================================

    print("\n" + "=" * 70)
    print("TEST 3 — EMPTY QUESTION")
    print("=" * 70)

    try:
        agent.retrieve("")

        raise AssertionError(
            "Empty question should have raised ValueError."
        )

    except ValueError as error:
        print("\nExpected error:")
        print(error)

    print("\nPASS")

    # ================================================================
    # TEST 4 — WHITESPACE QUESTION
    # ================================================================

    print("\n" + "=" * 70)
    print("TEST 4 — WHITESPACE QUESTION")
    print("=" * 70)

    try:
        agent.retrieve("   ")

        raise AssertionError(
            "Whitespace-only question should have raised ValueError."
        )

    except ValueError as error:
        print("\nExpected error:")
        print(error)

    print("\nPASS")

    # ================================================================
    # FINAL RESULT
    # ================================================================

    print("\n" + "=" * 70)
    print("PHASE 4.3 RAG AGENT TEST COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()