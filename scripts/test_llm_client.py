from backend.app.llm.llm_client import LLMClient


def main():
    print("=" * 70)
    print("TESTING LLM CLIENT - PHASE 4.4")
    print("=" * 70)

    client = LLMClient()

    question = "What were the results of campaign CMP-021?"

    evidence = [
        {
            "document_id": "DOC-MKT-024",
            "filename": "campaign_postmortem_CMP-021.docx",
            "title": "Campaign Postmortem Cmp-021",
            "document_type": "MARKETING",
            "page_number": None,
            "paragraph_number": 6,
            "content": (
                "Campaign CMP-021 (NovaMart Growth Campaign 21) "
                "recorded spend of ₹1,840,000.00, revenue of "
                "₹5,270,000.00, 3812 conversions, and 47,919 clicks."
            ),
        }
    ]

    print("\nQuestion:")
    print(question)

    print("\nCalling LLM...")

    answer = client.generate_answer(
        question=question,
        evidence=evidence,
    )

    print("\nLLM Answer:")
    print("-" * 70)
    print(answer)

    assert answer
    assert "1,840,000" in answer
    assert "5,270,000" in answer
    assert "3812" in answer
    assert "47,919" in answer

    print("\n" + "=" * 70)
    print("PHASE 4.4 LLM CLIENT TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()