# Occupancy Engine

## Purpose

Translate computer-vision observations into stable availability states.

## Zone states

- AVAILABLE
- OCCUPIED
- UNKNOWN

## Example metadata

```json
{
  "zone_id": "SA-A01",
  "zone": "Study Area A",
  "capacity": 30,
  "occupied": 18,
  "available": 12,
  "occupancy_rate": 60,
  "crowd_level": "moderate",
  "confidence": 0.94,
  "timestamp": "2026-10-08T10:32:15+05:30"
}
```

## Occupancy rate

```text
occupancy_rate = occupied / capacity × 100
```

## Crowd classification

An initial configurable model can classify:

- 0–30%: Low
- 31–70%: Moderate
- 71–90%: High
- 91–100%: Very High

Thresholds should remain configurable because different environments have different meanings of “crowded.”

## State transitions

Use temporal smoothing before changing state.

Example:

```text
AVAILABLE
   |
   | sustained occupancy
   v
OCCUPIED

OCCUPIED
   |
   | sustained availability
   v
AVAILABLE
```

If the camera or inference pipeline becomes unreliable:

```text
ANY STATE → UNKNOWN
```

## Rule

The system must prefer **unknown** over confidently reporting incorrect availability.
