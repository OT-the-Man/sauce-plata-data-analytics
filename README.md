# Sauce Plata Data Analytics

Code/data workspace for this project. Full design, phase checklist, and progress log live in Obsidian:
`G:\My Drive\Second Brain AI\Business\Sauce Plata\Sauce Plata Data Analytics - Project Log.md`

Read that vault note first in any new session — it has the orientation block, the locked design (architecture, data flow, error handling), and current status. Update it at the end of each phase, not just this folder.

## What this project is

Analyzes Sauce Plata restaurant's real purchasing/sales data (Google Sheets today, photo-based ingestion going forward), builds a hosted auto-updating dashboard, then a RAG Q&A layer. Runs in parallel with the Ledgerra project (`../Ledgerra/`) as an equally real second track — not a replacement for it. POS system and a sellable SaaS product are deliberately separate, later projects, not part of this one.

## Phases

0. Setup — Google Sheets API access, Python environment, local Postgres
1. Historical backfill — pull Sales Malejor + Purchases Malejor into raw staging
2. Cleaning — food-only filter, item-name deduplication (fuzzy matching)
3. Load to Postgres — cleaned data into final canonical tables
4. Dashboard — live-querying dashboard (Power BI or custom)
5. Ongoing ingestion (build-phase) — photo/doc pasted in chat, decoded, cleaned, written to Postgres
6. Hosting — dashboard live on the portfolio domain
7. RAG Q&A layer — natural-language questions over the real data
8. Automate ingestion — replace chat-paste with a programmatic vision-LLM API call
