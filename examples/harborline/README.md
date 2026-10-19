# Harborline demo (fictional)

A made-up goal with five draft findings, for trying Research Desk without reading any real site.

- Goal: *Is Harborline Freight a good fit for a 2027 West Coast cold-chain pilot?*
- Findings 1, 2 and 4 cite the company's own pages; finding 3 conflicts with finding 2; finding 5 is an unconfirmed rumor.
- A sensible review: approve 1, 3 and 4, discard 2 (self-reported, contradicted) and 5 (rumor). Then export.

Everything here is invented. The `.example` domain is reserved and never resolves.

```bash
python3 bin/research-desk demo
python3 bin/research-desk list
python3 bin/research-desk approve 1 3 4
python3 bin/research-desk discard 2 5 --note "self-reported or unconfirmed"
python3 bin/research-desk export --out harborline.sql
```

Expected export: [`expected-export.sql`](expected-export.sql) shows the shape (timestamps will differ).
