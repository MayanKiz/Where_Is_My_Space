# Product Requirements

## Core requirement

WIMS must transform occupancy observations into simple, actionable information for users and facility operators.

## Functional requirements

### Availability
- Show available and occupied capacity.
- Show the last update time.
- Support configurable zones.

### Occupancy
- Estimate occupancy for a zone or configured space.
- Calculate occupancy percentage.
- Assign a crowd level.

### Group discovery
- Find connected available spaces.
- Support queries such as “find four spaces together.”

### Recommendations
Rank available options using configurable signals such as:

- Availability
- Group fit
- Crowd level
- Distance
- Facilities
- User preferences

### Notifications
Notify users or operators when a relevant availability state changes.

### Analytics
Provide historical utilization metrics without requiring continuous raw-video storage.

## Non-functional requirements

- Privacy-conscious
- Low-latency updates
- Configurable
- Resilient to camera failures
- Secure
- Scalable
- Mobile-friendly

## MVP boundary

The MVP will not require:

- Face recognition
- Identity tracking
- Continuous cloud video storage
- Perfect multi-camera tracking
- Full autonomous facility management
