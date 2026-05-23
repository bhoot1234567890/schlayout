"""10 simple circuits for testing the schematic placer."""

import sys
sys.path.insert(0, "src")
from schlayout import SymbolLibrary, ForceDirectedPlacer, NetDef, SchematicGenerator

lib = SymbolLibrary()

def build(name, components, nets):
    """Load symbols, run placer, generate file."""
    comps = []
    for ref, lib_name, sym_name, value in components:
        sym = lib.load(lib_name, sym_name)
        if sym is None:
            raise ValueError(f"Symbol not found: {lib_name}:{sym_name}")
        sym.value = value
        comps.append((ref, sym))
    
    net_defs = [NetDef(nm, conns) for nm, conns in nets]
    
    placer = ForceDirectedPlacer(comps, net_defs,
        T_initial=100, T_min=0.1, alpha=0.9, moves_per_temp=15,
        max_steps=50, position_restarts=1, centering=0.1)
    
    placed, score = placer.search()
    
    gen = SchematicGenerator(title=name)
    path = f"/tmp/{name.lower().replace(' ', '_')}.kicad_sch"
    gen.generate(placed, net_defs, path, symbol_lib=lib)
    
    c = open(path).read()
    ok = c.count('(') == c.count(')')
    print(f"  {name:30s} {len(comps)}c {len(nets)}n  score={score:.0f}  {'✓' if ok else '✗'}")
    return path


