---
doc_id: SOP-014
title: Case Packer Jam Clearing and Label Recovery
revision: 1.4
department: Packaging
---

# Purpose and scope

JAM, ROBOT_FAULT and packing defects on M-51 Automatic Case Packer, the
PACKAGING line. This is the last machine before despatch, so a defect here
reaches the customer whatever happened upstream.

# Safety first, every time

Stop the machine, wait for all motion to cease, and apply lockout before any
part of your body enters the cell. Never reach into the erector to clear a
carton with the machine live.

# Carton jam at the erector

1. Lock out, then remove the crushed carton and every piece of it.
2. Check the blank magazine is not empty or bridged (PK-5001).
3. Inspect the vacuum cups for wear. Cups that no longer seal drop a blank
   halfway and are the most common cause of a repeat jam.
4. Confirm the case size programme matches the blanks loaded.

# Label web break

1. Re-thread the web through the dancer and past the sensor.
2. Check the roll (PK-5003) is seated and not coned.
3. Run five labels to waste and confirm placement before restarting.
4. Any part packed since the last confirmed good label is suspect - see below.

# LABEL_MISPLACED, CARTON_CRUSH and MISSING_ITEM

Any jam or fault puts the cases packed since the last good cycle on hold.

- **LABEL_MISPLACED**: sensor position, web tension, or conveyor speed drift.
- **CARTON_CRUSH**: compression from a pallet stacked beyond its rating, or a
  damp blank. Check pallet pattern against PK-5002 loading.
- **MISSING_ITEM**: count sensor at the infeed, or a part-present eye blinded
  by dust. Verify with a full case on the scale before releasing the batch.
