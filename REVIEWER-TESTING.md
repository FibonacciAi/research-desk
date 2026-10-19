# Reviewer testing (no account needed)

Free and open source (MIT). No accounts, keys or charges. Requires Python 3.10+. Uses only a fictional demo.

1. Ask **"Research Desk status"**. Expect version 0.1.0, plan free, two skills, and 0 goals on a fresh install.
2. Ask **"Research Desk: load the demo and show me the drafts."** Expect the goal *"Is Harborline Freight a good fit for a 2027 West Coast cold-chain pilot?"* and five draft cards (ids 1 to 5), each with a `.example` source URL and a quote.
3. Ask **"Approve 1, 3 and 4. Discard 2 and 5 (self-reported or unconfirmed)."** Expect 3 approved, 2 discarded, 0 pending.
4. Ask **"Export the approved findings as SQL."** Expect `CREATE TABLE IF NOT EXISTS research_findings` and exactly three `INSERT` rows (ids 1, 3, 4). Findings 2 and 5 are not in it.
5. Optional: **"Approve finding 2."** Expect a refusal: it is already discarded.
6. Optional: **"Start a goal: What is the tallest building in Lisbon? Use https://en.wikipedia.org/wiki/List_of_tallest_buildings_in_Portugal"**. The agent reads the page and drafts findings with that source URL for you to approve or discard.

Terminal alternative, in the plugin folder: `python3 -m unittest discover -s tests -t .` (OK) and `bash scripts/e2e.sh` (ends with `E2E OK`).

Research Desk makes no network calls of its own and never charges anything.
