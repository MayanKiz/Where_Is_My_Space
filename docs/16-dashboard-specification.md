# Dashboard Specification

## User dashboard

### Header

- Where Is My Space? logo
- Location selector
- Search / AI assistant
- Profile

### Live overview

Show:

- Total available
- Total occupied
- Overall crowd level
- Last updated time

### Space cards

Each card should show:

- Space name
- Available capacity
- Occupancy percentage
- Crowd level
- Group availability
- Facilities
- Last update
- Confidence / freshness indicator where useful

## Example

```text
Study Area A

12 available / 30 capacity
60% occupied
Crowd: Moderate

4 connected spaces available

Charging  | Wi-Fi | AC

[View Space]
```

## Map view

A visual map should communicate availability through clear status indicators.

Avoid relying on color alone. Use:

- Labels
- Icons
- Text status
- Accessible contrast

## AI interaction

Example:

> Find me a quiet space for 3 people with charging.

The interface should show the interpreted requirements before presenting the recommendation where appropriate.

## Mobile-first

The primary experience should work comfortably on a phone because users are likely to search while moving around campus or a facility.
