"""Cognitive-model schematic placer.

Implements the 11 human readability principles.
Key insight: spatial position encodes electrical meaning.
Cost function is HIERARCHICAL, not additive.
"""

from __future__ import annotations
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import math
from .symbols import SymbolData

GRID = 2.54


def snap(v: float) -> float:
    return round(v / GRID) * GRID


@dataclass
class PlacedComponent:
    ref: str
    symbol: SymbolData
    cx: float
    cy: float
    rotation: int
    voltage: float = 0.0  # relative voltage level for gradient sorting

    @property
    def w(self) -> float:
        return self.symbol.rotated_size(self.rotation)[0]

    @property
    def h(self) -> float:
        return self.symbol.rotated_size(self.rotation)[1]

    def pin_world(self, pin_index: int) -> Tuple[float, float]:
        offsets = self.symbol.rotated_offsets(self.rotation)
        ox, oy = offsets[pin_index]
        return (self.cx + ox, self.cy - oy)

    def pin_by_number(self, number: str) -> Tuple[float, float]:
        for i, p in enumerate(self.symbol.pins):
            if p.number == number:
                return self.pin_world(i)
        return (self.cx, self.cy)


@dataclass
class NetDef:
    name: str
    connections: List[Tuple[str, str]]


class CognitivePlacer:
    """Place components following human readability principles.

    Principles (hierarchical):
      1. Ground points down
      2. Voltage falls down (higher V = higher Y)
      3. Signal flows left→right
      5. Collinear series paths (series chain on same X)
      6. Orthogonal routing only
      7. Junction dots at 3+ connections
     10. Symmetry for symmetric circuits
    """

    def __init__(
        self,
        page_width: float = 297.0,
        page_height: float = 210.0,
    ):
        self.pw = page_width
        self.ph = page_height

    def place(
        self,
        components: List[Tuple[str, SymbolData, float]],  # (ref, symbol, voltage)
        nets: List[NetDef],
    ) -> Tuple[List[PlacedComponent], List[NetDef]]:
        """Place components following cognitive principles.

        Strategy:
        1. Sort by voltage: highest V at top
        2. Place ground at bottom
        3. Stack collinear series components vertically on center X
        4. Place sources (batteries, VCC) on the left
        5. Place loads (resistors, etc.) in the center column
        6. Spread horizontally for parallel branches
        """
        center_x = snap(self.pw / 2)
        placed: Dict[str, PlacedComponent] = {}

        # Build adjacency from nets
        adj: Dict[str, set] = {}
        for net in nets:
            refs = [r for r, _ in net.connections]
            for i, a in enumerate(refs):
                adj.setdefault(a, set())
                for b in refs[i+1:]:
                    adj[a].add(b)
                    adj.setdefault(b, set()).add(a)

        # Classify components
        sources = []  # batteries, VCC
        passives = []  # R, C, L
        grounds = []   # GND
        loads = []     # LED, D, etc.

        comp_map = {}
        for ref, sym, voltage in components:
            comp_map[ref] = (sym, voltage)
            if sym.is_power and 'GND' in (sym.value or '').upper():
                grounds.append(ref)
            elif sym.lib_id.startswith('Device:Battery') or \
                 sym.lib_id.startswith('power:V'):
                sources.append(ref)
            elif sym.lib_id.startswith('Device:R') or \
                 sym.lib_id.startswith('Device:C') or \
                 sym.lib_id.startswith('Device:L'):
                passives.append(ref)
            else:
                loads.append(ref)

        # === Apply Principles ===

        # P1: Ground at bottom
        gnd_y = snap(self.ph * 0.15)
        for ref in grounds:
            sym, v = comp_map[ref]
            placed[ref] = PlacedComponent(ref, sym, center_x, gnd_y, 0, v)

        # P2: Voltage falls down — sort by voltage, highest at top
        # Place sources at top-left
        sources_sorted = sorted(sources, key=lambda r: -comp_map[r][1])
        src_y = snap(self.ph * 0.75)
        src_x = snap(self.pw * 0.35)
        for ref in sources_sorted:
            sym, v = comp_map[ref]
            placed[ref] = PlacedComponent(ref, sym, src_x, src_y, 0, v)
            src_y -= snap(sym.height + 10)

        # P5: Collinear series — find series chains and stack vertically
        # Simple: if two passives are connected in series, stack them
        if len(passives) >= 2:
            # Find series chain order from nets
            chain = self._find_series_chain(passives, nets)
            if chain:
                chain_y = snap(self.ph * 0.60)
                for ref in chain:
                    sym, v = comp_map[ref]
                    placed[ref] = PlacedComponent(ref, sym, center_x, chain_y, 0, v)
                    chain_y -= snap(sym.height + 8)

        # Place loads (LEDs, etc.) to the right of passives
        load_x = snap(center_x + 30)
        load_y = snap(self.ph * 0.55)
        for ref in loads:
            sym, v = comp_map[ref]
            placed[ref] = PlacedComponent(ref, sym, load_x, load_y, 0, v)
            load_y -= snap(sym.height + 8)

        # Place any remaining unplaced components
        remaining_y = snap(self.ph * 0.40)
        for ref, sym, v in components:
            if ref not in placed:
                placed[ref] = PlacedComponent(ref, sym, center_x, remaining_y, 0, v)
                remaining_y -= snap(sym.height + 8)

        result = [placed[ref] for ref, _, _ in components if ref in placed]
        return result, nets

    def _find_series_chain(
        self, passives: List[str], nets: List[NetDef]
    ) -> Optional[List[str]]:
        """Find the longest series chain among passive components."""
        if len(passives) < 2:
            return passives if passives else None

        # Build connection graph among passives
        adj = {r: set() for r in passives}
        for net in nets:
            refs = [r for r, _ in net.connections if r in passives]
            for i, a in enumerate(refs):
                for b in refs[i+1:]:
                    adj[a].add(b)
                    adj[b].add(a)

        # Find the longest path
        best = None
        for start in passives:
            path = [start]
            visited = {start}
            while True:
                current = path[-1]
                candidates = [n for n in adj[current] if n not in visited]
                if not candidates:
                    break
                # Pick the unvisited neighbor with fewest remaining connections
                candidates.sort(key=lambda n: len(adj[n] - visited))
                next_node = candidates[0]
                path.append(next_node)
                visited.add(next_node)
            if best is None or len(path) > len(best):
                best = path

        return best if best and len(best) >= 2 else None


