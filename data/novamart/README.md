# AgentOps AI Synthetic Dataset — NovaMart

**Synthetic academic dataset. Not real company data.**

Generated deterministically with seed `20260927`.

## Contents
- `structured/` — PostgreSQL-compatible CSV tables
- `source_of_truth/` — canonical JSON records used to generate structured data and document facts
- `documents/` — synthetic PDF/DOCX RAG corpus
- `metadata/` — document metadata, data dictionary and ER description
- `evaluation/` — labeled routing/RAG/SQL/hybrid evaluation questions
- `schema.sql` — PostgreSQL schema

## Core design
Structured and unstructured data represent the same fictional company, NovaMart.
Shared IDs include customer_id, seller_id, product_id, campaign_id, order_id and order_item_id.

## Important
Documents are synthetic academic artifacts. They must never be represented as real internal documents of a real company.


## Document-to-Entity Metadata Fix (v1.2)
The document metadata has been corrected so RAG retrieval can filter documents using the same business entities used by the SQL database. `metadata/document_metadata.csv` now contains populated `related_entity_ids` for campaign reports/postmortems, product catalog/warranty documents, customer segmentation, and business reports. A normalized `metadata/document_entity_links.csv` is also provided for reliable joins and metadata filtering. Evaluation questions now reference deterministic document IDs where applicable.

Entity IDs use the existing NovaMart identifiers: `CMP-*` for campaigns, `PROD-*` for products, and `CUS-*` for customers. Regional documents use their existing `region` metadata rather than inventing region entity IDs.


## Phase 0 canonical document IDs
The project metadata uses the canonical document IDs embedded in the actual PDF/DOCX files (for example DOC-MKT-010, DOC-PRD-001, DOC-POL-001). This matches the evaluation references and prevents ID mismatches during RAG ingestion, citation, and evaluation.
