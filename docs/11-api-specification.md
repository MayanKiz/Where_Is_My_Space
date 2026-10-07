# API Specification

## Purpose

Provide a stable interface between computer-vision services, the data layer, recommendations, and the web application.

## Initial endpoints

### GET /api/health

Returns service health.

### GET /api/zones

Returns configured zones and their latest availability.

### GET /api/zones/{zone_id}

Returns detailed information for one zone.

### GET /api/occupancy

Returns current occupancy observations.

### GET /api/recommendations

Returns ranked spaces based on user constraints.

### GET /api/events

Returns recent meaningful occupancy events for authorized clients.

## Example zone response

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
  "crowd_level": "Moderate",
  "last_updated": "2026-10-08T10:32:15+05:30"
}
```

## API principles

- JSON responses
- Explicit error states
- Authentication for protected endpoints
- Pagination for historical data
- Versioning when breaking changes are introduced
- No camera credentials in API responses