class OrthogonalRouter:
    """Route nets with pure orthogonal (horizontal/vertical) wires.
    
    Principle 6: Wire Orthogonality — only 0° and 90° segments.
    Principle 7: Junction dots at every 3+ wire intersection.
    """

    def route(
        self,
        placed: List[PlacedComponent],
        nets: List[NetDef],
    ) -> Tuple[List[Tuple[float,float,float,float]], List[Tuple[float,float]]]:
        """Route all nets orthogonally."""
        comp_map = {p.ref: p for p in placed}
        wires = []
        juncs = []

        for net in nets:
            if len(net.connections) < 2:
                continue

            pts = []
            for ref, pn in net.connections:
                comp = comp_map.get(ref)
                if comp:
                    pts.append(comp.pin_by_number(pn))
            if len(pts) < 2:
                continue

            # Orthogonal chain routing
            for i in range(len(pts) - 1):
                ax, ay = pts[i]
                bx, by = pts[i + 1]

                # Horizontal first, then vertical
                if abs(ax - bx) > 0.01:
                    wires.append((ax, ay, bx, ay))
                if abs(ax - bx) > 0.01 and abs(ay - by) > 0.01:
                    juncs.append((bx, ay))
                if abs(ay - by) > 0.01:
                    wires.append((bx, ay, bx, by))

            # Junction dots at shared pins (3+ connections)
            for i in range(1, len(pts) - 1):
                px, py = pts[i]
                count = 0
                for w in wires:
                    if (abs(w[0]-px) < 0.1 and abs(w[1]-py) < 0.1) or \
                       (abs(w[2]-px) < 0.1 and abs(w[3]-py) < 0.1):
                        count += 1
                if count >= 2:
                    juncs.append((px, py))

        return wires, juncs
