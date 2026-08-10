---
doc_id: SOP-003
title: CNC Tool Breakage Response and Insert Replacement
revision: 2.4
department: Machining
---

# Purpose and scope

Response to TOOL_BREAK events on M-21, M-22, M-23 and M-24, and the
inspection required before the machine returns to production.

# Immediate response

1. Feed hold, then cycle stop. Do not power off; losing position means
   re-establishing work offsets from scratch.
2. Retract the spindle clear of the part before opening the door.
3. Photograph the tool and the part in place before removing anything. The
   fracture pattern tells you whether this was wear, a feed error, or a crash.
4. Inspect the part for embedded fragments and secondary damage.

# Replacement

1. Pull the replacement from crib stock. Carbide milling inserts are TL-2003
   (CNMG 432). If crib stock is below two units, raise a replenishment call
   before fitting the last one.
2. Fit the insert or end mill, torque to spec, and re-measure the tool on the
   tool setter. Never copy the previous tool's offset.
3. Re-run the last completed operation on a scrap blank where cycle time
   allows.

# Root cause triage

Work through these in order before restarting:

- **Worn early**: check the coolant concentration and nozzle aim. Weak or
  misdirected coolant is the most frequent cause of premature wear.
- **Chipped insert**: look for interrupted cut conditions, hard spots in the
  billet, or a feed rate carried over from a different material.
- **Broken tap**: check hole depth and pecking parameters, and confirm the
  tapping fluid is being delivered.
- **Repeat break on the same tool station**: suspect a programming issue or a
  fixture that lets the part shift under load.

# Quality hold

Parts machined since the last good inspection are suspect. Quarantine the
run and inspect for DIM_OOT, BURR and TOOL_MARK before releasing. A tool
that degrades gradually can produce dozens of out-of-tolerance parts before
it finally breaks.
