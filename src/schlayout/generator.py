"""KiCad .kicad_sch file generator using real system symbol data."""

from __future__ import annotations
import uuid
from typing import Dict, List, Tuple
from .symbols import SymbolData, SymbolLibrary
from .placer import PlacedComponent, NetDef


class SchematicGenerator:
    """Generate a .kicad_sch file from placed components and nets."""

    def __init__(self, title: str = "Schematic", date: str = "2026-05-23"):
        self.title = title
        self.date = date
        self.root_uuid = str(uuid.uuid4())

    def generate(
        self,
        placed: List[PlacedComponent],
        nets: List[NetDef],
        output_path: str,
        symbol_lib: SymbolLibrary | None = None,
    ) -> str:
        wires, juncs = self._route_all(placed, nets)

        T = "\t"
        L = []
        L.append("(kicad_sch")
        L.append(f'{T}(version 20260306)')
        L.append(f'{T}(generator "schlayout")')
        L.append(f'{T}(generator_version "0.1.0")')
        L.append(f'{T}(uuid "{self.root_uuid}")')
        L.append(f'{T}(paper "A4")')
        L.append(f'{T}(title_block')
        L.append(f'{T}{T}(title "{self.title}")')
        L.append(f'{T}{T}(date "{self.date}")')
        L.append(f'{T}{T}(rev "1.0")')
        L.append(f'{T})')

        L.append(f'{T}(lib_symbols')
        seen = set()
        for comp in placed:
            lib_id = comp.symbol.lib_id
            if lib_id in seen:
                continue
            seen.add(lib_id)
            if comp.symbol.raw_fragment:
                frag = comp.symbol.raw_fragment.strip()
                frag = frag.replace(
                    f'(symbol "{comp.symbol.name}"',
                    f'(symbol "{lib_id}"', 1
                )
                for line in frag.split('\n'):
                    if line.strip():
                        L.append(f'{T}{T}{line}')
                L.append('')
        L.append(f'{T})')

        for comp in placed:
            cx, cy, rot = comp.cx, comp.cy, comp.rotation
            lib = comp.symbol.lib_id
            ref = "#PWR" if comp.symbol.is_power else comp.ref
            L.append(f'{T}(symbol')
            L.append(f'{T}{T}(lib_id "{lib}")')
            L.append(f'{T}{T}(at {cx:.2f} {cy:.2f} {rot})')
            L.append(f'{T}{T}(unit 1)')
            L.append(f'{T}{T}(in_bom yes) (on_board yes)')
            L.append(f'{T}{T}(uuid "{str(uuid.uuid4())}")')
            L.append(f'{T}{T}(property "Reference" "{ref}" (at {cx:.2f} {cy+2.54:.2f} 0)')
            L.append(f'{T}{T}{T}(effects (font (size 1.27 1.27)) (justify left)))')
            L.append(f'{T}{T}(property "Value" "{comp.symbol.value}" (at {cx:.2f} {cy-2.54:.2f} 0)')
            L.append(f'{T}{T}{T}(effects (font (size 1.27 1.27)) (justify left)))')
            for k in ["Footprint", "Datasheet"]:
                L.append(f'{T}{T}(property "{k}" "" (at {cx:.2f} {cy:.2f} 0)')
                L.append(f'{T}{T}{T}(effects (font (size 1.27 1.27)) (justify left) hide))')
            for pin in comp.symbol.pins:
                L.append(f'{T}{T}(pin "{pin.number}" (uuid "{str(uuid.uuid4())}"))')
            L.append(f'{T}{T}(instances')
            L.append(f'{T}{T}{T}(project "schlayout"')
            L.append(f'{T}{T}{T}{T}(path "/{self.root_uuid}/" (reference "{ref}") (unit 1))')
            L.append(f'{T}{T}{T})')
            L.append(f'{T}{T})')
            L.append(f'{T})')

        for w in wires:
            L.append(f'{T}(wire')
            L.append(f'{T}{T}(pts (xy {w[0]:.2f} {w[1]:.2f}) (xy {w[2]:.2f} {w[3]:.2f}))')
            L.append(f'{T}{T}(stroke (width 0) (type default) (color 0 0 0 0))')
            L.append(f'{T}{T}(uuid "{str(uuid.uuid4())}"))')

        for j in juncs:
            L.append(f'{T}(junction')
            L.append(f'{T}{T}(at {j[0]:.2f} {j[1]:.2f})')
            L.append(f'{T}{T}(diameter 0) (color 0 0 0 0)')
            L.append(f'{T}{T}(uuid "{str(uuid.uuid4())}"))')

        # Place labels at the midpoint of the LAST wire segment for each net
        # Build net-to-wire mapping
        net_last_wire = {}
        for net in nets:
            if len(net.connections) < 2:
                continue
            # The last wire is at index = (number of connections - 2)
            # Since wires connect conns[0]→conns[1], conns[1]→conns[2], etc.
            # Actually with MST routing the order may differ.
            # Simpler: find the wire whose endpoint matches the net's last pin
            ra, pna = net.connections[-1]
            for comp in placed:
                if comp.ref == ra:
                    px, py = comp.pin_by_number(pna)
                    for wi, w in enumerate(wires):
                        if (abs(w[0]-px)<0.5 and abs(w[1]-py)<0.5) or                            (abs(w[2]-px)<0.5 and abs(w[3]-py)<0.5):
                            # Use midpoint of this wire for the label
                            lx = (w[0] + w[2]) / 2
                            ly = (w[1] + w[3]) / 2
                            net_last_wire[net.name] = (lx, ly)
                            break
                    break
        for net in nets:
            if net.name in net_last_wire:
                lx, ly = net_last_wire[net.name]
            else:
                ra, pna = net.connections[0] if net.connections else (None, None)
                lx, ly = 0, 0
                for comp in placed:
                    if comp.ref == ra:
                        lx, ly = comp.pin_by_number(pna)
                        break
            L.append(f'{T}(label "{net.name}"')
            L.append(f'{T}{T}(at {lx:.2f} {ly:.2f} 0)')
            L.append(f'{T}{T}(effects (font (size 1.27 1.27)) (justify left))')
            L.append(f'{T}{T}(uuid "{str(uuid.uuid4())}"))')

        L.append(f'{T}(sheet_instances')
        L.append(f'{T}{T}(path "/" (page "1"))')
        L.append(f'{T})')
        L.append(')')

        content = '\n'.join(L)
        while '\n\n\n' in content:
            content = content.replace('\n\n\n', '\n\n')

        with open(output_path, 'w') as f:
            f.write(content)
        return content

    def _route_all(
        self, placed: List[PlacedComponent], nets: List[NetDef],
    ) -> Tuple[List[Tuple[float,float,float,float]], List[Tuple[float,float]]]:
        """Route nets with direct pin-to-pin connections (diagonal allowed).

        For 2-pin nets: single direct wire between pins.
        For multi-drop nets: chain pins in order, add junctions at shared pins.
        """
        comp_map = {p.ref: p for p in placed}
        wires = []
        juncs = []

        for net in nets:
            conns = net.connections
            if len(conns) < 2:
                continue

            pts = []
            for ref, pn in conns:
                comp = comp_map.get(ref)
                if comp:
                    pts.append(comp.pin_by_number(pn))
            if len(pts) < 2:
                continue

            # Minimum spanning tree: connect closest pins first
            if len(pts) == 2:
                wires.append((pts[0][0], pts[0][1], pts[1][0], pts[1][1]))
            else:
                # Prim's algorithm
                connected = {0}
                while len(connected) < len(pts):
                    best_i, best_j, best_d = -1, -1, float('inf')
                    for i in connected:
                        for j in range(len(pts)):
                            if j not in connected:
                                d = (pts[i][0]-pts[j][0])**2 + (pts[i][1]-pts[j][1])**2
                                if d < best_d:
                                    best_d, best_i, best_j = d, i, j
                    wires.append((pts[best_i][0], pts[best_i][1], pts[best_j][0], pts[best_j][1]))
                    connected.add(best_j)

            # Junction at internal pins (shared by 2+ wire segments)
            for i in range(1, len(pts) - 1):
                px, py = pts[i]
                count = 0
                for w in wires:
                    if (abs(w[0] - px) < 0.1 and abs(w[1] - py) < 0.1) or \
                       (abs(w[2] - px) < 0.1 and abs(w[3] - py) < 0.1):
                        count += 1
                if count >= 2:
                    juncs.append((px, py))

        return wires, juncs
