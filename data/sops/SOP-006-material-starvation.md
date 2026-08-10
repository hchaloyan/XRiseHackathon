---
doc_id: SOP-006
title: Material Starvation Response and Line-Side Replenishment
revision: 2.0
department: Materials
---

# Purpose and scope

Response to MATERIAL_STARVE downtime and the replenishment rules that
prevent it. Starvation downtime is entirely avoidable and is measured
separately from equipment downtime for that reason.

# Immediate response

1. Identify the missing part number and the quantity needed to finish the run.
2. Raise a line-side call to materials with the machine ID and part number.
3. Put the machine in a controlled stop. Do not run the hopper dry on the
   moulding presses or the 3D printers; a dry run-out on M-34 means a failed
   build and a powder cleanout.
4. Log the event with the part number in the operator note.

# Line-side stock and reorder points

Each part carries a reorder point sized against daily usage. When on-hand
falls below the reorder point, replenishment is raised the same shift.

MOLDING line:

- RM-1001 Polypropylene resin, natural, 25kg bag
- RM-1002 ABS resin, black, 25kg bag
- RM-1003 Colorant masterbatch, grey
- CN-1004 Mold release agent, aerosol

MACHINING line:

- RM-2001 Aluminium bar stock 6061, 50mm
- RM-2002 Steel billet 1045, 75mm
- TL-2003 Carbide milling insert, CNMG 432
- CN-2004 Coolant concentrate, semi-synthetic

ASSEMBLY line:

- RM-3001 Weld wire ER70S-6, 0.9mm, 15kg spool
- CN-3002 Shielding gas, 75/25 argon-CO2
- HW-3003 Structural rivet, 6mm steel
- RM-3004 Nylon PA12 powder, additive grade
- RM-3005 ABS filament, 1.75mm, 5kg spool

# Drying and staging, MOLDING

Resin must be dried for the full cycle before use. Staging the next lot in
the dryer while the current lot runs is the standard practice; an empty
dryer hopper mid-run means the line stops for the drying time, not for the
delivery time.

# Kanban discipline

A missing kanban card is not a reason to skip replenishment. If the card is
missing, raise the call manually and flag it at handover. Recurring notes
about short deliveries with no card point at a card that has been lost from
the loop rather than a supply problem.

# Escalation

Two starvation events on the same part number in one week goes to the
materials planner to review the reorder point and daily usage figure.
