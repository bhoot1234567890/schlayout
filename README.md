# schlayout

> *"Any sufficiently advanced schematic placer is indistinguishable from a tired graduate student."*

A Python library that tries to do what every electrical engineer can do in their sleep: place components on a schematic so they don't look like garbage.

**It mostly fails. But it fails *scientifically*.**

---

## Why This Exists

You know that moment when KiCad imports a netlist and scatters 47 components across 12 pages like a toddler with LEGOs? And you spend the next hour dragging resistors around going "no, *you* go *there*, and *you* go next to the capacitor, and WHY IS THE GROUND SYMBOL AT THE TOP OF THE PAGE?"

We tried to automate that. Here's what we learned.

### The Psychology

Humans read schematics in three phases:

| Phase | Time | What happens |
|-------|------|-------------|
| **Preattentive Gestalt** | 100ms | *"Power at top, ground at bottom — this circuit is normal"* |
| **Template Matching** | 500ms-2s | *"Two resistors in series? That's a voltage divider."* |
| **Narrative Construction** | 2-10s | *"Signal enters here, gets divided, exits there."* |

If you violate phase 1 (ground pointing sideways, power at the bottom), the reader's brain rejects the schematic before they even consciously look at it. This is not a preference — this is how the visual cortex works.

Computers don't have a visual cortex. They have cost functions. And cost functions don't know that "ground points down" is infinitely more important than "wire length is minimal."

---

## The 11 Principles of Schematic Readability

Derived from cognitive research, transit map design, chemical structure layout, and staring at too many bad schematics:

| # | Principle | Weight | What happens if you violate it |
|---|-----------|--------|-------------------------------|
| 1 | **Ground Points Down** | ∞ | Reader's brain rejects the schematic in 100ms |
| 2 | **Voltage Falls Down** | ∞ | Reader must consciously invert their mental model |
| 3 | **Signal Flows Left→Right** | critical | Fights reading direction; slower tracing |
| 4 | **Functional Proximity** | strong | Related components scattered → can't group |
| 5 | **Collinear Series Paths** | strong | Visual scanning breaks; requires pathfinding |
| 6 | **Wire Orthogonality** | strong | Diagonals look sloppy; harder to trace |
| 7 | **Junction Dot Clarity** | required | "Wait, is that connected or not?" |
| 8 | **Wire Minimalism** | moderate | Extra bends are cognitive speed bumps |
| 9 | **Label Proximity** | moderate | "Which component does VOUT belong to?" |
| 10 | **Symmetry** | weak | Visual noise masks circuit structure |
| 11 | **Whitespace** | weak | Crowding causes confusion |

The key insight: **these are HIERARCHICAL, not additive.** Principle 1 is worth more than principles 8-11 combined. A longer wire preserving voltage gradient beats a shorter wire inverting it. Optimization algorithms fundamentally don't understand this.

---

## How We Tried to Solve It

### Attempt 1: Brute Force
Search every position and rotation. 64 million configurations for 3 components. Works great for ≤4 components, then the universe ends.

### Attempt 2: Force-Directed Physics
Attractive forces along nets, repulsive between overlaps. Components flew to page edges like scared insects. Added centering force. They huddled in the corner instead.

### Attempt 3: ELK / Sugiyama Layered Layout
The same algorithm that draws Mermaid diagrams. Spent a week researching. ELK explicitly mentions "circuit schematics" as a design target. Pin positions are first-class. It's the right tool. It requires a JVM or JS bridge. We sighed and moved on.

### Attempt 4: Simulated Annealing
Random swaps with temperature-based acceptance. The gold standard in VLSI placement. Works great for 10,000 standard cells. For a 3-component LED circuit, it produced layouts that looked like modern art.

### Attempt 5: Minimum Spanning Tree Routing
Connected closest pins first. Created elegant minimum-wire-length paths. Also created wires that passed directly through the middle of other components. The MST does not respect personal space.

### Attempt 6: Diagonal Routing
"Just draw straight lines between pins." The user suggested this. It worked surprisingly well. Then two wires crossed and KiCad said they were shorted. They weren't. KiCad was just being KiCad.

