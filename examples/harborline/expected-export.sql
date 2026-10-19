-- Research Desk export: 3 approved finding(s). Discarded and pending drafts are not included.
CREATE TABLE IF NOT EXISTS research_findings (
  id INTEGER NOT NULL,
  goal_id INTEGER,
  goal TEXT,
  claim TEXT NOT NULL,
  source_url TEXT NOT NULL,
  quote TEXT,
  note TEXT,
  approved_at TEXT
);
INSERT INTO research_findings (id, goal_id, goal, claim, source_url, quote, note, approved_at) VALUES (1, 1, 'Is Harborline Freight a good fit for a 2027 West Coast cold-chain pilot?', 'Harborline Freight operates 14 refrigerated cross-dock sites on the US West Coast.', 'https://harborline.example/about/network', 'Our network includes 14 temperature-controlled cross-docks from San Diego to Seattle.', '', '2026-10-19T00:25:27Z');
INSERT INTO research_findings (id, goal_id, goal, claim, source_url, quote, note, approved_at) VALUES (3, 1, 'Is Harborline Freight a good fit for a 2027 West Coast cold-chain pilot?', 'An industry newsletter puts Harborline''s refrigerated on-time rate closer to 94%.', 'https://coldchain-weekly.example/2026/03/carrier-scorecard', 'Harborline Freight: 94.1% on-time, reefer segment, trailing twelve months.', '', '2026-10-19T00:25:27Z');
INSERT INTO research_findings (id, goal_id, goal, claim, source_url, quote, note, approved_at) VALUES (4, 1, 'Is Harborline Freight a good fit for a 2027 West Coast cold-chain pilot?', 'Harborline added real-time temperature telemetry to its whole reefer fleet in 2026.', 'https://harborline.example/news/2026-telemetry', 'Every reefer trailer now streams temperature readings every 60 seconds.', '', '2026-10-19T00:25:27Z');
