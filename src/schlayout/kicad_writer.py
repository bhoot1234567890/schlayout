"""KiCad .kicad_sch file writer.

Generates valid S-expression format for KiCad 7.x / 8.x (version 20231120).
"""

from __future__ import annotations
from typing import List, Optional
import uuid
from .netlist import Netlist, Component, SymbolDef, Pin
from .routing import WireSegment, Junction, NetLabel

INDENT = "  "


class KiCadWriter:
    """Serialize a placed+routed netlist to .kicad_sch format."""

    def __init__(self, netlist: Netlist):
        self.nl = netlist
        self.wires: List[WireSegment] = []
        self.junctions: List[Junction] = []
        self.labels: List[NetLabel] = []
        self._pin_uuids: dict = {}  # (comp_ref, pin_num) → instance UUID

    # ----- Public API -----

    def set_routing(
        self,
        wires: List[WireSegment],
        junctions: List[Junction],
        labels: List[NetLabel],
    ) -> None:
        self.wires = wires
        self.junctions = junctions
        self.labels = labels

    def generate(self) -> str:
        """Generate the complete .kicad_sch file content."""
        lines = []
        self._write_header(lines)
        self._write_title_block(lines)
        self._write_lib_symbols(lines)
        self._write_symbol_instances(lines)
        self._write_wires(lines)
        self._write_junctions(lines)
        self._write_labels(lines)
        self._write_border(lines)
        self._write_sheet_instances(lines)
        lines.append(")")
        return "\n".join(lines)

    def write_file(self, path: str) -> None:
        """Write the schematic to a file."""
        with open(path, "w") as f:
            f.write(self.generate())

    # ----- Header -----

    def _write_header(self, lines: List[str]) -> None:
        lines.append("(kicad_sch")
        lines.append(f'{INDENT}(version 20231120)')
        lines.append(f'{INDENT}(generator "schlayout")')
        lines.append(f'{INDENT}(generator_version "0.1.0")')
        lines.append(f'{INDENT}(uuid "{self.nl.root_uuid}")')
        lines.append(f'{INDENT}(paper "A4")')

    def _write_title_block(self, lines: List[str]) -> None:
        lines.append(f"{INDENT}(title_block")
        lines.append(f'{INDENT}{INDENT}(title "{self.nl.name}")')
        lines.append(f'{INDENT}{INDENT}(date "{self.nl.date}")')
        lines.append(f'{INDENT}{INDENT}(rev "1.0")')
        lines.append(f'{INDENT}{INDENT}(company "")')
        for i in range(1, 5):
            lines.append(f'{INDENT}{INDENT}(comment {i} "")')
        lines.append(f"{INDENT})")

    # ----- Library symbols -----

    def _write_lib_symbols(self, lines: List[str]) -> None:
        lines.append(f"{INDENT}(lib_symbols")
        for sym_key, sym in self.nl.symbols.items():
            self._write_one_symbol(lines, sym)
        lines.append(f"{INDENT})")

    def _write_one_symbol(self, lines: List[str], sym: SymbolDef) -> None:
        lines.append(f'{INDENT}{INDENT}(symbol "{sym.lib_id}"')
        if sym.is_power:
            lines.append(f"{INDENT}{INDENT}{INDENT}(power)")
        lines.append(f"{INDENT}{INDENT}{INDENT}(pin_numbers hide)")
        lines.append(f"{INDENT}{INDENT}{INDENT}(pin_names (offset 0))")
        lines.append(f"{INDENT}{INDENT}{INDENT}(in_bom yes) (on_board yes)")

        # Properties
        self._write_symbol_property(
            lines, "Reference", sym.reference_prefix, id=0, at_y=2.54
        )
        self._write_symbol_property(
            lines, "Value", sym.value, id=1, at_y=-2.54
        )
        self._write_symbol_property(
            lines, "Footprint", "", id=2, at_y=0, hide=True
        )
        self._write_symbol_property(
            lines, "Datasheet", "", id=3, at_y=0, hide=True
        )

        # Symbol body — graphics only in _0_1
        body_name = sym.lib_id.split(":")[-1] + "_0_1"
        lines.append(f'{INDENT}{INDENT}{INDENT}(symbol "{body_name}"')
        self._write_symbol_rectangle(lines, sym)
        lines.append(f"{INDENT}{INDENT}{INDENT})")  # close _0_1

        # Pin body — pins only in _1_1
        pin_body_name = sym.lib_id.split(":")[-1] + "_1_1"
        lines.append(f'{INDENT}{INDENT}{INDENT}(symbol "{pin_body_name}"')
        self._write_symbol_pins(lines, sym)
        lines.append(f"{INDENT}{INDENT}{INDENT})")  # close _1_1

        lines.append(f"{INDENT}{INDENT})")          # close symbol

    def _write_symbol_property(
        self, lines: List[str], key: str, value: str,
        *, id: int, at_y: float, hide: bool = False,
    ) -> None:
        hide_attr = " hide" if hide else ""
        lines.append(
            f'{INDENT}{INDENT}{INDENT}(property "{key}" "{value}" '
            f'(id {id}) (at 0 {at_y:.2f} 0)'
        )
        lines.append(
            f"{INDENT}{INDENT}{INDENT}{INDENT}"
            f"(effects (font (size 1.27 1.27)) (justify left){hide_attr}))"
        )

    def _write_symbol_rectangle(
        self, lines: List[str], sym: SymbolDef
    ) -> None:
        hw, hh = sym.width / 2, sym.height / 2
        lines.append(
            f"{INDENT}{INDENT}{INDENT}{INDENT}"
            f"(rectangle (start {-hw:.2f} {-hh:.2f}) (end {hw:.2f} {hh:.2f})"
        )
        lines.append(
            f"{INDENT}{INDENT}{INDENT}{INDENT}{INDENT}"
            f"(stroke (width 0.254) (type default))"
        )
        lines.append(
            f"{INDENT}{INDENT}{INDENT}{INDENT}{INDENT}"
            f"(fill (type background)))"
        )

    def _write_symbol_pins(
        self, lines: List[str], sym: SymbolDef
    ) -> None:
        for i, pin in enumerate(sym.pins):
            px, py = sym.pin_position(i)
            if abs(py) > abs(px):
                angle = 90 if py > 0 else 270
            else:
                angle = 180 if px < 0 else 0
            lines.append(
                f"{INDENT}{INDENT}{INDENT}{INDENT}"
                f"(pin {pin.electrical_type} line "
                f"(at {px:.2f} {py:.2f} {angle}) (length 2.54)"
            )
            lines.append(
                f"{INDENT}{INDENT}{INDENT}{INDENT}{INDENT}"
                f'(name "{pin.name}" (effects (font (size 1.27 1.27))))'
            )
            lines.append(
                f"{INDENT}{INDENT}{INDENT}{INDENT}{INDENT}"
                f'(number "{pin.number}" (effects (font (size 1.27 1.27)))))'
            )

    # ----- Symbol instances -----

    def _write_symbol_instances(self, lines: List[str]) -> None:
        for comp in self.nl.components:
            self._write_one_instance(lines, comp)

    def _write_one_instance(
        self, lines: List[str], comp: Component
    ) -> None:
        sym = comp.symbol
        ref = "#PWR" if sym.is_power else comp.ref

        lines.append(f"{INDENT}(symbol")
        lines.append(f'{INDENT}{INDENT}(lib_id "{sym.lib_id}")')
        lines.append(f"{INDENT}{INDENT}(at {comp.x:.2f} {comp.y:.2f} {comp.rotation})")
        lines.append(f"{INDENT}{INDENT}(unit 1)")
        lines.append(f"{INDENT}{INDENT}(body_style 1)")
        lines.append(f"{INDENT}{INDENT}(in_bom yes) (on_board yes) (dnp no)")
        lines.append(f'{INDENT}{INDENT}(uuid "{comp._uuid}")')

        # Properties
        self._write_instance_property(lines, "Reference", ref, comp, at_y=2.54)
        self._write_instance_property(lines, "Value", sym.value, comp, at_y=-2.54)
        self._write_instance_property(
            lines, "Footprint", "", comp, at_y=0, hide=True
        )
        self._write_instance_property(
            lines, "Datasheet", "", comp, at_y=0, hide=True
        )

        # Pins with unique per-instance UUIDs
        for pin in sym.pins:
            pin_uuid = str(uuid.uuid4())
            self._pin_uuids[(comp.ref, pin.number)] = pin_uuid
            lines.append(
                f'{INDENT}{INDENT}(pin "{pin.number}" (uuid "{pin_uuid}"))'
            )

        # Instance data
        lines.append(f"{INDENT}{INDENT}(instances")
        lines.append(f'{INDENT}{INDENT}{INDENT}(project "schlayout"')
        lines.append(
            f'{INDENT}{INDENT}{INDENT}{INDENT}'
            f'(path "/{self.nl.root_uuid}/" (reference "{ref}") (unit 1))'
        )
        lines.append(f"{INDENT}{INDENT}{INDENT})")
        lines.append(f"{INDENT}{INDENT})")
        lines.append(f"{INDENT})")

    def _write_instance_property(
        self, lines: List[str], key: str, value: str,
        comp: Component, *, at_y: float, hide: bool = False,
    ) -> None:
        y = comp.y + at_y
        hide_attr = " hide" if hide else ""
        lines.append(
            f'{INDENT}{INDENT}(property "{key}" "{value}" '
            f'(at {comp.x:.2f} {y:.2f} 0)'
        )
        lines.append(
            f"{INDENT}{INDENT}{INDENT}"
            f"(effects (font (size 1.27 1.27)) (justify left){hide_attr}))"
        )

    # ----- Wires, junctions, labels -----

    def _write_wires(self, lines: List[str]) -> None:
        for w in self.wires:
            lines.append(f"{INDENT}(wire")
            lines.append(
                f"{INDENT}{INDENT}(pts (xy {w.x1:.2f} {w.y1:.2f}) "
                f"(xy {w.x2:.2f} {w.y2:.2f}))"
            )
            lines.append(
                f"{INDENT}{INDENT}(stroke (width 0) "
                f"(type default) (color 0 0 0 0))"
            )
            lines.append(f'{INDENT}{INDENT}(uuid "{w._uuid}"))')

    def _write_junctions(self, lines: List[str]) -> None:
        for j in self.junctions:
            lines.append(f"{INDENT}(junction")
            lines.append(f"{INDENT}{INDENT}(at {j.x:.2f} {j.y:.2f})")
            lines.append(f"{INDENT}{INDENT}(diameter 0)")
            lines.append(f"{INDENT}{INDENT}(color 0 0 0 0)")
            lines.append(f'{INDENT}{INDENT}(uuid "{j._uuid}"))')

    def _write_labels(self, lines: List[str]) -> None:
        for lbl in self.labels:
            lines.append(f'{INDENT}(label "{lbl.text}"')
            lines.append(
                f"{INDENT}{INDENT}(at {lbl.x:.2f} {lbl.y:.2f} {lbl.rotation})"
            )
            lines.append(
                f"{INDENT}{INDENT}(effects (font (size 1.27 1.27)) (justify left))"
            )
            lines.append(f'{INDENT}{INDENT}(uuid "{lbl._uuid}"))')

    # ----- Graphics -----

    def _write_border(self, lines: List[str]) -> None:
        """A4 page border (292×205 mm)."""
        border_uuid = str(uuid.uuid4())
        lines.append(f"{INDENT}(polyline")
        lines.append(
            f"{INDENT}{INDENT}(pts (xy 5 5) (xy 292 5) (xy 292 205) "
            f"(xy 5 205) (xy 5 5))"
        )
        lines.append(
            f"{INDENT}{INDENT}(stroke (width 0.1524) "
            f"(type default) (color 0 0 0 0))"
        )
        lines.append(f'{INDENT}{INDENT}(uuid "{border_uuid}"))')

    def _write_sheet_instances(self, lines: List[str]) -> None:
        lines.append(f"{INDENT}(sheet_instances")
        lines.append(f'{INDENT}{INDENT}(path "/" (page "1"))')
        lines.append(f"{INDENT})")