### Attempt 7: Cycle Breaking
Learned from graph theory: loops are cycles. Break cycles by removing low-weight edges. Identify power/ground return paths as low-weight. Convert cyclic netlist to tree. Place tree cleanly. This actually worked. The voltage divider became readable. Then we rotated the resistors 180° and everything got 38% shorter.

### Attempt 8: The Cognitive Model
Spawned independent agents to research how metro maps, chemical structures, transit diagrams, and human engineers handle layout. The answer across all domains: **cycles are the foundation, not the problem.** Place the structure first, grow everything else from it. Templates for known patterns. Polish with local optimization.

---

## What Actually Works

After all that, here's the pipeline that produces readable schematics:

```python
from schlayout import SymbolLibrary, BruteForcePlacer, NetDef, SchematicGenerator

# 1. Load real KiCad symbols
lib = SymbolLibrary()
bat = lib.load("Device", "Battery_Cell")
res = lib.load("Device", "R")

# 2. Search for optimal placement
placer = BruteForcePlacer(components, nets)
placed, score = placer.search()

# 3. Generate valid .kicad_sch
gen = SchematicGenerator("My Circuit")
gen.generate(placed, nets, "output.kicad_sch", symbol_lib=lib)
```

**For 3-4 components:** brute force over positions + rotations with loop-checker verification. Finds the global optimum.

**For larger circuits:** cognitive placer (voltage gradient + series chain detection + orthogonal routing) plus local optimization.

**The loop checker** (`loop_checker.py`): verifies no wire crossings, no wires through components, computes wire length, and tells you if the layout is clean.

---

## Installation

```bash
git clone https://github.com/nuclearkerosene/schlayout
cd schlayout
pip install -e .
```

Requires KiCad 7+ for symbol library access.

---

## The Loop Checker

The one genuinely useful module. Feed it a placement and it tells you if the wires tangle:

```python
from schlayout.loop_checker import check_loop

result = check_loop(wires, component_bboxes, pin_positions)
print(result['is_clean'])      # True if no crossings
print(result['total_length'])  # Total wire length
print(result['crossings'])     # List of crossing wire pairs
```

---

## Project Structure

```
schlayout/
├── symbols.py          # KiCad .kicad_sym parser
├── placer.py           # Brute-force search over positions + rotations
├── force_placer.py     # Force-directed with SA acceptance
├── cognitive_placer.py # Voltage gradient + series chain detection
├── cycle_placer.py     # Cycle breaker + tree layout
├── loop_checker.py     # Wire crossing detection + length optimization
├── generator.py        # .kicad_sch file writer
└── routing.py          # Manhattan + MST routing
```

---

## The 10 Test Circuits

| # | Circuit | Components | Topology |
|---|---------|-----------|----------|
| 1 | LED + Resistor | 3 | Loop |
| 2 | Voltage Divider | 4 | Loop with GND break |
| 3 | RC Low-Pass Filter | 4 | Tree |
| 4 | R-2R Ladder | 6 | Ladder |
| 5 | LC Tank | 4 | Parallel |
| 6 | Diode Clamp | 5 | Bridge |
| 7 | Dual LED | 6 | Star |
| 8 | Pi Filter | 6 | Ladder |
| 9 | Wheatstone Bridge | 6 | Bridge loop |
| 10 | Buck Converter | 7 | Mesh |

---

## What We Learned

1. **ERC passing ≠ good schematic.** Zero violations does not mean readable.
2. **Rotation is placement.** A 180° flip can reduce wire length by 38%.
3. **Diagonals are fine.** Orthogonality is a preference, not a law.
4. **Labels are the hardest problem.** Every single approach failed at label placement.
5. **Ground is a cycle-breaker.** Human schematics don't draw return wires — they use GND symbols.
6. **The cognitive model is hierarchical.** You can't optimize readability with additive cost functions.
7. **KiCad's file format has tabs.** This matters more than you'd think.
8. **`pin_world_position` needs Y-inversion.** We learned this the hard way. Multiple times.

---

## Contributing

If you understand why `self.y - py` is correct in `pin_world_position`, you're already qualified. If you don't, read the commit history and weep with us.

---

## License

MIT. Use it, break it, fix it, laugh at it.

---

*"The difference between a good schematic and a bad one is about 12 pixels and three hours of your life."*
