"""Sugiyama-inspired layered placement engine for PCB schematics.

Adapted from Dagre/ELK concepts with schematic-specific constraints:
- Signal flow direction (inputs → IC → outputs)
- Power/ground rail anchoring to edges
- Grid-aligned placement
- Component size-aware spacing
"""

from __future__ import annotations
from typing import Dict, List, Tuple
from collections import defaultdict
from .netlist import Netlist, Component

# Grid and spacing constants (mm)
GRID = 2.54              # 100 mil
COMPONENT_PAD_Y = 12.0   # vertical padding between components
COLUMN_PAD = 30.0        # horizontal padding between columns

# Default column X positions
DEFAULT_COLUMNS = {
    0: GRID * 5,     # Power/GND rail (left)
    1: GRID * 25,    # Inputs / decoupling
    2: GRID * 55,    # Main IC (center)
    3: GRID * 85,    # Outputs / RF
    4: GRID * 105,   # Power rail (right)
}


class SugiyamaPlacer:
    """Assign layers and coordinates to components."""

    def __init__(
        self,
        netlist: Netlist,
        grid: float = GRID,
        component_pad_y: float = COMPONENT_PAD_Y,
        column_pad: float = COLUMN_PAD,
        rankdir: str = "LR",  # "LR" = left-to-right signal flow
    ):
        self.nl = netlist
        self.grid = grid
        self.pad_y = component_pad_y
        self.pad_x = column_pad
        self.rankdir = rankdir

    # ----- Phase 1: Layer assignment -----

    def assign_layers(self) -> Dict[str, int]:
        """Assign each component to a signal-flow layer (column index)."""
        adj = self.nl.adjacency()
        layers: Dict[str, int] = {}

        for comp in self.nl.components:
            if comp.symbol.is_power:
                layers[comp.ref] = 0 if comp.symbol.value == "GND" else 4
            elif comp.ref.startswith("U") or comp.ref.startswith("IC"):
                layers[comp.ref] = 2  # ICs in center
            elif comp.symbol.lib_id.startswith("Device:X"):
                layers[comp.ref] = 1  # crystals on left
            else:
                layers[comp.ref] = 1  # default: input side

        # Overrides: components only connected to IC right-side pins → column 3
        for comp in self.nl.components:
            if comp.ref in layers and layers[comp.ref] == 1:
                connected = adj.get(comp.ref, set())
                if any(c.startswith("RF") or c.startswith("ANT")
                       for c in connected):
                    layers[comp.ref] = 3

        return layers

    # ----- Phase 2: Within-column ordering -----

    def order_columns(self, layers: Dict[str, int]) -> Dict[str, int]:
        """Order components within each column (minimize crossings)."""
        adj = self.nl.adjacency()

        # Group by layer
        by_layer: Dict[int, List[Component]] = defaultdict(list)
        for comp in self.nl.components:
            by_layer[layers.get(comp.ref, 2)].append(comp)

        # Barycenter heuristic: sort by average layer of neighbors
        ordering: Dict[str, int] = {}
        for layer_idx, comps in by_layer.items():
            barycenters = {}
            for comp in comps:
                neighbors = adj.get(comp.ref, set())
                if not neighbors:
                    barycenters[comp.ref] = 0.0
                else:
                    avg = sum(layers.get(n, 2) for n in neighbors) / len(neighbors)
                    barycenters[comp.ref] = avg

            sorted_comps = sorted(comps, key=lambda c: (barycenters[c.ref], c.ref))
            for i, comp in enumerate(sorted_comps):
                ordering[comp.ref] = i
                comp.layer = layer_idx
                comp.order = i

        return ordering

    # ----- Phase 3: Coordinate assignment -----

    def assign_coordinates(
        self, layers: Dict[str, int], ordering: Dict[str, int],
        columns: Dict[int, float] | None = None,
    ) -> None:
        """Assign exact (x, y) coordinates to every component."""
        if columns is None:
            columns = DEFAULT_COLUMNS

        # Group by layer
        by_layer: Dict[int, List[Component]] = defaultdict(list)
        for comp in self.nl.components:
            by_layer[layers.get(comp.ref, 2)].append(comp)

        for layer_idx, comps in by_layer.items():
            x = columns.get(layer_idx, self.grid * (10 + layer_idx * 20))

            # Sort by within-layer order
            comps.sort(key=lambda c: ordering.get(c.ref, 0))

            # Place main IC first (centered vertically), then others
            main_ic = None
            others = []
            for c in comps:
                if c.ref.startswith("U") or c.ref.startswith("IC"):
                    main_ic = c
                else:
                    others.append(c)

            if main_ic:
                # Rough center — will be refined below
                main_ic.x = x
                main_ic.y = self.grid * 65

            # Place others vertically
            start_y = self.grid * 20
            for i, comp in enumerate(others):
                comp.x = x
                comp.y = start_y + i * (self.pad_y + comp.symbol.height)

        # Refine: pull passives close to their IC pin connections
        self._refine_passive_placement(layers)

    def _refine_passive_placement(self, layers: Dict[str, int]) -> None:
        """Move passive components closer to the IC pins they connect to."""
        adj = self.nl.adjacency()
        pin_to_comp: Dict[Tuple[str, str], Component] = {}
        for comp in self.nl.components:
            for i, pin in enumerate(comp.symbol.pins):
                pin_to_comp[(comp.ref, pin.number)] = comp

        # For each net, try to align passives with their IC pin
        for net in self.nl.nets:
            # Find the IC in this net
            ic_refs = [r for r, _ in net.connections
                       if r.startswith("U") or r.startswith("IC")]
            if not ic_refs:
                continue
            ic_ref = ic_refs[0]
            ic_comp = self.nl.get_component(ic_ref)
            if not ic_comp:
                continue

            ic_pin_nums = [p for r, p in net.connections if r == ic_ref]
            if not ic_pin_nums:
                continue

            # Get the IC pin's Y coordinate
            ic_pin_num = ic_pin_nums[0]
            ic_pin_idx = None
            for i, pin in enumerate(ic_comp.symbol.pins):
                if pin.number == ic_pin_num:
                    ic_pin_idx = i
                    break
            if ic_pin_idx is None:
                continue

            _, ic_pin_y = ic_comp.symbol.pin_position(ic_pin_idx)
            target_y = ic_comp.y + ic_pin_y

            # Move connected passives to this Y
            for ref, _ in net.connections:
                if ref == ic_ref:
                    continue
                comp = self.nl.get_component(ref)
                if comp and comp.layer != ic_comp.layer:
                    comp.y = target_y

    # ----- Full pipeline -----

    def run(self, columns: Dict[int, float] | None = None):
        """Execute the full placement pipeline."""
        layers = self.assign_layers()
        ordering = self.order_columns(layers)
        self.assign_coordinates(layers, ordering, columns)
        return layers, ordering
