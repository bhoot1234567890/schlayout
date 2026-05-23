"""Example: nRF52832-QFAA NFC reference schematic.

Builds the complete netlist, runs placement + routing, writes KiCad file.
"""

import sys
sys.path.insert(0, "src")

from schlayout import (
    Netlist, SymbolDef, Pin, SugiyamaPlacer,
    ManhattanRouter, KiCadWriter,
)


def build_nrf52_nfc() -> Netlist:
    nl = Netlist(
        name="nRF52832-QFAA NFC Reference Layout",
        date="2026-05-23",
    )

    # ---- Symbol Definitions ----

    # nRF52832-QFAA (48-pin QFN — key pins only)
    nl.add_symbol("nRF52832", SymbolDef(
        lib_id="nRF52:nRF52832-QFAA",
        reference_prefix="U",
        value="nRF52832-QFAA",
        pins=[
            Pin("1", "DEC1", "power_in"),
            Pin("2", "P0.00/XL1", "input"),
            Pin("3", "P0.01/XL2", "output"),
            Pin("13", "VDD", "power_in"),
            Pin("25", "SWDCLK", "input"),
            Pin("26", "SWDIO", "bidirectional"),
            Pin("30", "ANT", "output"),
            Pin("31", "VSS", "power_in"),
            Pin("32", "DEC2", "power_in"),
            Pin("34", "XC1", "input"),
            Pin("35", "XC2", "output"),
            Pin("36", "VDD", "power_in"),
            Pin("45", "VSS", "power_in"),
            Pin("46", "DEC4", "power_in"),
            Pin("48", "VDD", "power_in"),
        ],
        width=16, height=20,
    ))

    # Passives
    nl.add_symbol("cap", SymbolDef(
        lib_id="Device:C", reference_prefix="C", value="",
        pins=[Pin("1"), Pin("2")], width=4, height=4,
    ))
    nl.add_symbol("ind", SymbolDef(
        lib_id="Device:L", reference_prefix="L", value="",
        pins=[Pin("1"), Pin("2")], width=6, height=4,
    ))
    nl.add_symbol("xtal", SymbolDef(
        lib_id="Device:X", reference_prefix="X", value="",
        pins=[Pin("1"), Pin("2")], width=6, height=5,
    ))
    nl.add_symbol("gnd", SymbolDef(
        lib_id="power:GND", reference_prefix="#PWR", value="GND",
        pins=[Pin("1", "GND", "power_in")],
        width=2.5, height=2.5, is_power=True,
    ))
    nl.add_symbol("vdd", SymbolDef(
        lib_id="power:VDD", reference_prefix="#PWR", value="VDD",
        pins=[Pin("1", "VDD", "power_out")],
        width=2.5, height=2.5, is_power=True,
    ))

    # ---- Components ----

    nl.add_component("U1", "nRF52832")
    for ref in ["C1", "C2", "C3", "C4", "C5", "C7", "C8", "C9", "C10",
                "C11", "C12", "C_tune1", "C_tune2"]:
        nl.add_component(ref, "cap")
    for ref in ["L1", "L2", "L3"]:
        nl.add_component(ref, "ind")
    for ref in ["X1", "X2"]:
        nl.add_component(ref, "xtal")
    for i in range(1, 7):
        nl.add_component(f"GND_{i}", "gnd")
    nl.add_component("VDD_1", "vdd")

    # ---- Nets ----

    nl.add_net("DEC1", ("U1", "1"), ("C7", "1"), ("GND_1", "1"))
    nl.add_net("XL1", ("U1", "2"), ("X1", "1"), ("C1", "1"))
    nl.add_net("XL2", ("U1", "3"), ("X1", "2"), ("C2", "1"))
    nl.add_net("VDD_nRF",
               ("U1", "13"), ("U1", "36"), ("U1", "48"),
               ("C8", "1"), ("C9", "1"), ("C10", "1"),
               ("L2", "1"), ("VDD_1", "1"))
    nl.add_net("DEC4", ("U1", "46"), ("C4", "1"))
    nl.add_net("DEC2", ("U1", "32"), ("C5", "1"), ("GND_2", "1"))
    nl.add_net("SWDCLK", ("U1", "25"))
    nl.add_net("SWDIO", ("U1", "26"))
    nl.add_net("ANT", ("U1", "30"), ("L1", "1"))
    nl.add_net("RF", ("L1", "2"), ("C3", "1"), ("L3", "1"))
    nl.add_net("XC1", ("U1", "34"), ("X2", "1"), ("C11", "1"))
    nl.add_net("XC2", ("U1", "35"), ("X2", "2"), ("C12", "1"))
    nl.add_net("GND",
               ("U1", "31"), ("U1", "45"),
               ("C1", "2"), ("C2", "2"), ("C3", "2"),
               ("C4", "2"), ("C7", "2"), ("C8", "2"),
               ("C9", "2"), ("C10", "2"), ("C11", "2"), ("C12", "2"),
               ("L3", "2"),
               ("GND_3", "1"), ("GND_4", "1"),
               ("GND_5", "1"), ("GND_6", "1"))
    nl.add_net("VDD_DEC4", ("L2", "2"), ("U1", "46"))
    nl.add_net("NFC1", ("C_tune1", "1"))
    nl.add_net("NFC2", ("C_tune2", "1"))

    return nl


def main():
    nl = build_nrf52_nfc()

    # Phase 1: Placement
    placer = SugiyamaPlacer(nl, rankdir="LR")
    layers, ordering = placer.run()
    print(f"Placed {len(nl.components)} components in "
          f"{len(set(layers.values()))} columns")

    # Phase 2: Routing
    router = ManhattanRouter(nl)
    wires, junctions, labels = router.route_all()
    print(f"Routed {len(wires)} wires, {len(junctions)} junctions, "
          f"{len(labels)} labels")

    # Phase 3: Write KiCad file
    writer = KiCadWriter(nl)
    writer.set_routing(wires, junctions, labels)
    writer.write_file("/tmp/nrf52_nfc.kicad_sch")
    print(f"Written /tmp/nrf52_nfc.kicad_sch ({nl.name})")


if __name__ == "__main__":
    main()
