# Answer verification evaluation matrix

Run date: 2026-11-14. End-to-end cases used the Angular `/api/ask` proxy.
The live matrix checks route, verification status, and key returned facts;
synthetic evidence cases exercise the verifier directly.

| ID | Question | Expected route and key evidence | Actual behavior | Result |
|---|---|---|---|---|
| SQL-01 | How many customers? | SQL; customer count from returned row | 10,000; SQL value matched row | PASS |
| SQL-01b | How many active customers? | SQL; status-filtered count | 8,550; returned row matched | PASS |
| SQL-01c | How many inactive customers? | SQL; statuses other than ACTIVE | 1,450 across DORMANT and CLOSED; answer states this interpretation | PASS |
| SQL-02 | What are the top-selling products by quantity? | SQL; descending `units_sold` | PureGlow Yoga Series 0622, 187; order checked against rows and SQL | PASS |
| SQL-03 | What are the top products by revenue? | SQL; descending `total_revenue` | GreenBasket Audio Series 0057, â‚¹16,606,653.87; ranking checked | PASS |
| SQL-04 | What is total sales revenue and average order value? | SQL; count, revenue, average from orders | 50,000 orders; â‚¹4,745,475,661.63 revenue; â‚¹94,909.51 AOV | PASS |
| SQL-05 | What were monthly sales in 2025? | SQL; calendar-year date bounds | 12 monthly rows; answer states â€œcalendar year 2025â€ | PASS |
| SQL-05b | What were sales in the last 30 days? | SQL; rolling trailing 30-day range | 0 orders; live maximum order date is 2026-08-31, before the query window; answer states rolling window | PASS |
| SQL-05c | Show monthly sales from 2025 through 2026. | SQL; inclusive calendar years, exclusive 2027 boundary | Returned 2025 and 2026 month rows; answer states both calendar years | PASS |
| SQL-06 | Which customer segment generated the most revenue? | SQL join; grouped customer/order revenue | Growth led with â‚¹1,328,034,411.55 | PASS |
| SQL-07 | Which campaigns had the best ROI? | SQL; descending `roi_percent` | CMP-012 led at 535.46%; SQL ordering and metric values checked | PASS |
| SQL-08 | How many support tickets by issue category? | SQL; grouped ticket counts | Issue groups and counts returned; claims matched rows | PASS |
| SQL-09 | What is payment volume by method? | SQL; payment count and amount grouped by method | Six methods returned; values matched rows | PASS |
| SQL-10 | How many shipments by carrier? | SQL; shipment counts and delays by carrier | Five carriers returned; values matched rows | PASS |
| SQL-11 | What are the results for campaign CMP-021? | SQL; exact campaign row | Spend â‚¹1,840,000; revenue â‚¹5,270,000; 3,812 conversions; 47,919 clicks | PASS |
| SQL-12 | What is the return rate? | SQL; returns divided by orders | 3,585 / 50,000 = 7.17%; values matched row | PASS |
| SQL-13 | What are the top return reasons? | SQL; reason counts in returned order | Quality Issue led with 639; values matched rows | PASS |
| RAG-01 | According to the return policy, what is the refund timeline? | RAG; policy excerpt and actual source reference | 30-calendar-day general window with conditions; source `DOC-POL-001` | PASS |
| RAG-02 | What is the return window for a damaged product? | RAG; policy excerpt | General 30-calendar-day window, subject to product-specific conditions; source `DOC-POL-001` | PASS |
| BOTH-01 | Explain the CMP-021 campaign performance and why it performed that way. | BOTH; SQL campaign metrics plus focused postmortem excerpt | SQL metrics and `Campaign Postmortem Cmp-021` (`DOC-MKT-024`) returned and matched evidence | PASS |
| AMB-01 | What were sales last year? | Clarify calendar year vs rolling 12 months | Asked which period; no result guessed | PASS |
| AMB-02 | Show customers by location. | Clarify city, state, or country | Asked which grouping; no default dimension guessed | PASS |
| AMB-03 | What are the top products? | Clarify quantity vs revenue ranking | Asked which metric; no ranking guessed | PASS |
| AMB-04 | What are the top campaigns? | Clarify ROI, revenue, spend, or conversions | Asked which metric; no ranking guessed | PASS |
| AMB-05 | Show product inventory by category. | Clarify product-level listing vs category totals | Asked which interpretation; did not present a product list as grouped totals | PASS |
| UNSUP-01 | How many customers by age? | Clarify; field exists but no supported template | Said age grouping is unsupported and offered supported groupings | PASS |
| UNSUP-02 | Orders where payment status is failed | Clarify unsupported filter | Stated the filter is unsupported and did not return a broader status summary as if filtered | PASS |
| INSUFF-01 | What does the policy say about interplanetary refunds? | RAG; insufficient evidence, no document source | Returned â€œnot enough substantive evidenceâ€; verification false | PASS |
| VERIFY-01 | Synthetic customer-count row says 12; answer says 120 | Reject SQL numeric claim | Verification rejected the mismatched answer | PASS |
| VERIFY-02 | Synthetic ranking rows are 2 then 9 units | Reject ranking order inconsistent with metric | Verification rejected the out-of-order ranking | PASS |
| VERIFY-03 | Synthetic refund excerpt does not promise a five-day guarantee | Reject unsupported RAG statement | Verification rejected the fabricated guarantee | PASS |
| VERIFY-04 | Synthetic answer cites a different document/chunk ID | Reject source mismatch | Verification rejected the non-retrieved source reference | PASS |
| VERIFY-05 | Two retrieved policy excerpts specify 30 vs 14 days | Keep both claims attributed and qualify disagreement | Both titled excerpts were shown with an unreconciled-differences note; source IDs matched | PASS |

The broader Angular regression run covered 45 questions across customer and
product groupings, inventory, sales and date trends, seller performance,
campaign ROI and channels, support tickets, payments, shipments, returns,
campaign lookup, RAG, hybrid routing, clarification, and insufficient evidence.
All 45 matched their expected route and verification outcome. The bounded
2025â€“2026 date-range question was additionally verified through the proxy,
for 48 successful end-to-end cases total.

Eight focused repository test functions were invoked directly and passed:
evidence-matched SQL, incorrect SQL numeric claim, incorrect ranking order,
unsupported RAG claim, mismatched source reference, unsupported question
aspect, ambiguity prompts, and conflicting attributed excerpts. The pytest
runner itself was unavailable in the project venv, so these were direct
function invocations rather than a pytest run.

