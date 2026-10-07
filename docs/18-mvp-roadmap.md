# MVP Roadmap

## Stage 0 — Product foundation

- Product definition
- User validation
- Architecture
- Privacy model
- Data model

## Stage 1 — Computer vision proof

Goal:

```text
Video
 ↓
YOLO
 ↓
Person detection
 ↓
Zone mapping
 ↓
Occupancy JSON
```

Success criterion:

A controlled video can produce stable occupancy information.

## Stage 2 — Backend

Add:

- FastAPI
- PostgreSQL / Supabase
- Occupancy API
- Realtime updates
- Health monitoring

## Stage 3 — Web product

Build:

- Live dashboard
- Space cards
- Map
- Availability states
- Mobile experience

## Stage 4 — Intelligence

Add:

- Group-space discovery
- Recommendation engine
- Natural-language search
- Notifications

## Stage 5 — Scale

Add:

- Multiple cameras
- Camera calibration
- Analytics
- Reliability monitoring
- Edge deployment
- Organization-level administration

## MVP definition

The first complete demo is:

> **One authorized camera/video source → reliable occupancy detection → API → live WIMS dashboard.**
