"""Generate the synthetic factory dataset. Run ONCE, commit the output.

Volume (spec 6.0): 3 lines x 4 machines = 12 machines, 14 days ending
"yesterday", 2 shifts/day, ~340 production runs, ~120 downtime events,
~90 quality events.

The three planted patterns (spec 6.1) are the whole point. Uniform random
data gives root-cause analysis nothing to find and the model produces
generic filler:

  1. Recurring CHANGEOVER overrun on one machine, concentrated on shift B.
  2. A quality defect spike beginning right after a specific changeover,
     so cause and effect must be correlated ACROSS two event tables.
  3. Silent cycle-time drift on one machine that depresses OEE without ever
     raising a downtime event.

Writes machines.json, production_runs.json, downtime_events.json and
quality_events.json into data/generated/.
"""

if __name__ == "__main__":
    raise SystemExit("Not implemented yet - built during the 0:00-0:45 contract slice.")
