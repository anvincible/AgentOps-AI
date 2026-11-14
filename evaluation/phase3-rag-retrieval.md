# Phase 3 RAG Retrieval Evaluation

Executed against the live PostgreSQL-backed index through Angular's `/api/ask`
proxy at `http://[::1]:4200/api/ask`. The API reports source document IDs and
verification state; retrieval scores below were captured with the existing
retriever against the same unchanged index.

## Retrieval score comparison

Scores are raw cosine similarity / reranker score. Baseline is the pre-tuning
capture; updated scores include query expansion and the `0.30` raw similarity
floor. These comparisons are retrieval candidates, not proof that a claim is
supported; answer composition still checks content and requested facets.

| Evaluation query | Baseline candidates | Updated candidates | Outcome |
|---|---|---|---|
| “How long after buying something can a customer send it back for a refund?” | DOC-POL-001-001 `0.4714 / 0.5517`; no excerpt selected | DOC-POL-001-001 `0.5796 / 0.6807`; selected | Paraphrase now returns the 30-calendar-day policy; verified |
| “What does the return policy say, and how many returns were recorded?” | DOC-POL-001 `0.501 / 0.623` | DOC-POL-001 `0.5901 / 0.7154` | Hybrid SQL + policy evidence; verified |
| “What do the return policy and customer service policy say about refunds and disputes?” | DOC-POL-001 `0.5094 / 0.6444`; DOC-POL-003 rank 4 at `0.3751 / 0.5234`; only return source selected | DOC-POL-001 `0.5545 / 0.6824`; DOC-POL-003 candidate `0.3534 / 0.4756`; both selected | Both named source documents represented; verified |
| “What does the shipping policy say, and what happens when a delivery is delayed?” | Shipping DOC-POL-002 `0.4635 / 0.5742`; exception DOC-OPS-004 `0.4311 / 0.4725`; no excerpt selected | DOC-POL-002 `0.6234 / 0.7518`; DOC-OPS-004 `0.5191 / 0.5582`; both selected | Both requested aspects covered; verified |
| “What strategy was recommended for campaign CMP-021?” | The pre-tuning capture found the campaign postmortem among candidates; it did not demonstrate supported strategy text | DOC-MKT-024-001 `0.6963 / 1.4811` was nearest, but returned chunks were title/metadata/heading only | No substantive recommendation excerpt; honest insufficient answer, unverified |
| “What is the return policy for interplanetary purchases?” | Nearest policy chunks included DOC-POL-002 `0.4713 / 0.5803` and DOC-POL-001 `0.405 / 0.5800`; no answer selected | Similarity remains above the floor, but requested unsupported wording is not evidenced | No claim produced; unverified |

## End-to-end evaluation matrix

| Question | Expected route / evidence | Actual route, evidence and key result | Verification | Result |
|---|---|---|---|---|
| How many customers are in the database? | SQL; total count | SQL; 10,000 | Pass | Pass |
| What are the top selling products by quantity sold? | SQL; descending units | SQL; PureGlow Yoga Series 0622 leads at 187 units | Pass | Pass |
| What are the top selling products by revenue? | SQL; descending revenue | SQL; GreenBasket Audio Series 0057 leads at ₹16,606,653.87 | Pass | Pass |
| What was the performance of campaign CMP-021? | SQL; campaign metrics | SQL; spend ₹1,840,000, revenue ₹5,270,000, 3,812 conversions, 47,919 clicks | Pass | Pass |
| What is the return rate? | SQL; return and order counts/rate | SQL; 3,585 returns / 50,000 orders = 7.17% | Pass | Pass |
| What are the return reasons? | SQL; grouped reasons | SQL; grouped counts returned, beginning with Quality Issue 639 | Pass | Pass |
| What is the NovaMart return and refund policy? | RAG; return policy | RAG; DOC-POL-001, 30-calendar-day general window | Pass | Pass |
| How long after buying something can a customer send it back for a refund? | RAG; paraphrase of return window | RAG; DOC-POL-001, same 30-calendar-day window | Pass | Pass |
| What do the return policy and customer service policy say about refunds and disputes? | RAG; DOC-POL-001 and DOC-POL-003 | Both sources selected and shown | Pass; both facets represented | Pass |
| What does the return policy say, and how many returns were recorded? | Hybrid; SQL count plus DOC-POL-001 | BOTH; 3,585 returns and return-policy evidence | Pass | Pass |
| What does the shipping policy say, and what happens when a delivery is delayed? | RAG; DOC-POL-002 and DOC-OPS-004 | Both source documents selected; shipping dates are shipment-specific and material exceptions escalated | Pass | Pass |
| How long does shipping take, and what happens if delivery is delayed? | RAG; duration plus exception guidance | Both documents cited; answer explicitly says a fixed general duration is absent | Unverified because duration evidence is absent | Pass for honest qualification |
| What were the results of campaign CMP-021 and what strategy was recommended? | BOTH; SQL metrics plus recommendation source | BOTH; SQL metrics shown, but no substantive recommendation excerpt selected | Unverified; requested campaign-recommendation facet is missing | Limitation exposed, no unsupported claim |
| What strategy was recommended for campaign CMP-021? | RAG; campaign-specific recommendation | RAG; no substantive supporting excerpt selected | Unverified | Limitation exposed |
| Can customers return lunar purchases for a refund? | RAG; only answer if source supports eligibility | RAG; insufficient-evidence response, no source cited | Unverified | Pass for abstention |
| What is the return policy for interplanetary purchases? | RAG; unsupported premise should not be inferred | RAG; insufficient-evidence response, no source cited | Unverified | Pass for abstention |
| Only policy documents: what does the return policy say? | RAG, metadata filter POLICIES | RAG; DOC-POL-001 selected | Pass | Pass |

## Coverage and remaining limitations

- Multi-document coverage is explicit: return + customer service uses DOC-POL-001
  and DOC-POL-003; shipping + delivery exceptions uses DOC-POL-002 and
  DOC-OPS-004. Missing facets now prevent a verified status.
- Campaign recommendation evidence is not available in the retrieved
  substantive excerpts for CMP-021. The index returned title/metadata/header
  chunks for DOC-MKT-024; the system abstains instead of presenting SQL metrics
  as a recommendation.
- The corpus does not provide a general fixed shipping duration. The answer
  preserves the shipment-specific policy wording and marks the duration aspect
  unverified.
- `pytest` is not installed in the existing backend environment. No package was
  installed. Syntax compilation, focused in-process verification assertions,
  and the Angular-proxy matrix were run instead.
