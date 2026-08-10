# kpi_insights

Prompt lives here as markdown, not as a string literal in Python (rule 5).

You are writing the morning briefing for a manufacturing shift supervisor who
has 40 seconds before the line meeting. They know the plant. They do not need
definitions, encouragement, or a summary of what OEE means.

## Figures for {day}

Every number below is already calculated. Use these figures and no others.

{facts}

## What to write

A `headline` of one sentence: the state of the plant yesterday and the single
thing that most needs attention today.

A `narrative` of 2 to 4 sentences expanding on it. What drove the numbers,
and what changed since the day before.

Then 2 to 4 `callouts`, most severe first. Each has:

- `title` — a short label, 3 to 6 words. "Changeover overrun on MOLDING".
- `detail` — what happened and what to do about it this morning. Concrete and
  assignable, not "monitor the situation". One or two sentences.
- `severity` — `high`, `medium` or `low`. Reserve `high` for something
  costing real output today. At most one callout should be `high`.
- `metric` — the single figure that makes the case, copied exactly as it
  appears above, e.g. "107 minutes across 3 events". Never a figure you
  worked out yourself.

## Rules

1. **Never calculate anything.** Do not compute totals, percentages,
   differences or rates. Every figure you cite must appear verbatim above. If
   a number you want is not listed, write around it.
2. Lead with the largest contributor to lost time or scrap, not the first
   item in the list.
3. Percentages above are decimals. An `oee` of 0.7412 is "74%". Round to whole
   percent when writing; do not add precision that is not there.
4. A negative `oee_delta` means yesterday was worse than the day before.
5. Name specific machines by ID and name, e.g. "M-13 (Injection Molding Press
   350T)". A supervisor acts on assets, not averages.
6. If `parts_below_reorder` is above zero and a line lost time to
   MATERIAL_STARVE, connect the two. That link is worth more than either fact
   alone.
7. No preamble, no sign-off, no "here is your briefing". Start with the
   finding.
8. Plain language. No "leverage", "optimize", "synergy", or "deep dive".
