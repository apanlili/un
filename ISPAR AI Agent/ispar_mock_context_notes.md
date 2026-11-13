# ISPAR AI Agent – Mock Context Notes

Companion to `ispar_mock_context.md` (EGDI / Kuwait example). Revised 10 Nov 2026; supersedes the uploaded mock.

## Decisions
- **Audience:** engineers. The mock is model-ready markdown with XML-tagged blocks; the final format depends on the infrastructure.
- **Page state:** index, country and ISO code. No year selector; KPI values are the latest published by the publisher.
- **KPI hierarchy:** OSI, TII and HCI are the top-level KPIs. The 15 series on the site are sub-level KPIs that make up those three. Wording can differ from the publisher's; KPI IDs link them.
- **No simulator adjustments:** the agent sees published values only, exactly as the user does.
- **Background:** covers the whole index and all its KPIs.
- **Data lineage:** per KPI.
- **Quality metadata:** methodology, the 1% relative threshold and one bucket per KPI. Raw comparison values are not shown.
- **Buckets A and B:** A = the publisher's value is confirmed by a separate source's most recent data point. B = confirmed by a separate source, but only for a prior year.
- **Subscription cap:** the publisher caps KPIs 271 and 274 at 120 per 100 inhabitants; the quality check uses the capped value.
- **Policy sources:** none yet. The block states that none exist. Future: tag sources to the KPIs they target.
- **Conversation history:** passed in as `{conversation_history}`.

## Changes from the uploaded mock
- **One KPI table:** the sub-level values, quality results and comparison sources are merged into one table keyed by KPI ID, instead of three tables repeating the same KPI names.
- **Units, direction and data year** now sit next to each value. Direction marks 1941 and 1942 as lower is better.
- **Top-level/sub-level mapping:** each top-level KPI lists its sub-level KPIs by ID, including affordability = 1941 + 1942.
- **Cap:** the 120 cap is noted in the TII background, the definitions of 271 and 274, the quality methodology and the units column.
- **Definitions:** KPI 281 now has the expected-years definition (it repeated the mean-years one). KPI 282 now specifies ages 25+. The dictionary definitions are shortened.
- **Canonical names:** one name per KPI ID. Fixed the typos "Iteracy", "Expected Year of Schooling", "E-participation", "technology140" and "B-".
- **Background cleanup:** removed the stray citation residue ("un", "google", "vikaspedia") and set the edition to 2024.
- **Quality metadata:** a methodology paragraph and bucket legend replace the raw comparison table. A and B are reworded to "confirmed by a separate source".
- **Index values:** added the EGDI level, a rating-class placeholder and "of 193" to ranks.
- **Lineage:** added the index version and a last-refresh placeholder. Source URLs are grouped by source.
- **Engineer notes** moved into an HTML comment at the top, so they aren't presented to the model as data.

## Still to supply ([TBC] in the mock)
- **Rating class** for 2022 and 2024.
- **TII score** with more decimal places (it shows 1.0 with rank 2).
- **ISPAR last-refresh date.**
- **Real comparison sources** for 1237–1241 and 1940, if UN DESA was a stand-in.

## Pending team confirmation
- **2022 vs 2024 values:** proposed behaviour is that the agent reports both values and the relative-measure caveat, but does not explain why they changed. In Kuwait's case the rank fell (61 → 66) while the score rose (0.75 → 0.78).
- **TII precision:** supply more decimal places, so the agent doesn't claim Kuwait has the top TII score.

## Open questions
- **Comparison source for the UN DESA sub-KPIs (1237–1241, 1940):** to check. The lineage lists the UN DESA Data Center, the publisher itself, as the comparison source. This may be a stand-in. Once the real sources are in, confirm every bucket A/B KPI was checked against a source separate from the publisher. If one wasn't, revisit its bucket (likely E or C).

## For the system prompt (not part of the context)
- Never compute or estimate index, top-level or sub-level KPI values; only report values supplied in context.
- Respect each KPI's direction when describing performance.
- Treat 120 for KPIs 271 and 274 as the publisher's cap, not the actual rate.
- Cite the source and data year when stating a value.
- When asked about reliability, use the KPI's quality bucket and say what it means.
- When comparing 2022 and 2024, state both values and that EGDI is relative; don't explain why values changed.
- If no vetted policy source exists, say so rather than suggesting reforms.
- Use only the context blocks; if something isn't there, say what is missing.

## Context size and structure
- **Size:** the full context for one page is about 3,000 tokens (about 11,000 characters). That is very small for Sonnet. Even with 8 turns of history, a request stays well under 10,000 tokens.
- **What limits quality here** is duplicated or conflicting information, not volume. Keep one table per fact, keyed by KPI ID.
- **Static vs dynamic:** `<index_background>` and `<quality_methodology>` are the same for every country on an index. Put them first and cache them (prompt caching) to cut cost and latency. Page values come next, then history, then the question last.
- **Rules go in the system prompt;** data goes in the tagged blocks. Don't mix them.
- **Where size will grow:** the policy library. When it exists, retrieve the few entries relevant to the question rather than passing the whole library.
- **Before launch:** test with a small fixed question set covering direction (1941/1942), the cap (271/274), buckets B and C, 2022 vs 2024, missing policy sources and out-of-scope questions.

## Resolved
- 120 cap (KPIs 271, 274): confirmed as a publisher cap (10 Nov 2026).
- 1% threshold: confirmed as relative (10 Nov 2026).
- Meaning of buckets A and B: confirmed (10 Nov 2026).
