"""LED circuit: Battery → current-limiting resistor → LED → GND.

Uses real KiCad symbol dimensions extracted from the system library.
"""

import sys
sys.path.insert(0, "src")

from schlayout import (
    Netlist, SymbolDef, Pin, SugiyamaPlacer,
    ManhattanRouter, KiCadWriter,
)


def build_led_circuit() -> Netlist:
    """Simple LED circuit: BAT1 → R1 → D1 → GND.

    Dimensions extracted from KiCad 10.0 system libraries:
      - LED (Device:LED): pins at ±3.81mm → symbol ~7.62×5.0mm
      - R (Device:R): rectangle 2.03×5.08mm, pins at (0,±3.81) → total ~2.5×12.7mm
      - Battery_Cell (Device:Battery_Cell): pins at (0,+5.08) & (0,-2.54) → ~6.5×10mm
      - GND (power:GND): pin at (0,0) → ~4×3mm
    """
    nl = Netlist(
        name="LED Circuit — Battery, Resistor, LED",
        date="2026-05-23",
    )

    # ---- Symbols with real KiCad dimensions ----

    nl.add_symbol("led", SymbolDef(
        lib_id="Device:LED",
        reference_prefix="D",
        value="LED",
        pins=[
            Pin("1", "K", "passive"),   # cathode, left side
            Pin("2", "A", "passive"),   # anode, right side
        ],
        width=7.62,  height=5.08,  # based on pin span ±3.81mm
    ))

    nl.add_symbol("res", SymbolDef(
        lib_id="Device:R",
        reference_prefix="R",
        value="220Ω",
        pins=[
            Pin("1", "~", "passive"),   # top
            Pin("2", "~", "passive"),   # bottom
        ],
        width=2.54,  height=12.7,  # rectangle 2.03mm + pin lengths
    ))

    nl.add_symbol("battery", SymbolDef(
        lib_id="Device:Battery_Cell",
        reference_prefix="BAT",
        value="3V",
        pins=[
            Pin("1", "+", "power_out"),  # positive terminal, top
            Pin("2", "−", "power_in"),   # negative terminal, bottom
        ],
        width=6.5,  height=10.16,
    ))

    nl.add_symbol("gnd", SymbolDef(
        lib_id="power:GND",
        reference_prefix="#PWR",
        value="GND",
        pins=[Pin("1", "GND", "power_in")],
        width=4.0,  height=3.0,
        is_power=True,
    ))

    # ---- Components ----

    nl.add_component("BAT1", "battery")
    nl.add_component("R1", "res")
    nl.add_component("D1", "led")
    nl.add_component("GND_1", "gnd")

    # ---- Nets (left-to-right signal flow) ----
    #
    #   BAT1(+) ─── R1 ─── D1(anode)
    #   BAT1(−) ─────────── D1(cathode) ─── GND
    #
    # Wait — in a real LED circuit:
    #   BAT(+) → R1(top) → R1(bottom) → LED(anode, pin 2)
    #   LED(cathode, pin 1) → GND
    #   BAT(−) → GND
    #
    # So the current path is: BAT1.1(+) → R1.1 → R1.2 → D1.2(A) → D1.1(K) → GND
    # And: BAT1.2(−) → GND

    nl.add_net("VCC", ("BAT1", "1"), ("R1", "1"))
    nl.add_net("LED_IN", ("R1", "2"), ("D1", "2"))  # R1 bottom → LED anode
    nl.add_net("GND", ("BAT1", "2"), ("D1", "1"), ("GND_1", "1"))

    return nl


def main():
    nl = build_led_circuit()

    # Custom column layout for this simple circuit
    # 4 components in a clean left-to-right flow:
    #   [BAT] → [R] → [LED] → [GND]
    #   col 0    col 1   col 2    col 3
    columns = {
        0: 25.4,   # Battery
        1: 63.5,   # Resistor
        2: 101.6,  # LED
        3: 139.7,  # GND (rightmost)
    }

    # Override layer assignment for clean flow
    placer = SugiyamaPlacer(nl, rankdir="LR")
    layers, ordering = placer.run(columns=columns)

    # Force the component order
    for comp in nl.components:
        if comp.ref == "BAT1":
            comp.layer = 0
        elif comp.ref == "R1":
            comp.layer = 1
        elif comp.ref == "D1":
            comp.layer = 2
        elif comp.ref == "GND_1":
            comp.layer = 3

    placer.assign_coordinates(layers, ordering, columns)

    # Route
    router = ManhattanRouter(nl)
    wires, junctions, labels = router.route_all()

    # Write
    writer = KiCadWriter(nl)
    writer.set_routing(wires, junctions, labels)
    writer.write_file("/tmp/led_circuit.kicad_sch")

    # Show placement
    print("=== LED Circuit Placement ===")
    for comp in nl.components:
        print(f"  {comp.ref:8s} layer={comp.layer}  pos=({comp.x:7.2f}, {comp.y:7.2f})  "
              f"size={comp.symbol.width}×{comp.symbol.height}mm")
    print(f"\nRouted: {len(wires)} wires, {len(junctions)} junctions, {len(labels)} labels")
    print(f"Written: /tmp/led_circuit.kicad_sch")


if __name__ == "__main__":
    main()
