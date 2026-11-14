from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.orchestration.verification_agent import VerificationAgent


def main():
    agent = VerificationAgent()

    # Test 1: SQL answer with result rows
    sql_result = {
        "result": {
            "columns": ["campaign_id", "revenue_generated"],
            "rows": [["CMP-021", 5270000.00]],
        }
    }

    result = agent.verify(
        answer="Campaign CMP-021 generated revenue of 5,270,000.00.",
        route="SQL",
        sql_result=sql_result,
    )

    print("Test 1 — SQL with evidence")
    print(result)
    assert result["verified"] is True

    # Test 2: RAG answer with retrieved documents
    rag_result = {
        "evidence": [
            {
                "title": "Return Refund Policy",
                "content": "Eligible products may generally be returned within 30 days.",
            }
        ]
    }

    result = agent.verify(
        answer="The return policy describes a 30-day window.",
        route="RAG",
        rag_result=rag_result,
    )

    print("\nTest 2 — RAG with evidence")
    print(result)
    assert result["verified"] is True

    # Test 3: RAG answer with no evidence
    result = agent.verify(
        answer="The return policy allows returns.",
        route="RAG",
        rag_result={"evidence": []},
    )

    print("\nTest 3 — RAG without evidence")
    print(result)
    assert result["verified"] is False

    # Test 4: Greeting
    result = agent.verify(
        answer="Hello! I'm AgentOps AI.",
        route="CHAT",
    )

    print("\nTest 4 — Greeting")
    print(result)
    assert result["verified"] is True

    print("\nAll verification-agent tests passed.")


if __name__ == "__main__":
    main()
