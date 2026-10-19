# Security

Research Desk stores data in one local SQLite file and makes no network calls. Exports are text you choose to run elsewhere. Table names are restricted to plain identifiers. Every value is escaped as a SQL string literal for the dialect you pick: doubled quotes for Postgres and SQLite, and backslash escapes for Snowflake and BigQuery.

Report a problem to heydimitri@mail.grokbot.com.
