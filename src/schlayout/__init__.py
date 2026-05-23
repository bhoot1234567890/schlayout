"""schlayout — Schematic auto-placement engine.

Load symbols from KiCad system libraries, brute-force optimal placement,
and generate valid .kicad_sch files.
"""

from schlayout.symbols import SymbolLibrary, SymbolData, SymbolPin
from schlayout.placer import BruteForcePlacer, PlacedComponent, NetDef
from schlayout.force_placer import ForceDirectedPlacer
from schlayout.generator import SchematicGenerator

__version__ = "0.2.0"
__all__ = [
    "SymbolLibrary", "SymbolData", "SymbolPin",
    "BruteForcePlacer", "PlacedComponent", "NetDef",
    "SchematicGenerator",
]
