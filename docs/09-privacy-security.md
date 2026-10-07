# Privacy & Security

## Privacy principle

> **Process what is necessary, retain what is necessary, and expose what is useful.**

## Preferred data flow

```text
Authorized Camera
      ↓
Local / Edge Inference
      ↓
Occupancy Metadata
      ↓
Secure Backend
      ↓
User Interface
```

Raw continuous footage should not be sent to the cloud merely to calculate availability.

## Identity

The core product does not require:

- Face recognition
- Name identification
- Personal identity tracking

## Cloud data

Potential stored metadata:

- Zone ID
- Occupancy state
- Capacity
- Confidence
- Timestamp
- Camera health
- Space facilities
- Aggregated utilization

## Security controls

- Authenticated APIs
- Role-based access
- Secure secrets
- Encrypted transport
- Database access policies
- Audit logging
- Minimal data retention
- Camera credentials isolated from frontend code

## Camera access

Camera feeds must only be connected with explicit authorization from the infrastructure owner.

WIMS should not encourage bypassing authentication or accessing cameras without permission.

## Data retention

Retention should be configurable and aligned with the institution's policies and applicable privacy requirements.

## Trust

The system should clearly communicate when information is stale, uncertain, or unavailable.
