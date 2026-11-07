# Shopping list (Bastelgarage)

## Ordered (2026-10-29)

| Article | Used for | Note |
|---|---|---|
| Gravity DS18B20 Sensor Kit | inside sensor + adapter board with pull-up and screw terminals | contains one probe; the second sensor connects to the same terminals |
| IP67 enclosure | electronics | cable glands still needed, see below |
| Neopixel WS2812B RGB LED (420021) | status LED | not delivered; no longer needed, the LCD flashes instead |
| RTC DS3231 module with AT24C32 EEPROM and LIR2032 | clock | delivered; rechargeable cell, insert as is; the EEPROM is not used |

## Available

| Article | Used for | Note |
|---|---|---|
| second DS18B20 | outside sensor | connects to the Gravity adapter terminals |
| 2-Kanal Relais Modul 5V (Bastelgarage 420010) | both pads | remove the JD-VCC jumper for 3.3V logic (WIRING.md) |
| microSD Kartenleser Breakout Modul 3V/5V (play-zone.ch) | SD logging | on 5V; check MISO first (README, Hardware checks) |

## Still open

| Qty | Article | Price | Why |
|---|---|---|---|
| 3–4 | Kabelverschraubung M12 / IP68 | 1.50 | cable glands for supply, pads and sensors into the enclosure |
| 1 | Schottky diode 1N5817 or SS14 | – | in the wire from the 5V supply to VSYS, so USB can't feed the relays and pads (WIRING.md, Power) |
| 1 | 8GB or 16GB MicroSDHC Class 10 | 9.90 / 10.90 | only if you have no card ≤ 32 GB; avoid 64 GB+ (exFAT) |
| 1 | 5V DC 4000mA Stecknetzteil 5.5/2.1mm (or 5000mA) | 15.90 / 18.90 | only if your supply can't run both pads plus ~0.5 A |

## Instead of the relays (optional)

| Qty | Article | Price | Why |
|---|---|---|---|
| 2 | Gravity MOSFET Treiber Modul 10A (421644) | 6.90 | one per pad, 3.3V logic stated, silent. Set `RELAY_ACTIVE_LOW = False` |

Do not use the "IRF520 MOSFET Treiber Modul": it needs 5V logic.
