# Where Is My Space?

> **Find your space before you reach there.**

**Where Is My Space? (WIMS)** is an AI-powered spatial intelligence platform designed to help people discover available and suitable spaces in real time.

Instead of asking users to walk around and manually check different locations, WIMS turns authorized camera infrastructure into useful occupancy intelligence.

## Core idea

**Camera stream → Edge inference → Occupancy intelligence → Realtime API → Web app → User recommendations**

The platform is designed to work across campuses, study areas, offices, waiting areas, hospitals, co-working spaces, venues, and other capacity-based environments.

## What WIMS can provide

- Real-time availability
- Occupancy and crowd-level information
- Visual space maps
- Group-space discovery
- Less-crowded recommendations
- Availability notifications
- Space-utilization analytics
- Natural-language search and recommendations

## Privacy by design

WIMS does not require identity recognition to solve the availability problem. The preferred architecture processes visual data near the camera or on an authorized edge computer and sends only the required occupancy metadata to the backend.

**Raw video is not the product. Intelligence extracted from the video is.**

## Initial MVP

The first prototype will focus on one controlled area:

1. Receive an authorized video feed.
2. Detect people using computer vision.
3. Map detections to configured zones/spaces.
4. Calculate occupancy.
5. Expose the result through an API.
6. Display live availability in a web dashboard.

## Planned technology

- Python
- OpenCV
- YOLO
- FastAPI
- PostgreSQL / Supabase
- Next.js
- TypeScript
- Realtime APIs
- LLM-assisted natural-language interaction

## Repository

This repository contains the product documentation, system architecture, MVP specifications, and implementation roadmap for Where Is My Space?

**Status:** Early-stage prototype / product development.
