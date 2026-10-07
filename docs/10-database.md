# Database Architecture

## Core tables

### zones

Stores physical spaces.

Fields:

- id
- name
- building
- floor
- capacity
- status
- facilities
- created_at

### cameras

Stores authorized camera configuration.

Fields:

- id
- name
- location
- health_status
- covered_zones
- created_at

### occupancy

Stores current or recent occupancy metadata.

Fields:

- id
- zone_id
- occupied
- available
- occupancy_rate
- crowd_level
- confidence
- observed_at

### space_events

Stores meaningful state changes.

Fields:

- id
- zone_id
- event_type
- previous_state
- new_state
- observed_at

### facilities

Stores capabilities such as:

- Charging
- Wi-Fi
- Air conditioning
- Accessibility
- Quiet zone

## Relationships

```text
cameras ───< zones
zones ─────< occupancy
zones ─────< space_events
zones ─────< facilities
```

## Realtime

The current occupancy state should be available to the frontend through a realtime mechanism such as Supabase Realtime or an equivalent event layer.

## Principle

The database should represent **space intelligence**, not become a repository for unnecessary raw video.
