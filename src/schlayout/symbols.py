"""KiCad symbol library parser — extract real symbol data from .kicad_sym files."""

from __future__ import annotations
import re, os, json
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional


@dataclass
class SymbolPin:
    number: str
    name: str = ""
    electrical_type: str = "passive"
    x: float = 0.0
    y: float = 0.0
    angle: int = 0
    length: float = 2.54


@dataclass
class SymbolData:
    """Complete data for a KiCad symbol from the system library."""
    name: str
    lib_id: str           # e.g. "Device:R"
    reference: str        # e.g. "R"
    value: str            # e.g. "R"
    width: float          # bounding box width (mm)
    height: float         # bounding box height (mm)
    pins: List[SymbolPin] = field(default_factory=list)
    is_power: bool = False
    raw_fragment: str = ""  # complete S-expression from the library file

    @property
    def pin_count(self) -> int:
        return len(self.pins)

    def pin_offset(self, index: int) -> Tuple[float, float]:
        """Return (x, y) offset of the pin from symbol center."""
        if 0 <= index < len(self.pins):
            return (self.pins[index].x, self.pins[index].y)
        return (0.0, 0.0)

    def pin_offsets(self) -> List[Tuple[float, float]]:
        return [(p.x, p.y) for p in self.pins]

    def rotated_offsets(self, deg: int) -> List[Tuple[float, float]]:
        """Pin offsets after rotating the symbol CCW by `deg` degrees."""
        import math
        rad = math.radians(deg)
        c, s = math.cos(rad), math.sin(rad)
        result = []
        for p in self.pins:
            rx = p.x * c - p.y * s
            ry = p.x * s + p.y * c
            result.append((round(rx, 4), round(ry, 4)))
        return result

    def rotated_size(self, deg: int) -> Tuple[float, float]:
        """Width and height after rotation."""
        if deg % 180 == 0:
            return (self.width, self.height)
        return (self.height, self.width)


class SymbolLibrary:
    """Parser for KiCad .kicad_sym library files."""

    def __init__(self, lib_dirs: List[str] | None = None):
        if lib_dirs is None:
            lib_dirs = self._default_lib_dirs()
        self.lib_dirs = lib_dirs
        self._cache: Dict[str, SymbolData] = {}

    @staticmethod
    def _default_lib_dirs() -> List[str]:
        import platform
        candidates = []
        if platform.system() == "Darwin":
            candidates.append(
                "/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols"
            )
        candidates.append("/usr/share/kicad/symbols")
        candidates.append(os.path.expanduser("~/Library/Application Support/kicad"))
        return [d for d in candidates if os.path.isdir(d)]

    def find_library(self, lib_name: str) -> Optional[str]:
        """Find the .kicad_sym file for a library name."""
        for d in self.lib_dirs:
            path = os.path.join(d, f"{lib_name}.kicad_sym")
            if os.path.isfile(path):
                return path
        return None

    def load(self, lib_name: str, sym_name: str) -> Optional[SymbolData]:
        """Load a symbol from a KiCad system library."""
        cache_key = f"{lib_name}:{sym_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        lib_path = self.find_library(lib_name)
        if not lib_path:
            return None

        with open(lib_path) as f:
            content = f.read()

        data = self._parse(content, sym_name)
        if data:
            data.lib_id = f"{lib_name}:{sym_name}"
            data.raw_fragment = self._extract_fragment(content, sym_name)
            self._cache[cache_key] = data
        return data

    def _extract_fragment(self, content: str, sym_name: str) -> str:
        """Extract the raw S-expression for a symbol."""
        idx = content.find(f'(symbol "{sym_name}"')
        if idx < 0:
            return ""
        line_start = content.rfind('\n', 0, idx) + 1
        depth = 0
        in_str = False
        for i in range(line_start, len(content)):
            c = content[i]
            if c == '"' and (i == 0 or content[i-1] != '\\'):
                in_str = not in_str
            if not in_str:
                if c == '(': depth += 1
                elif c == ')':
                    depth -= 1
                    if depth == 0:
                        return content[line_start:i+1]
        return ""

    def _parse(self, content: str, sym_name: str) -> Optional[SymbolData]:
        """Parse a symbol definition from library content."""
        fragment = self._extract_fragment(content, sym_name)
        if not fragment:
            return None

        ref = re.search(r'\(property "Reference" "([^"]*)"', fragment)
        val = re.search(r'\(property "Value" "([^"]*)"', fragment)
        is_power = '(power' in fragment

        # Extract pins from _1_1 body
        pins = []
        for m in re.finditer(
            r'\(pin (\w+) \w+\s+\(at ([\d.-]+) ([\d.-]+) (\d+)\)\s+\(length ([\d.]+)\)\s+\(name "([^"]*)"',
            fragment
        ):
            pins.append(SymbolPin(
                electrical_type=m.group(1),
                x=float(m.group(2)), y=float(m.group(3)),
                angle=int(m.group(4)), length=float(m.group(5)),
                name=m.group(6), number="",
            ))

        # Pin numbers
        for i, m in enumerate(re.finditer(r'\(number "([^"]*)"', fragment)):
            if i < len(pins):
                pins[i].number = m.group(1)

        # Compute bounding box from graphics
        all_x, all_y = [], []
        for m in re.finditer(r'\(rectangle\s+\(start ([\d.-]+) ([\d.-]+)\)\s+\(end ([\d.-]+) ([\d.-]+)\)', fragment):
            all_x.extend([float(m.group(1)), float(m.group(3))])
            all_y.extend([float(m.group(2)), float(m.group(4))])
        for m in re.finditer(r'\(polyline\s+\(pts((?:\s*\(xy [\d.-]+ [\d.-]+\))+)', fragment):
            for pt in re.finditer(r'\(xy ([\d.-]+) ([\d.-]+)\)', m.group(1)):
                all_x.append(float(pt.group(1)))
                all_y.append(float(pt.group(2)))
        for m in re.finditer(r'\(circle\s+\(center ([\d.-]+) ([\d.-]+)\)\s+\(radius ([\d.]+)\)', fragment):
            cx, cy, r = float(m.group(1)), float(m.group(2)), float(m.group(3))
            all_x.extend([cx-r, cx+r]); all_y.extend([cy-r, cy+r])
        for p in pins:
            all_x.append(p.x); all_y.append(p.y)

        width = round(max(all_x) - min(all_x), 2) if all_x else 5.0
        height = round(max(all_y) - min(all_y), 2) if all_y else 5.0

        return SymbolData(
            name=sym_name,
            lib_id=f"?:{sym_name}",
            reference=ref.group(1) if ref else "?",
            value=val.group(1) if val else sym_name,
            width=width, height=height,
            pins=pins,
            is_power=is_power,
        )
