# System Architecture

## High-level architecture

```text
Authorized Camera / Video Feed
            |
            v
      Edge Processing
            |
            v
   Computer Vision Model
            |
            v
     Occupancy Engine
            |
            v
   Structured Metadata
            |
            v
       FastAPI Backend
            |
            +------> PostgreSQL / Supabase
            |
            +------> Realtime Events
            |
            v
     WIMS Web Application
            |
            v
      User Recommendations
```

## Architectural principles

### Edge-first processing
Visual inference should happen as close to the camera as practical.

### Metadata over footage
The cloud should receive only the information required for the product.

### Configuration over hardcoding
Zones, capacity, camera mapping, and facilities should be configurable.

### Deterministic availability
Availability and occupancy calculations should come from explicit system logic.

### AI where it adds value
LLMs should interpret user intent and explain results, not invent occupancy data.

## Main components

1. Camera adapter
2. Edge inference service
3. Occupancy engine
4. API service
5. Database
6. Realtime event layer
7. Recommendation engine
8. Web application
9. Notification service

## Failure philosophy

A camera failure should produce an explicit unknown/stale state rather than false availability.
