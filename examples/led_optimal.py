"""LED Circuit — battery, resistor, LED. Brute-force optimal placement."""

import sys
sys.path.insert(0, "src")

from schlayout import SymbolLibrary, BruteForcePlacer, NetDef, SchematicGenerator
from schlayout.placer import snap

lib = SymbolLibrary()
bat = lib.load("Device", "Battery_Cell"); bat.value = "3V"
res = lib.load("Device", "R"); res.value = "220Ω"
led = lib.load("Device", "LED"); led.value = "LED"

print(f"BAT {bat.width}×{bat.height}mm  R {res.width}×{res.height}mm  LED {led.width}×{led.height}mm")

components = [("BAT1", bat), ("R1", res), ("D1", led)]
nets = [
    NetDef("VCC",    [("BAT1", "1"), ("R1", "1")]),
    NetDef("LED_IN", [("R1", "2"), ("D1", "2")]),
    NetDef("RTN",    [("D1", "1"), ("BAT1", "2")]),
]

# Small search grid — 9 X positions × 8 Y positions = 72 per component
# 72³ × 64 rotations = ~24M combos, should be fast
placer = BruteForcePlacer(components, nets,
    x_range=[snap(x) for x in range(12, 40, 3)],   # ~9 values
    y_range=[snap(y) for y in range(30, 60, 4)],   # ~8 values
)

print("Searching...")
placed, score = placer.search()

print(f"\nOptimal (score={score:.1f}):")
for p in placed:
    print(f"  {p.ref:6s} ({p.cx:5.1f},{p.cy:5.1f}) rot={p.rotation:3d}°  {p.w:.1f}×{p.h:.1f}mm")
    for i, pin in enumerate(p.symbol.pins):
        wx, wy = p.pin_world(i)
        print(f"    pin {pin.number} '{pin.name}': ({wx:.1f}, {wy:.1f})")

gen = SchematicGenerator(title="LED Circuit")
gen.generate(placed, nets, "/tmp/led_circuit.kicad_sch", symbol_lib=lib)

c = open("/tmp/led_circuit.kicad_sch").read()
print(f"\nParens: {c.count('(')}/{c.count(')')} {'OK' if c.count('(')==c.count(')') else 'BAD'}")
print("Written /tmp/led_circuit.kicad_sch")
