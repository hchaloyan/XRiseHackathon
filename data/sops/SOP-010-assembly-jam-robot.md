---
doc_id: SOP-010
title: Assembly Station Jam Clearing and Robot Fault Recovery
revision: 2.1
department: Assembly
---

# Purpose and scope

JAM and ROBOT_FAULT recovery on the automated assembly and riveting station
M-32, the robotic welding cell M-31, and jam clearing on the moulding
presses. Also covers the assembly quality defects MISSING_FASTENER and
MISALIGNMENT.

# Safety first, every time

1. Stop the machine and wait for all motion to cease.
2. Apply lockout before any part of your body enters the cell envelope.
3. Never bypass an interlock to reach a jam. If the guard has to be open for
   the recovery, the machine is locked out, not jogged.

# Robot fault recovery (M-31, M-32)

Typical faults: gripper failed to confirm part, pick-and-place axis faulted
on overtravel.

1. Read and record the fault before clearing.
2. Clear the obstruction with the robot locked out.
3. Re-home the robot and confirm it reaches each reference position.
4. Run one cycle empty before reintroducing parts.
5. **Gripper failed to confirm**: check the part-present sensor, the gripper
   pads for wear, and the nest for a part left behind from the last cycle.
6. **Overtravel fault**: check for a part or fixture out of position rather
   than assuming an axis problem. Overtravel is usually a symptom.

# Jam clearing, moulding presses

- **Part stuck in cavity**: check ejector stroke and timing, inspect the
  cavity for damage or residue, and confirm mold release (CN-1004) is being
  applied per the part standard. Do not lever parts out with steel tools;
  cavity damage costs far more than the cycle.
- **Sprue hung up in the chute**: inspect the chute for burrs and check the
  sprue puller. A repeat sprue jam usually means the puller is worn.

# Rivet feed jams (M-32)

HW-3003 structural rivet, 6mm steel. Clear the feed track, check for a
deformed rivet at the throat, and confirm the hopper is above the minimum
level. An empty rivet hopper is MATERIAL_STARVE and belongs to SOP-006.

# MISSING_FASTENER and MISALIGNMENT

1. Any jam or robot fault puts the parts in process on hold.
2. Inspect every part produced since the last confirmed good cycle. A station
   that jammed once has very often placed a partial cycle's work.
3. MISSING_FASTENER: check the feed track, the presence sensor at the anvil,
   and the cycle-complete confirmation in the program.
4. MISALIGNMENT: check fixture clamp positions and locating pins for wear.
   After any fixture change, re-verify with a first-off part.

# Handling and SCRATCH defects

Finished parts go into dunnage, never stacked directly on the bench. Most
SCRATCH findings are handling damage after the process, not a machine fault.
