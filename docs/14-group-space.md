# Group Space Discovery

## Problem

Finding one free space is different from finding several spaces together.

## Representation

Model configured spaces as a graph.

Example:

```text
A1 —— A2 —— A3 —— A4
|      |      |      |
B1 —— B2 —— B3 —— B4
```

Each node represents a space/seat and each edge represents an allowed adjacency relationship.

## Query

User:

> Find 4 available spaces together.

## Algorithm

1. Get the current availability state.
2. Remove occupied/unknown nodes.
3. Build connected components or candidate adjacent groups.
4. Find groups meeting the requested size.
5. Rank candidates using distance, crowd level, and facilities.
6. Return the best valid options.

## Why deterministic logic?

The LLM should not decide whether four spaces are physically connected.

That relationship is a property of the configured environment.

## Future enhancements

- Different adjacency definitions
- Table-based groups
- Accessibility constraints
- Quiet-zone preference
- Reserved spaces
