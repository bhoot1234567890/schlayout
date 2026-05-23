"""Manhattan (orthogonal) wire router for schematic connections.

Routes each net as a spanning tree of horizontal/vertical wire segments
with junction dots at branch points. All coordinates snapped to grid.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import uuid
from .netlist import Netlist

GRID = 2.54  # mm — KiCad's standard connection grid


@dataclass
class WireSegment:
    """A single wire segment between two points."""
    x1: float; y1: float
    x2: float; y2: float
    _uuid: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def start(self) -> Tuple[float, float]:
        return (self.x1, self.y1)

    @property
    def end(self) -> Tuple[float, float]:
        return (self.x2, self.y2)


@dataclass
class Junction:
    """A connection dot at a wire intersection."""
    x: float; y: float
    _uuid: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class NetLabel:
    """A text label for a net."""
    text: str
    x: float; y: float
    rotation: float = 0.0
    _uuid: str = field(default_factory=lambda: str(uuid.uuid4()))


def snap(v: float) -> float:
    """Snap a coordinate to the KiCad grid."""
    return round(v / GRID) * GRID


class ManhattanRouter:
    """Route nets as orthogonal wire segments with junction dots."""

    def __init__(self, netlist: Netlist, tolerance: float = 0.01):
        self.nl = netlist
        self.tolerance = tolerance
        self.wires: List[WireSegment] = []
        self.junctions: List[Junction] = []
        self.labels: List[NetLabel] = []

    def route_all(self) -> Tuple[List[WireSegment], List[Junction], List[NetLabel]]:
        """Route every net in the netlist."""
        pin_map = self._build_pin_map()

        for net in self.nl.nets:
            if len(net.connections) < 2:
                continue

            points: List[Tuple[str, Tuple[float, float]]] = []
            for ref, pin_num in net.connections:
                key = (ref, pin_num)
                if key in pin_map:
                    points.append((ref, pin_map[key]))

            if len(points) < 2:
                continue

            # Star routing from the first pin
            center_ref, center_pos = points[0]
            for ref, pos in points[1:]:
                self._route_pair(center_pos, pos)

            # Place label snapped to grid, at the first pin + 1 grid unit up
            if net.name not in ("GND", "VDD", "VDD_nRF"):
                cx, cy = center_pos
                self.labels.append(NetLabel(
                    text=net.name,
                    x=snap(cx),
                    y=snap(cy + GRID),
                ))

        return self.wires, self.junctions, self.labels

    def _build_pin_map(self) -> Dict[Tuple[str, str], Tuple[float, float]]:
        """Build lookup: (component_ref, pin_number) → world (x, y)."""
        pin_map = {}
        for comp in self.nl.components:
            for i, pin in enumerate(comp.symbol.pins):
                px, py = comp.pin_world_position(i)
                pin_map[(comp.ref, pin.number)] = (px, py)

            # Power symbols: pin at component center
            if comp.symbol.is_power and comp.symbol.pins:
                pin_map[(comp.ref, comp.symbol.pins[0].number)] = (comp.x, comp.y)

        return pin_map

    def _route_pair(
        self, a: Tuple[float, float], b: Tuple[float, float]
    ) -> None:
        """Route a Manhattan path between two points.

        Horizontal first, then vertical. Midpoint snapped to grid.
        """
        ax, ay = a
        bx, by = b
        mid_x = snap((ax + bx) / 2)

        # Segment 1: horizontal from A to mid_x
        if abs(ax - mid_x) > self.tolerance:
            self.wires.append(WireSegment(ax, ay, mid_x, ay))

        # Junction at the bend point
        if abs(ax - mid_x) > self.tolerance and abs(ay - by) > self.tolerance:
            self.junctions.append(Junction(mid_x, ay))

        # Segment 2: vertical
        if abs(ay - by) > self.tolerance:
            self.wires.append(WireSegment(mid_x, ay, mid_x, by))

        # Segment 3: horizontal to B
        if abs(mid_x - bx) > self.tolerance:
            self.junctions.append(Junction(mid_x, by))
            self.wires.append(WireSegment(mid_x, by, bx, by))
