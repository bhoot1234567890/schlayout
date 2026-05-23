"""Basic smoke tests for schlayout."""

import sys
sys.path.insert(0, "src")

from schlayout import (
    Netlist, SymbolDef, Pin, SugiyamaPlacer,
    ManhattanRouter, KiCadWriter,
)


def test_simple_rc_circuit():
    """A resistor + capacitor + GND — minimal valid schematic."""
    nl = Netlist(name="RC Test", date="2026-05-23")

    nl.add_symbol("res", SymbolDef(
        lib_id="Device:R", reference_prefix="R", value="10k",
        pins=[Pin("1"), Pin("2")], width=5, height=4,
    ))
    nl.add_symbol("cap", SymbolDef(
        lib_id="Device:C", reference_prefix="C", value="100n",
        pins=[Pin("1"), Pin("2")], width=4, height=4,
    ))
    nl.add_symbol("gnd", SymbolDef(
        lib_id="power:GND", reference_prefix="#PWR", value="GND",
        pins=[Pin("1", "GND", "power_in")],
        width=2.5, height=2.5, is_power=True,
    ))

    nl.add_component("R1", "res")
    nl.add_component("C1", "cap")
    nl.add_component("GND_1", "gnd")

    nl.add_net("RC_OUT", ("R1", "2"), ("C1", "1"))
    nl.add_net("GND", ("C1", "2"), ("GND_1", "1"))

    # Place
    placer = SugiyamaPlacer(nl)
    layers, ordering = placer.run()
    assert set(layers.values()) == {0, 1}, f"Unexpected layers: {set(layers.values())}"

    # Route
    router = ManhattanRouter(nl)
    wires, junctions, labels = router.route_all()
    assert len(wires) > 0, "No wires generated"

    # Write
    writer = KiCadWriter(nl)
    writer.set_routing(wires, junctions, labels)
    content = writer.generate()
    assert content.startswith("(kicad_sch"), "Bad file header"
    assert content.count("(") == content.count(")"), "Parenthesis imbalance"
    assert "(uuid " in content, "Missing UUIDs"

    print(f"✅ RC test passed: {len(wires)} wires, balanced parens")


def test_pin_positions():
    """Pin positions span the symbol correctly."""
    sym = SymbolDef(
        lib_id="Test:IC", reference_prefix="U", value="",
        pins=[Pin(str(i)) for i in range(1, 9)],
        width=10, height=16,
    )

    # Check all pin positions are within symbol bounds
    hw, hh = sym.width / 2, sym.height / 2
    for i in range(len(sym.pins)):
        px, py = sym.pin_position(i)
        assert abs(px) == hw, f"Pin {i} not on edge: x={px}, expected ±{hw}"
        assert -hh <= py <= hh, f"Pin {i} Y out of bounds: {py}"

    print(f"✅ Pin position test passed: {len(sym.pins)} pins on boundary")


def test_layer_assignment():
    """Power symbols go to column 0/4, IC to center."""
    nl = Netlist(name="Layer Test")
    nl.add_symbol("ic", SymbolDef(
        lib_id="Test:U", reference_prefix="U", value="",
        pins=[Pin("1"), Pin("2")], width=10, height=10,
    ))
    nl.add_symbol("gnd", SymbolDef(
        lib_id="power:GND", reference_prefix="#PWR", value="GND",
        pins=[Pin("1")], width=2, height=2, is_power=True,
    ))
    nl.add_symbol("vdd", SymbolDef(
        lib_id="power:VDD", reference_prefix="#PWR", value="VDD",
        pins=[Pin("1")], width=2, height=2, is_power=True,
    ))

    nl.add_component("U1", "ic")
    nl.add_component("GND_1", "gnd")
    nl.add_component("VDD_1", "vdd")

    placer = SugiyamaPlacer(nl)
    layers = placer.assign_layers()

    assert layers["U1"] == 2, f"IC should be center (2), got {layers['U1']}"
    assert layers["GND_1"] == 0, f"GND should be left (0), got {layers['GND_1']}"
    assert layers["VDD_1"] == 4, f"VDD should be right (4), got {layers['VDD_1']}"

    print("✅ Layer assignment test passed")


if __name__ == "__main__":
    test_pin_positions()
    test_layer_assignment()
    test_simple_rc_circuit()
    print("\n🎉 All tests passed")
