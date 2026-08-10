---
doc_id: SOP-008
title: Robotic Welding Quality - Porosity, Spatter and Undercut
revision: 2.6
department: Quality
---

# Purpose and scope

Weld defect diagnosis on the robotic welding cell M-31 (ASSEMBLY, CELL-1).
Covers WELD_POROSITY, SPATTER and UNDERCUT. Porosity is the highest-count
quality defect in the plant, so it gets the most detail here.

# WELD_POROSITY

Gas trapped in the solidified weld. Almost always a shielding problem.

Check in this order:

1. **Shielding gas flow.** Verify the regulator setting and the actual flow at
   the torch, not just the gauge. CN-3002 is 75/25 argon-CO2. A regulator
   that has drifted since the last service is the most common single cause.
2. **Gas leaks.** Inspect the line from the regulator to the torch. A cracked
   hose upstream shows up as intermittent porosity that follows no pattern.
3. **Draughts.** Open doors and fans near the cell will strip the shielding
   envelope off the puddle.
4. **Joint cleanliness.** Oil, rust or moisture on the joint boils into the
   weld pool. Degrease before welding.
5. **Wire condition.** RM-3001 ER70S-6 that has been left unspooled in humid
   air will introduce moisture. Check the spool storage.
6. **Contact tip and liner.** A worn tip causes erratic arc and inconsistent
   gas coverage. Replace at PM intervals, not on failure.

Parts welded since the last good inspection are suspect. Porosity is
internal; a visual pass does not clear it.

# SPATTER

Molten metal ejected from the arc.

1. Voltage too low for the wire feed speed. Check the parameter set against
   the part program.
2. Contact tip to work distance too long.
3. Wire feed inconsistency: check the liner for kinks and the drive roll
   tension.
4. Clean spatter from the nozzle and the seam-tracking optics after every
   occurrence. Spatter on the tracking sensor causes the torch to lose the
   joint mid-seam.

# UNDERCUT

Groove melted into the base metal alongside the weld, not filled.

1. Travel speed too high.
2. Excessive voltage or current for the joint.
3. Torch angle wrong, or the seam tracker following a mis-taught path.
4. Re-teach the joint after any fixture change.

# Escalation

Any porosity finding above ten parts in a shift stops the cell for a full
gas system check before further production.
