---
doc_id: SOP-009
title: Additive Manufacturing Build Failure Recovery
revision: 1.5
department: Additive
---

# Purpose and scope

Recovery from BUILD_FAILURE and build-related downtime on M-33 (FDM
large-format) and M-34 (SLS powder-bed), both in ASSEMBLY. Builds run long
and unattended, so a failure discovered late costs a full shift of machine
time.

# M-33 FDM: part lifted off the plate

The most common failure mode. The part detaches or curls away from the bed
mid-build.

1. Stop the build. Do not attempt to resume; layer registration is lost.
2. Remove the part and inspect the first layer for adhesion.
3. Re-level the build plate. Plate levelling is required after every plate
   swap and is the first thing to check on a lift-off.
4. Verify chamber temperature. A cold or drifting chamber causes differential
   cooling and curl. See SOP-005 for thermocouple recalibration.
5. Check the first-layer parameters: nozzle height, extrusion width, bed
   temperature.
6. Confirm the nozzle is clear. A partially blocked nozzle under-extrudes the
   first layer and guarantees poor adhesion.

# M-33 FDM: filament run-out

RM-3005 ABS filament, 1.75mm, 5kg spool. Estimate the filament required
against the spool remaining before starting a long build. A spool that runs
out mid-build is logged as MATERIAL_STARVE, not BUILD_FAILURE, and is
covered by SOP-006.

# M-34 SLS: recoater strike

The recoater blade contacts a curled part edge and aborts the build.

1. Stop and allow the chamber to cool before opening. Powder handling on a
   hot chamber is a burn risk.
2. Inspect the recoater blade for nicks. A nicked blade leaves streaks in
   every subsequent layer and must be replaced, not dressed.
3. Identify the curled part in the build layout. Curl at the edges usually
   means the part orientation or the thermal profile needs revisiting, not
   that the machine is at fault.
4. Sieve and reclaim the powder per the powder handling procedure. RM-3004
   nylon PA12, additive grade.

# Before restarting any build

- Chamber at temperature and stable, not still climbing
- Plate levelled and clean
- Sufficient feedstock staged for the full build plus margin
- Build layout reviewed if the previous failure was orientation-related

# Handover

A build running across a shift change is called out at handover with the
expected completion time and the feedstock remaining. Unannounced long
builds are how a failure sits undiscovered for six hours.
