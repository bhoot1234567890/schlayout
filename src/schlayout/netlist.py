"""Netlist data model — the abstract description of a circuit.

A Netlist is a graph of Components connected by Nets. It carries no
geometric information — that's added by the layout engine.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import uuid


@dataclass
class Pin:
    """A pin on a component symbol."""
    number: str
    name: str = "~"
    electrical_type: str = "passive"
    # electrical_type values: input, output, bidirectional, tri_state,
    #   passive, free, unspecified, power_in, power_out,
    #   open_collector, open_emitter, no_connect


@dataclass
class SymbolDef:
    """A library symbol definition — the template for a component type."""
    lib_id: str          # e.g. "Device:R", "power:GND", "nRF52:nRF52832-QFAA"
    reference_prefix: str  # e.g. "R", "C", "U", "#PWR"
    value: str = ""
    pins: List[Pin] = field(default_factory=list)
    width: float = 5.0    # mm
    height: float = 5.0   # mm
    is_power: bool = False
    offsets: List[Tuple[float, float]] | None = None  # explicit pin (x,y) offsets from center

    @property
    def pin_count(self) -> int:
        return len(self.pins)

    def pin_position(self, index: int) -> Tuple[float, float]:
        """Return the (x, y) offset of a pin on the symbol boundary.
        
        If explicit offsets are set, use those. Otherwise distribute
        evenly: left side first, then right side.
        """
        if self.offsets and index < len(self.offsets):
            return self.offsets[index]
        
        hw, hh = self.width / 2, self.height / 2
        n = len(self.pins)

        if n <= 4:
            if index < n / 2:
                y = hh - (index + 0.5) * (self.height / (n / 2))
                return (-hw, y)
            else:
                y = hh - ((index - n / 2) + 0.5) * (self.height / (n / 2))
                return (hw, y)
        else:
            half = n // 2
            if index < half:
                y = hh - (index + 0.5) * (self.height / half)
                return (-hw, y)
            else:
                y = hh - ((index - half) + 0.5) * (self.height / (n - half))
                return (hw, y)

@dataclass
class Component:
    """A placed component instance."""
    ref: str
    symbol: SymbolDef
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    layer: int = 0      # assigned by layout engine
    order: int = 0      # within-layer ordering
    _uuid: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def position(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def pin_world_position(self, pin_index: int) -> Tuple[float, float]:
        """Return the absolute (x, y) of a pin in schematic space."""
        px, py = self.symbol.pin_position(pin_index)
        return (self.x + px, self.y - py)


@dataclass
class Net:
    """A net — a named electrical connection between pins."""
    name: str
    connections: List[Tuple[str, str]] = field(default_factory=list)
    # Each connection: (component_ref, pin_number)


class Netlist:
    """Complete circuit description without geometry."""

    def __init__(self, name: str = "", date: str = ""):
        self.name = name
        self.date = date
        self.symbols: Dict[str, SymbolDef] = {}
        self.components: List[Component] = []
        self.nets: List[Net] = []
        self._root_uuid: str = str(uuid.uuid4())

    @property
    def root_uuid(self) -> str:
        return self._root_uuid

    def add_symbol(self, key: str, symbol: SymbolDef) -> SymbolDef:
        self.symbols[key] = symbol
        return symbol

    def add_component(self, ref: str, symbol_key: str) -> Component:
        symbol = self.symbols[symbol_key]
        comp = Component(ref=ref, symbol=symbol)
        self.components.append(comp)
        return comp

    def add_net(self, name: str, *connections: Tuple[str, str]) -> Net:
        net = Net(name=name, connections=list(connections))
        self.nets.append(net)
        return net

    def get_component(self, ref: str) -> Optional[Component]:
        for c in self.components:
            if c.ref == ref:
                return c
        return None

    def adjacency(self) -> Dict[str, set]:
        """Return the adjacency graph: {ref: {connected_refs}}."""
        adj: Dict[str, set] = {}
        for net in self.nets:
            refs = [ref for ref, _ in net.connections]
            for i, a in enumerate(refs):
                adj.setdefault(a, set())
                for b in refs[i + 1:]:
                    adj[a].add(b)
                    adj.setdefault(b, set()).add(a)
        return adj