circuits = {
    "1. LED with Resistor": (
        [("BAT1", "Device", "Battery_Cell", "3V"),
         ("R1", "Device", "R", "220Ω"),
         ("D1", "Device", "LED", "LED")],
        [("VCC", [("BAT1", "1"), ("R1", "1")]),
         ("LED_IN", [("R1", "2"), ("D1", "2")]),
         ("RTN", [("D1", "1"), ("BAT1", "2")])],
    ),
    "2. Voltage Divider": (
        [("V1", "Device", "Battery_Cell", "5V"),
         ("R1", "Device", "R", "10k"),
         ("R2", "Device", "R", "10k"),
         ("GND1", "power", "GND", "GND")],
        [("VIN", [("V1", "1"), ("R1", "1")]),
         ("VOUT", [("R1", "2"), ("R2", "1")]),
         ("GND", [("R2", "2"), ("V1", "2"), ("GND1", "1")])],
    ),
    "3. RC Low-Pass Filter": (
        [("V1", "Device", "Battery_Cell", "5V"),
         ("R1", "Device", "R", "1k"),
         ("C1", "Device", "C", "100n"),
         ("GND1", "power", "GND", "GND")],
        [("VIN", [("V1", "1"), ("R1", "1")]),
         ("VOUT", [("R1", "2"), ("C1", "1")]),
         ("GND", [("C1", "2"), ("V1", "2"), ("GND1", "1")])],
    ),
    "4. Pull-up Resistor": (
        [("VCC1", "power", "VCC", "+3V3"),
         ("R1", "Device", "R", "10k"),
         ("SW1", "Device", "SW_Push", "BTN"),
         ("GND1", "power", "GND", "GND")],
        [("PWR", [("VCC1", "1"), ("R1", "1")]),
         ("SIG", [("R1", "2"), ("SW1", "1")]),
         ("GND", [("SW1", "2"), ("GND1", "1")])],
    ),
    "5. BJT NPN Switch": (
        [("V1", "Device", "Battery_Cell", "5V"),
         ("R1", "Device", "R", "1k"),
         ("R2", "Device", "R", "10k"),
         ("Q1", "Device", "Q_NPN_BCE", "2N3904"),
         ("D1", "Device", "LED", "LED"),
         ("GND1", "power", "GND", "GND")],
        [("VCC", [("V1", "1"), ("R1", "1"), ("R2", "1")]),
         ("BASE", [("R2", "2"), ("Q1", "2")]),
         ("COLLECTOR", [("R1", "2"), ("D1", "2")]),
         ("EMITTER", [("Q1", "3"), ("GND1", "1")]),
         ("LED_OUT", [("D1", "1"), ("V1", "2")])],
    ),
    "6. Op-Amp Buffer": (
        [("VCC1", "power", "VCC", "+5V"),
         ("VEE1", "power", "VEE", "-5V"),
         ("U1", "Amplifier_Operational", "LM358", "LM358"),
         ("IN1", "Connector", "Conn_01x01_Female", "IN"),
         ("OUT1", "Connector", "Conn_01x01_Female", "OUT"),
         ("GND1", "power", "GND", "GND")],
        [("VCC_PWR", [("VCC1", "1"), ("U1", "8")]),
         ("VEE_PWR", [("VEE1", "1"), ("U1", "4")]),
         ("IN_SIG", [("IN1", "1"), ("U1", "3")]),
         ("FB", [("U1", "1"), ("U1", "2")]),
         ("OUT_SIG", [("U1", "1"), ("OUT1", "1")]),
         ("GND", [("GND1", "1")])],
    ),
    "7. 555 Timer Astable": (
        [("VCC1", "power", "VCC", "+5V"),
         ("U1", "Timer", "NE555P", "NE555"),
         ("R1", "Device", "R", "10k"),
         ("R2", "Device", "R", "100k"),
         ("C1", "Device", "C", "10n"),
         ("C2", "Device", "C", "100n"),
         ("GND1", "power", "GND", "GND")],
        [("VCC", [("VCC1", "1"), ("U1", "8"), ("R1", "1")]),
         ("CHG", [("R1", "2"), ("R2", "1"), ("U1", "7")]),
         ("THR_TRG", [("R2", "2"), ("U1", "6"), ("U1", "2"), ("C1", "1")]),
         ("CTRL", [("U1", "5"), ("C2", "1")]),
         ("GND", [("C1", "2"), ("C2", "2"), ("U1", "1"), ("GND1", "1")])],
    ),
    "8. Full-Bridge Rectifier": (
        [("D1", "Device", "D", "1N4007"),
         ("D2", "Device", "D", "1N4007"),
         ("D3", "Device", "D", "1N4007"),
         ("D4", "Device", "D", "1N4007"),
         ("C1", "Device", "C", "1000u"),
         ("R1", "Device", "R", "1k"),
         ("GND1", "power", "GND", "GND")],
        [("AC1", [("D1", "1"), ("D3", "2")]),
         ("AC2", [("D2", "1"), ("D4", "2")]),
         ("DC+", [("D1", "2"), ("D2", "2"), ("C1", "1"), ("R1", "1")]),
         ("DC-", [("D3", "1"), ("D4", "1"), ("C1", "2"), ("R1", "2"), ("GND1", "1")])],
    ),
    "9. Voltage Regulator 7805": (
        [("V1", "Device", "Battery_Cell", "9V"),
         ("U1", "Regulator_Linear", "L7805", "7805"),
         ("C1", "Device", "C", "10u"),
         ("C2", "Device", "C", "10u"),
         ("D1", "Device", "LED", "PWR"),
         ("R1", "Device", "R", "330Ω"),
         ("GND1", "power", "GND", "GND")],
        [("VIN", [("V1", "1"), ("U1", "1"), ("C1", "1")]),
         ("VOUT", [("U1", "2"), ("C2", "1"), ("R1", "1")]),
         ("LED", [("R1", "2"), ("D1", "1")]),
         ("GND", [("V1", "2"), ("U1", "3"), ("C1", "2"), ("C2", "2"), ("D1", "2"), ("GND1", "1")])],
    ),
    "10. Transistor H-Bridge": (
        [("V1", "Device", "Battery_Cell", "6V"),
         ("Q1", "Device", "Q_NPN_BCE", "NPN"),
         ("Q2", "Device", "Q_NPN_BCE", "NPN"),
         ("Q3", "Device", "Q_PNP_ECB", "PNP"),
         ("Q4", "Device", "Q_PNP_ECB", "PNP"),
         ("R1", "Device", "R", "1k"),
         ("R2", "Device", "R", "1k"),
         ("M1", "Device", "M", "Motor"),
         ("GND1", "power", "GND", "GND")],
        [("VCC", [("V1", "1"), ("Q3", "2"), ("Q4", "2")]),
         ("A_HI", [("Q3", "2"), ("Q1", "3"), ("M1", "1")]),
         ("B_HI", [("Q4", "2"), ("Q2", "3"), ("M1", "2")]),
         ("A_LO", [("Q1", "2"), ("Q3", "3"), ("R1", "1")]),
         ("B_LO", [("Q2", "2"), ("Q4", "3"), ("R2", "1")]),
         ("GND", [("Q1", "1"), ("Q2", "1"), ("R1", "2"), ("R2", "2"), ("V1", "2"), ("GND1", "1")])],
    ),
}

print("=== 10 Test Circuits ===\n")
for name, (components, nets) in circuits.items():
    try:
        build(name, components, nets)
    except Exception as e:
        print(f"  {name:30s} FAILED: {e}")
