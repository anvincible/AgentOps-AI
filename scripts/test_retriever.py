from pathlib import Path
import sys
from backend.app.database_config import load_database_config

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.rag.retriever import Retriever


def print_results(query: str, results: list[dict]):
    print("\n" + "=" * 70)
    print(f"QUERY: {query}")
    print("=" * 70)

    print(f"Results returned: {len(results)}")

    for index, result in enumerate(results, start=1):
        print("\n" + "-" * 70)
        print(f"RESULT {index}")
        print("-" * 70)

        print(f"Chunk ID:          {result['chunk_id']}")
        print(f"Document ID:       {result['document_id']}")
        print(f"Filename:          {result['filename']}")
        print(f"Document type:     {result['document_type']}")
        print(f"Related entities:  {result['related_entity_ids']}")

        if result.get("page_number") is not None:
            print(f"Page:              {result['page_number']}")

        if result.get("paragraph_number") is not None:
            print(f"Paragraph:         {result['paragraph_number']}")

        print(f"Similarity:        {result['similarity']:.4f}")

        print("\nContent:")
        print(result["content"])


def main():

    print("=" * 70)
    print("TESTING SEMANTIC RETRIEVER - FULL DATASET")
    print("=" * 70)

    db_config = load_database_config(require_explicit=True)
    retriever = Retriever(
        **db_config,
    )

    test_queries = [
        "What were the results of campaign CMP-021?",
        "What is NovaMart's return and refund policy?",
        "What products are available in the NovaMart catalog?",
        "What were the main business results in Q1?",
    ]

    for query in test_queries:

        print("\n")
        print_results(
            query,
            retriever.search(
                query=query,
                top_k=5,
            ),
        )

    print("\n" + "=" * 70)
    print("RETRIEVER TEST COMPLETED")
    print("=" * 70)


if __name__ == "__main__":
    main()