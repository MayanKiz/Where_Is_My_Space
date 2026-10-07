# Multi-Camera Architecture

## Problem

Adding person counts from multiple cameras can double-count the same person when camera views overlap.

```text
Camera A → 12 people
Camera B → 10 people

Naive total = 22

Actual people may be only 15.
```

## MVP strategy

Start with authoritative camera-to-zone mapping.

Each zone has a designated source camera or controlled region.

This keeps the first version deterministic and testable.

## Future strategy

For larger environments, add:

- Camera calibration
- Overlap maps
- Cross-camera tracking
- Re-identification where justified
- Temporal association
- Global occupancy reconciliation

## Camera configuration

Each camera should have:

- Camera ID
- Stream endpoint reference
- Location
- Covered zones
- Orientation
- Calibration metadata
- Health status

## Failure handling

If a camera stops producing reliable observations:

- Mark affected zones as stale or unknown
- Record the failure event
- Do not silently report old values as live

## Design principle

Multi-camera intelligence should improve coverage without sacrificing correctness or privacy.
