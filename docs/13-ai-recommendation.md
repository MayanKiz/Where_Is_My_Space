# AI Recommendation Layer

## Goal

Allow users to describe what they need naturally and receive a useful space recommendation.

## Example

User:

> “Find a quiet space for four people with charging.”

## Processing flow

```text
Natural Language Query
          ↓
Intent / Constraint Extraction
          ↓
Structured Search Constraints
          ↓
Availability Filter
          ↓
Deterministic Ranking
          ↓
Recommendation
          ↓
Natural Language Response
```

## Constraint examples

- Group size
- Maximum crowd level
- Required facilities
- Preferred building
- Preferred floor
- Distance
- Quietness

## Important architecture rule

The LLM should not invent live availability.

Live availability must come from trusted system data.

The LLM is responsible for:

- Understanding user intent
- Structuring constraints
- Explaining results
- Conversational interaction

The availability engine is responsible for:

- Filtering
- Ranking
- Current state
- Capacity

## Example ranking

```text
score =
  availability_fit
+ group_fit
+ facility_fit
+ crowd_preference
+ distance_preference
```

Weights should be configurable.
