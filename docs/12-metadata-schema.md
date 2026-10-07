# Occupancy Metadata Schema

## Canonical record

```json
{
  "zone_id": "SA-A01",
  "zone": "Study Area A",
  "building": "Central Academic Block",
  "floor": 2,
  "capacity": 30,
  "occupied": 18,
  "available": 12,
  "occupancy_rate": 60,
  "status": "PARTIALLY_OCCUPIED",
  "crowd_level": "Moderate",
  "group_spaces": {
    "available_2": 5,
    "available_3": 2,
    "available_4": 1
  },
  "facilities": {
    "charging": true,
    "wifi": true,
    "air_conditioning": true
  },
  "camera_id": "CAM-SA-01",
  "confidence": 0.94,
  "last_updated": "2026-10-08T10:32:15+05:30"
}
```

## Required fields

- zone_id
- capacity
- occupied
- available
- timestamp / last_updated

## Derived fields

- occupancy_rate
- crowd_level
- status

## Optional fields

- group-space availability
- facilities
- confidence
- camera health
- quality indicators

## Rule

The schema should remain independent of the specific camera vendor or computer-vision model.
