# Wiring diagram

## Power (read first)

"5V supply" in this file always means the **external 5V power supply** (wall adapter),
never USB. USB-C is only for programming: a PC port gives 0.5–0.9 A, the pads need
more, and their current must not flow through the board.

The board has no 5V output. It is powered from the 5V supply through its VSYS pin and
gives out 3.3V on its 3V3 pin for the small modules.

| 5V supply | goes to |
|---|---|
| + | relay JD-VCC, relay COM1 and COM2, microSD 5V (VCC), board VSYS (pin 39) through a Schottky diode |
| − | relay GND next to JD-VCC, both pads −, microSD GND, board GND |

- Schottky diode (1N5817 or SS14) in the wire from 5V supply + to VSYS, stripe towards
  VSYS. The board already has a diode between USB and VSYS, so the supply can't push
  current into the PC. The extra diode stops the other direction: without it, with the
  supply off (or sagging under pad load) and USB plugged in, the PC's USB port would
  feed the relays and pads. Without the extra diode: keep the 5V supply on whenever USB
  is plugged in.
- USB alone runs only the board and the LCD; the relays and the microSD module have no
  power then (`SD` fault). Switch the 5V supply on for them.
- Use a small terminal block or lever clamps for the + and − rails, and thick wire on
  the pad path (5V supply + → COM → NO → pad → 5V supply −).

## Board pins used

RP2040-LCD-0.96 (Waveshare 20330), pin numbers as on the Raspberry Pi Pico: pin 1 = GP0,
counted down one side and back up the other. Check against the labels on the board.

| Pin | Name | Connect to |
|---|---|---|
| 4 | GP2 | microSD SCK |
| 5 | GP3 | microSD MOSI |
| 6 | GP4 | microSD MISO |
| 7 | GP5 | microSD CS |
| 9 | GP6 | DS3231 SDA |
| 10 | GP7 | DS3231 SCL |
| 20 | GP15 | DS18B20 data |
| 21 | GP16 | relay IN1 |
| 22 | GP17 | relay IN2 |
| 36 | 3V3 (output) | relay VCC (jumper header), DS3231 VCC, DS18B20 adapter VCC (one pin, several wires: use a small terminal) |
| 39 | VSYS (input) | 5V supply + through the Schottky diode |
| 3, 8, 13, 18, 23, 28, 38 | GND | module GNDs, 5V supply − |
| 37 | 3V3_EN | leave open |
| 40 | VBUS | leave open (USB 5V, live only while USB is plugged in) |

The LCD is wired on the board itself: GP8 DC, GP9 CS, GP10 CLK, GP11 DIN, GP12 RST,
GP25 backlight. Don't connect anything else to these.

## DS18B20 (inside + outside on one wire, via the Gravity DS18B20 adapter board)

- Adapter Gravity connector -> board:
  - VCC (red)  -> board 3V3
  - GND (black) -> board GND
  - Data (green/blue) -> GP15
- Both sensors -> adapter screw terminals, two wires per terminal:
  - Gravity probe: red -> VCC, black -> GND, yellow -> Data
  - Second DS18B20, if it is a probe with cable: same colors (check its label)
  - Second DS18B20, if it is a bare 3-leg sensor (TO-92): flat side towards you, legs
    down: left -> GND, middle -> Data, right -> VCC
- The 4.7k pull-up is on the adapter board; no extra resistor. If the second sensor
  sits on its own small board with a resistor, that's fine too.
- Outside sensor: waterproof probe, in the shade, away from the box and the wall.
- Inside sensor: in the air, not touching a pad. Near the lid it reads the warmest
  spot; at battery height is better (see README, Hardware checks).

## Relay module (2-Kanal Relais Modul 5V: optocoupler, JD-VCC jumper, switches on at LOW)

- Remove the jumper between VCC and JD-VCC. The relay coils then run on JD-VCC (5V
  supply) and the inputs on VCC (board 3V3): an input at 3.3V leaves the optocoupler
  fully off.
- Jumper header (all three pins used, the jumper is off):
  - JD-VCC -> 5V supply +
  - VCC (middle) -> board 3V3
  - GND -> GND (common ground)
- Input header:
  - IN1 -> GP16 (pad 1: bottom pad, runs first)
  - IN2 -> GP17 (pad 2: side wall pad)
  - VCC and GND: leave open. On this module they are the same connections as VCC and
    GND on the jumper header (check with the meter: continuity between the two VCC pins
    and between the two GND pins).
- Check that each relay clicks at 0V and releases at 3.3V on IN (see README, Hardware
  checks). Only if a relay does not click (its LED may light dimly): put the jumper
  back **and remove the 3V3 wire from VCC** (VCC then gets 5V through the jumper; with
  both connected the 5V supply would push into the board's 3.3V). Then check again
  that it releases at 3.3V.
- Contacts: 5V supply + -> COM1 and COM2, NO1 -> pad 1 +, NO2 -> pad 2 +, both pads −
  -> 5V supply −. NC stays open.
- Gravity MOSFET modules instead: signal -> GP16 / GP17, module VIN/GND -> 5V supply,
  pad on the module output; set `RELAY_ACTIVE_LOW = False` in config.py.

## microSD breakout module (SPI0, voltage regulator and level shifter on the module)

- 5V (VCC) -> 5V supply +
- GND -> 5V supply − / board GND
- 3.3V -> leave open
- SCK  -> GP2
- MOSI -> GP3
- MISO -> GP4
- CS   -> GP5
- Measure MISO before connecting it (README, Hardware checks). Only if it shows about
  5V: power the module from the board instead (board 3V3 -> module 3.3V pin, module 5V
  pin open).

## DS3231 RTC module (with AT24C32 EEPROM, usually labeled ZS-042), I2C1

- VCC -> board 3V3 (then its pull-ups on SDA/SCL are at 3.3V, safe for the RP2040)
- GND -> board GND
- SDA -> GP6
- SCL -> GP7
- 32K, SQW: leave open. The EEPROM (address 0x57) shares the bus and is not used.
- Battery: LIR2032 (rechargeable), insert as is. Never use a normal CR2032 in this
  module without removing the charging resistor (marked 201).
- At 3.3V the module's charging circuit hardly charges the LIR2032 (it needs 4.2V).
  That is fine: the cell only runs the clock during power cuts. Do not move VCC to the
  5V supply to charge it, SDA/SCL would then be pulled up to 5V.

## Enclosure (IP67)

- LCD facing the window side, through a transparent lid: it shows the status, and the
  whole screen flashes yellow or red on a problem.
- Cables through cable glands on the bottom side, so water runs off.
- A small desiccant bag inside helps against condensation in winter.

## Notes

- All grounds are connected: 5V supply −, board GND and every module GND.
- GP18 is free (it was reserved for a status LED).
