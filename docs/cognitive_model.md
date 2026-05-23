# Schematic Layout — Cognitive Model & Principles

## The 11 Principles (Hierarchical, Not Additive)

Derived from independent cognitive analysis of human schematic designers.

| Rank | Principle | Weight | Encoding |
|------|-----------|--------|----------|
| 1 | **Ground Points Down** | ∞ | GND rotation = 0°, pin at top |
| 2 | **Voltage Falls Down** | ∞ | V(higher) > V(lower) in Y |
| 3 | **Signal Flows Left→Right** | critical | Inputs left, outputs right |
| 4 | **Functional Proximity** | strong | Related components clustered |
| 5 | **Collinear Series Paths** | strong | Series chain on same axis |
| 6 | **Wire Orthogonality** | strong | Only 0°/90°, no diagonals |
| 7 | **Junction Dot Clarity** | required | Dot at every 3+ wire junction |
| 8 | **Wire Minimalism** | moderate | Fewest bends, shortest path |
| 9 | **Label Proximity** | moderate | Label near component, not on wire |
| 10 | **Symmetry** | weak | Mirror identical subcircuits |
| 11 | **Whitespace** | weak | Breathing room between groups |

## Three-Phase Reading Model

1. **Preattentive Gestalt** (100ms): Pattern recognition — ground at bottom, power at top
2. **Template Matching** (500ms-2s): Recognize topology — "this is a voltage divider"
3. **Narrative Construction** (2-10s): Trace signal flow, understand function

## Why Our Placer Fails

| Principle | Our violation |
|-----------|--------------|
| #2 Voltage Falls Down | BAT at same Y as R1, GND below — no gradient |
| #5 Collinear Series | R1 and R2 scattered horizontally |
| #6 Orthogonality | Diagonal routing everywhere |
| #7 Junction Dots | Missing at multi-drop nets |
| #9 Label Proximity | Labels at wire midpoints, not near components |

## The Meta-Principle

**Spatial position encodes electrical meaning.**
Humans optimize for readability (time-to-understand), not wire length.
The cost function must be HIERARCHICAL — violating principle #1 is infinitely
worse than violating principle #8. A longer wire preserving voltage gradient
beats a shorter wire inverting it.

## Ideal Voltage Divider

```
   VCC (BAT+)        ← top
     │
    R1               ← middle-top
     ├── VOUT         ← junction with dot
    R2               ← middle-bottom
     │
    GND              ← bottom
```

Vertical stack, centered on one axis. Pure orthogonal wires.
Zero diagonals. Zero overlaps. Instant recognition.
