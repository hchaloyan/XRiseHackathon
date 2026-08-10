---
doc_id: SOP-005
title: Sensor Fault Diagnosis and Recalibration
revision: 1.8
department: Maintenance
---

# Purpose and scope

Diagnosis of SENSOR_FAULT downtime across all lines. Sensor faults are
frequently nuisance trips, which makes them easy to clear and easy to
under-report. Every trip gets logged even when the fix takes two minutes.

# General approach

1. Read the fault code at the HMI and record it before clearing.
2. Check the obvious physical causes first: contamination on the lens or
   face, a loose connector, a cable rubbing on a moving member.
3. Clear and attempt a restart. If the same fault returns within one hour,
   stop treating it as a nuisance trip and escalate to maintenance.

# Mold-close proximity switch (M-11 to M-14)

Symptom: press will not confirm mold close, or confirms intermittently.

1. Inspect the target face for flash and moulding debris.
2. Verify the sensing gap against the value on the mold tag.
3. Reseat the switch and re-torque the lock nuts.
4. If the fault recurs, check toggle lubrication. A dry toggle changes the
   close position enough to drop the switch out of range.

# Cavity pressure transducer (M-11 to M-14)

Symptom: erratic readings, process monitoring alarms on good-looking parts.

1. Check the connector and cable routing for damage.
2. Compare the peak pressure trace against the reference for the part.
3. Do not adjust the process to chase a suspect transducer. Verify the sensor
   first, or you will be tuning against a bad signal.

# Tool-setter probe (M-21 to M-24)

Symptom: tool lengths misread, first article out of tolerance.

1. Clean the stylus and the reference surface. Coolant film alone will shift
   a reading.
2. Recalibrate against the master gauge.
3. Re-measure every tool in the current job before restarting.

# Chamber thermocouple (M-33, M-34)

Symptom: chamber temperature drifting, builds warping or lifting.

1. Verify the probe is seated and not resting against a wall.
2. Recalibrate against the reference probe.
3. A drifting chamber is a leading cause of BUILD_FAILURE; do not start a long
   build on an uncalibrated chamber.

# Seam-tracking sensor (M-31)

Symptom: torch wanders off the joint, weld quality falls away mid-seam.

1. Clean the optics. Spatter accumulation is the usual cause.
2. Re-teach the reference joint.
3. Inspect the preceding welds for UNDERCUT and MISALIGNMENT before releasing.

# Door interlock nuisance trips

Check the strike alignment and the door hinge for sag before replacing the
switch. Never bypass an interlock. A bypassed interlock is a stop-work issue.
