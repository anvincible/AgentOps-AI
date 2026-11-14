from pprint import pprint
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from backend.app.rag.document_loader import DocumentLoader


loader = DocumentLoader()


documents = [
    "data/novamart/documents/policies/return_refund_policy.pdf",
    "data/novamart/documents/marketing/campaign_postmortem_CMP-021.docx",
]


for file_path in documents:

    print("\n" + "=" * 70)
    print(f"TESTING: {file_path}")
    print("=" * 70)

    document = loader.load(file_path)

    print("\nDocument metadata:")
    print(f"Document ID:       {document['document_id']}")
    print(f"Filename:          {document['filename']}")
    print(f"File type:         {document['file_type']}")
    print(f"Title:             {document['title']}")
    print(f"Document type:     {document['document_type']}")
    print(f"Department:        {document['department']}")
    print(f"Region:            {document['region']}")
    print(f"Related entities:  {document['related_entity_ids']}")

    print("\nContent preview:")

    for item in document["content"][:3]:
        pprint(item)

    print("\nDocument loaded successfully.")