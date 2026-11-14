from backend.app.rag.retriever import Retriever
from backend.app.database_config import load_database_config

config = load_database_config()

retriever = Retriever(
    host=config["host"],
    port=config["port"],
    database=config["database"],
    user=config["user"],
    password=config["password"],
)

query = "What information is available about campaign performance?"
results = retriever.search(query, top_k=5)

print(f"\nQuery: {query}")
print(f"Results found: {len(results)}\n")

for i, result in enumerate(results, start=1):
    print(f"--- Result {i} ---")
    print("Title:", result["title"])
    print("Document:", result["filename"])
    print("Similarity:", round(result["similarity"], 4))
    print("Relevance:", round(result["relevance_score"], 4))
    print("Content:", result["content"][:500])
    print()