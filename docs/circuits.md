# 10 Test Circuits — Component Lists

All components from KiCad 10 system libraries (`Device`, `power`).

## 1. LED + Resistor
Battery → current-limiting resistor → LED. The simplest complete circuit.

| Ref | Library:Sym | Value | Pins |
|-----|------------|-------|------|
| BAT1 | Device:Battery_Cell | 3V | 2 |
| R1 | Device:R | 220Ω | 2 |
| D1 | Device:LED | LED | 2 |

Nets: VCC (BAT+ → R1), LED_IN (R1 → LED anode), RTN (LED cathode → BAT−)

---

## 2. Voltage Divider
Two equal resistors split a voltage in half.

| Ref | Library:Sym | Value | Pins |
|-----|------------|-------|------|
| BAT1 | Device:Battery_Cell | 5V | 2 |
| R1 | Device:R | 10k | 2 |
| R2 | Device:R | 10k | 2 |
| G1 | power:GND | GND | 1 |

Nets: VIN (BAT+ → R1), VOUT (R1 → R2), GND (R2 → BAT− → GND)

---

## 3. RC Low-Pass Filter
Resistor + capacitor to ground. Passes low frequencies, attenuates high.

| Ref | Library:Sym | Value | Pins |
|-----|------------|-------|------|
| BAT1 | Device:Battery_Cell | 5V | 2 |
| R1 | Device:R | 1k | 2 |
| C1 | Device:C | 100n | 2 |
| G1 | power:GND | GND | 1 |

Nets: VIN (BAT+ → R1), VOUT (R1 → C1), GND (C1 → BAT− → GND)

---

## 4. R-2R Ladder
Four resistors forming a 2-bit DAC ladder.

| Ref | Library:Sym | Value | Pins |
|-----|------------|-------|------|
| BAT1 | Device:Battery_Cell | 5V | 2 |
| R1 | Device:R | 10k | 2 |
| R2 | Device:R | 10k | 2 |
| R3 | Device:R | 10k | 2 |
| R4 | Device:R | 20k | 2 |
| G1 | power:GND | GND | 1 |

Nets: VCC (BAT+ → R1), N1 (R1 → R2 → R3), N2 (R2 → R4), GND (R3 → R4 → BAT− → GND)

---

## 5. LC Tank
Inductor and capacitor in parallel — resonates at f = 1/(2π√LC).

| Ref | Library:Sym | Value | Pins |
|-----|------------|-------|------|
| L1 | Device:L | 10u | 2 |
| C1 | Device:C | 100n | 2 |
| R1 | Device:R | 1k | 2 |
| G1 | power:GND | GND | 1 |

Nets: TANK_A (L1 → C1 → R1), TANK_B (L1 → C1 → GND), OUT (R1 only)

---

## 6. Diode Clamp
Two diodes clamp a signal to ±0.7V.

| Ref | Library:Sym | Value | Pins |
|-----|------------|-------|------|
| BAT1 | Device:Battery_Cell | 5V | 2 |
| R1 | Device:R | 1k | 2 |
| D1 | Device:D | 1N4148 | 2 |
| D2 | Device:D | 1N4148 | 2 |
| G1 | power:GND | GND | 1 |

Nets: VIN (BAT+ → R1), OUT (R1 → D1 anode → D2 cathode), GND (D1 cathode → D2 anode → BAT− → GND)

---

## 7. Dual LED
Two LEDs with individual current-limiting resistors.

| Ref | Library:Sym | Value | Pins |
|-----|------------|-------|------|
| BAT1 | Device:Battery_Cell | 5V | 2 |
| R1 | Device:R | 220Ω | 2 |
| R2 | Device:R | 220Ω | 2 |
| D1 | Device:LED | RED | 2 |
| D2 | Device:LED | GRN | 2 |
| G1 | power:GND | GND | 1 |

Nets: VCC (BAT+ → R1 → R2), LED1 (R1 → D1 anode), LED2 (R2 → D2 anode), GND (D1 cathode → D2 cathode → BAT− → GND)

---

## 8. Pi Filter
CLC low-pass filter for power supply ripple rejection.

| Ref | Library:Sym | Value | Pins |
|-----|------------|-------|------|
| BAT1 | Device:Battery_Cell | 5V | 2 |
| C1 | Device:C | 10u | 2 |
| L1 | Device:L | 100u | 2 |
| C2 | Device:C | 10u | 2 |
| R1 | Device:R | 1k | 2 |
| G1 | power:GND | GND | 1 |

Nets: VIN (BAT+ → C1 → L1), VOUT (L1 → C2 → R1), GND (C1 → C2 → R1 → BAT− → GND)

---

## 9. Wheatstone Bridge
Four-resistor bridge for precision resistance measurement.

| Ref | Library:Sym | Value | Pins |
|-----|------------|-------|------|
| BAT1 | Device:Battery_Cell | 5V | 2 |
| R1 | Device:R | 1k | 2 |
| R2 | Device:R | 1k | 2 |
| R3 | Device:R | 1k | 2 |
| R4 | Device:R | 1k | 2 |
| G1 | power:GND | GND | 1 |

Nets: VCC (BAT+ → R1 → R3), A (R1 → R2), B (R3 → R4), GND (R2 → R4 → BAT− → GND)

---

## 10. Buck Converter (Concept)
Step-down DC-DC converter topology. Inductor, diode, capacitors.

| Ref | Library:Sym | Value | Pins |
|-----|------------|-------|------|
| BAT1 | Device:Battery_Cell | 12V | 2 |
| C1 | Device:C | 100u | 2 |
| L1 | Device:L | 100u | 2 |
| D1 | Device:D | 1N5819 | 2 |
| C2 | Device:C | 100u | 2 |
| R1 | Device:R | 10 | 2 |
| G1 | power:GND | GND | 1 |

Nets: VIN (BAT+ → C1 → L1), SW (L1 → D1 cathode → C2 → R1), GND (C1 → D1 anode → C2 → R1 → BAT− → GND)
