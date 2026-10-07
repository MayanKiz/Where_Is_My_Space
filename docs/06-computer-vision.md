# Computer Vision Pipeline

## Goal

Convert an authorized visual feed into reliable occupancy observations without requiring person identity.

## Pipeline

```text
Video Frame
   ↓
Pre-processing
   ↓
Person Detection
   ↓
Tracking / Temporal Association
   ↓
Region-of-Interest Mapping
   ↓
Occupancy Decision
   ↓
Confidence + Timestamp
```

## Initial stack

- Python
- OpenCV
- YOLO
- ByteTrack or another lightweight tracker when needed

## Detection

The first prototype focuses on person detection.

The model should provide:

- Bounding box
- Class
- Confidence
- Frame timestamp

## ROI mapping

A physical area is represented by configured polygons or regions.

Example:

```text
Zone A
+----------------+
| A1 | A2 | A3  |
|----|----|-----|
| A4 | A5 | A6  |
+----------------+
```

The system maps detections to the configured zones.

## Temporal validation

A single frame should not immediately change availability.

Use multiple observations over time to reduce false transitions caused by:

- Occlusion
- Brief movement
- Detection noise
- Lighting changes

## Privacy

Identity recognition is not required for the core availability use case.
