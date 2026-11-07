# Akkubox Heizung (RP2040-LCD)

MicroPython firmware that keeps a LiPo storage box on the balcony warm (LiPos should
stay above ~5 °C). It measures the inside and outside temperature with two DS18B20
sensors, switches two 5V reptile heat pads via relays, logs to SD, and shows the status
on the RP2040-LCD-0.96. On a problem the whole screen flashes yellow or red, visible
through the window.

The board runs on its own; a PC is only needed to install the firmware and to set the
clock once.

To build and start it, follow [First-time setup](#first-time-setup) step by step.
Parts to buy: [shopping.md](shopping.md).

## Features

Heating control
- Two stages with an on/off gap (hysteresis) on both, controlled by the inside temperature:

  | Inside temperature | Pads |
  |---|---|
  | falls to `T_STAGE1_ON` (13 °C) | stage 1: pad 1 (bottom) |
  | falls to `T_STAGE2_ON` (10 °C) | stage 2: both pads |
  | rises to `T_STAGE2_OFF` (12 °C) | back to stage 1 |
  | rises to `T_OFF` (15 °C) | off |

- Pad 1 (relay 1) is the bottom pad and runs first: it heats the batteries, and the warm
  air rises to the sensor. Pad 2 (side wall) only helps when it gets colder.
  `ROTATE_PADS = True` alternates the pads instead.
- Use the stronger pad (the one drawing more current at 5V) as pad 1, at the bottom on
  relay 1: it runs most of the time. Here: 1.23 A (6.2 W) as pad 1, 0.65 A (3.3 W) as
  pad 2.
- Measuring and switching: both sensors are read once a minute (`LOOP_INTERVAL_S`), and
  the relays can only change at that moment, so at most once a minute. The 2 °C gap
  between on and off (stage 1: 13/15 °C, stage 2: 10/12 °C) keeps switching much rarer.
  The display also updates once a minute. The 5 minutes (`LOG_INTERVAL_S`) are only the
  log interval: each log line has the average, minimum and maximum of the last 5
  readings.
- Fallback: inside sensor lost → control on the outside temperature (heats more, never
  less). Both sensors lost → `FAILSAFE_STAGE` (default: both pads on).
- The outside sensor has no influence on normal heating, which uses the inside
  temperature only. It serves as the fallback above and for information on the display
  and in the logs: comparing inside and outside shows how well the box holds its heat
  and how much reserve the pads have.
- Relays can be disabled individually; active-low relay modules are supported.

Fault handling
- Every control cycle runs in its own error handler. An error is logged and the next
  cycle runs normally; after `MAX_CONSECUTIVE_ERRORS` in a row the board resets.
- Hardware watchdog (8 s): a hang (e.g. a stuck SD card) resets the board.
- A fatal error outside the control loop switches to failsafe heating with a red
  flashing screen for 10 minutes, then resets.
- Sensors: a bad reading (CRC error, disconnected, 85 °C power-on value) is ignored;
  after `SENSOR_FAIL_COUNT` bad reads in a row the sensor counts as lost. The bus is
  re-scanned every 10 minutes while a sensor is missing.
- SD card: on a write error the card is unmounted and remounted every 10 minutes.
  Events are kept in RAM meanwhile (up to 100), lost measurement lines are counted.
- RTC: copied to the internal clock at boot and every hour. If the RTC fails, the
  internal clock keeps running.
- A heater that stopped working shows up as falling temperatures: stage 2 more often
  in the logs, and `COLD` below 5 °C.
- Ctrl-C (also when `mpremote` connects) disables the watchdog and switches the pads
  off, so the REPL stays usable.

Status signal (LCD, visible through the window)

| Screen | Meaning |
|---|---|
| green bar at the bottom, no flashing | all OK |
| blue bar at the bottom, no flashing | all OK, inside below `STATUS_TEMP` (info only) |
| whole screen flashes yellow every 10 s | warning: check when convenient |
| whole screen flashes red every 10 s | alarm: check now |
| color test (red, green, blue blocks) | starting up |
| `FATAL ERROR`, flashes red | failsafe heating, resets after 10 minutes |
| `Stopped (REPL)` | stopped by Ctrl-C / `mpremote`, pads off |
| dark | no power: check now |

A new fault flashes at once, then every `FLASH_INTERVAL_S` for `FLASH_MS`. A hung
firmware is reset by the watchdog; the clock on the screen shows whether it updates.

Display (0.96" LCD), updated once a minute

```
21:43  now  min  max
In    14.2 12.8 15.1
Out   -3.5 -4.2  2.0
Stage 1 in     [1][2]
Night pads  3.1h 0.4h
[######## OK ########]
```

- Clock, then inside and outside temperature: `now`, and `min`/`max` of the night
  (20:00–08:00). During the night it shows the running night, by day the last
  complete night.
- Heating stage and control source (`in`, `out`, `failsafe`), pad boxes (red = heating).
- `Night pads`: how long pad 1 and pad 2 heated in that night. Close to 12 h means the
  pads have no reserve left.
- Status bar over the full width: green OK, blue OK but below `STATUS_TEMP`, yellow
  warning, red alarm. The active fault codes are written into it; with many codes it
  grows to two lines.
- The night values are kept in RAM: after a restart by day they show `--.-` until the
  next night.
- At boot: color test (red, green, blue blocks) and a white frame to check the offsets.

Logging (SD card)
- `/sd/log/YYYYMMDD.csv`, one file per day, a line every 5 minutes:
  `timestamp,uptime_s,t_in,t_in_min,t_in_max,t_out,t_out_min,t_out_max,pad1_on_s,pad2_on_s,stage,source,faults`
  (average/min/max over the interval, heater on-time in seconds).
- `/sd/events.csv`: boot with reset cause, sensor ROM ids, every relay change, fault
  set/clear, SD recovery, errors with message. At 08:00 a `NIGHT` line with the night's
  inside/outside min and max and the heating hours per pad:
  `2026-11-08 08:00:41,52860,NIGHT,in_min=12.80 in_max=15.10 out_min=-4.20 out_max=2.00 pad1_h=3.10 pad2_h=0.40`.
- `/sd/daily.csv`: one line per day: min/max inside and outside, on-hours per pad,
  all faults of the day.
- Timestamps are local time (CET/CEST, switches automatically). The night of the
  October switch has a 25-hour day, the March one a 23-hour day.
- Every event is also printed on the USB console (ignored when no PC is connected).
- Without valid time the timestamp column stays empty (`uptime_s` still orders the
  lines) and measurements go to `nodate.csv`.

## Fault codes

| Code | Level | Meaning | What to check |
|---|---|---|---|
| `COLD` | alarm | inside below `T_ALARM_LOW` (5 °C) | heaters, 5V supply, relays, box lid |
| `HOT` | alarm | inside above `T_ALARM_HIGH` (40 °C) | sun on the box, shade it |
| `SENS_IN` | alarm | inside sensor lost (heating runs on outside sensor / failsafe) | sensor cable |
| `SENS_OUT` | warning | outside sensor lost | sensor cable |
| `SD` | warning | SD card missing or write failed | card, reinsert |
| `RTC` | warning | RTC unreadable, stopped or not set | coin cell, [set the time](#setting-the-time) |
| `ERR` | warning | a control cycle failed in the last hour | `events.csv` |
| `RESET` | warning | board restarted by the watchdog in the last 6 h | `events.csv` |

## First-time setup

Do the steps in this order. Steps 1–3 need no power on the board.

### 1. Prepare the PC

- Install Python, then `pip install mpremote`.
- Download the MicroPython firmware for the Raspberry Pi Pico (v1.22 or newer,
  `RPI_PICO-....uf2`) from https://micropython.org/download/RPI_PICO/. The RP2040-LCD
  uses the same firmware. `onewire` and `ds18x20` are built in.
- Open a terminal in this project folder; all `mpremote` commands below are run from
  here. `mpremote` finds the board by itself; with several boards connected use
  `mpremote connect COM5 ...`.

### 2. Prepare the SD card

- Format it as FAT32 (Windows: right-click the card → Format → FAT32; works for cards
  up to 32 GB). The firmware creates the `log` folder and files itself.

### 3. Check the hardware before wiring

Go through [Hardware checks](#hardware-checks-before-wiring), then wire everything as in
[WIRING.md](WIRING.md). Leave the pads disconnected for now if you like; the relays
work without them.

### 4. Flash MicroPython

Hold the BOOT button on the board, plug in USB, release. A drive `RPI-RP2` appears;
copy the `.uf2` file onto it. The board restarts with MicroPython.

From here on, switch the external 5V supply on while USB is connected: USB alone powers
only the board, not the relays and the microSD module (WIRING.md, Power).

### 5. Copy the firmware

```
mpremote cp main.py config.py heating.py sensors.py status.py datalog.py settime.py sensorid.py :
mpremote mkdir :lib
mpremote cp lib/ds3231.py lib/sdcard.py lib/st7789.py :lib/
```

If an older version is on the board, remove its leftovers:
`mpremote rm :boot.py`, `mpremote rm :sd_boot_fail` and `mpremote rm :lib/ds1307.py`.

`main.py` runs at every power-up and after `mpremote reset`. Any other `mpremote`
command stops it (watchdog off, pads off) until the next reset; that is normal.

### 6. Set the time

See [Setting the time](#setting-the-time). One command.

### 7. Assign the sensors

Tell the firmware which sensor is inside and which is outside (both connected):

1. Show all sensors with their live temperature (runs 1 minute):

   ```
   mpremote exec "import sensorid"
   ```

   Output, one line every 2 seconds:

   ```
   found 2 sensor(s)
   "28ff641e80160495" 18.50 C   "28aa3c1d0b00007f" 18.44 C
   ```

2. Hold the inside sensor in your hand. The id whose temperature rises is the
   inside one.
3. Enter both ids in `config.py`:

   ```python
   SENSOR_IN_ROM = "28ff641e80160495"
   SENSOR_OUT_ROM = "28aa3c1d0b00007f"
   ```

Without this the scan order decides, and a sensor missing at boot can swap inside and
outside. The ids are also written to `events.csv` at every boot (`SENSORS` line).

### 8. Check config.py

- `RELAY_ACTIVE_LOW`: `True` for the 2-channel relay module (switches on at 0 V),
  `False` for MOSFET modules.
- Thresholds (`T_STAGE1_ON` etc.) and `FLASH_INTERVAL_S` can stay as they are for now.

Copy it to the board: `mpremote cp config.py :`

### 9. Test the relays

Room temperature is above the heating thresholds, so the pads stay off in normal
operation. Switch each one on for 5 seconds by hand (relay clicks, its LED lights):

```
mpremote exec "from machine import Pin; import time; r = Pin(16, Pin.OUT, value=1); r(0); time.sleep(5); r(1)"
mpremote exec "from machine import Pin; import time; r = Pin(17, Pin.OUT, value=1); r(0); time.sleep(5); r(1)"
```

(16 = pad 1, 17 = pad 2. With MOSFET modules swap the values: `value=0`, `r(1)` on,
`r(0)` off.)

### 10. First start

`mpremote reset`. What you should see:

1. The LCD shows the color test: red, green, blue blocks and a white frame around the
   edge. Wrong colors or a cut-off frame: see [LCD settings](#lcd-settings).
2. After a few seconds the normal screen: inside/outside temperature, clock,
   `Stage 0 in`. By day, the night values show `--.-` until 20:00.
3. Green bar at the bottom with `OK`, no flashing.

Yellow or red instead of `OK` (and the screen flashes every 10 s): the fault code on
the LCD tells you what is missing, see [Fault codes](#fault-codes). Typical first-start
faults are `SD` (card not inserted or not FAT32), `RTC` (time not set) and
`SENS_OUT`/`SENS_IN` (wiring, step 7).

Optional, to watch it work: `mpremote repl` shows the events live without stopping the
program (exit with Ctrl-X; the program keeps running only if you exit without pressing
Ctrl-C).

### 11. Install

Unplug USB. The board now runs on its 5V supply alone. Mount the box with the LCD
facing the window, place the sensors (outside in the shade, inside at battery height), connect the
pads (the stronger pad at the bottom, on relay 1). After a day, check the logs (see below).

## Reading the logs

1. Switch off the 5V supply (the card is written every 5 minutes; pulling it while
   powered can corrupt a file).
2. Take out the SD card and read it on the PC: `log/YYYYMMDD.csv`, `events.csv`,
   `daily.csv` (open with Excel or LibreOffice, separator comma).
3. Put the card back, switch on.

If you do pull the card while running, the firmware shows `SD`, keeps the events in
memory and remounts the card within 10 minutes after it is back.

## Changing settings later

Connect USB, edit `config.py` on the PC, `mpremote cp config.py :`, `mpremote reset`.

## LCD settings

If the color test at boot is wrong: toggle `LCD_BGR` (red and blue swapped), then
`LCD_INVERT` (colors inverted). If the white frame is cut off or there are garbage
lines at an edge: adjust `LCD_XSTART` / `LCD_YSTART` (try 0/24, 1/26, 0/0) or
`LCD_ROTATION` (1 or 3).

## Setting the time

The DS3231 keeps the time on its coin cell while the box has no power.
It holds UTC; the firmware adds the time zone and switches between winter and summer
time by itself (`UTC_OFFSET_H`, `DST_EU` in `config.py`). So you only set it once.

1. Connect the board to the PC with USB. The 5V supply may stay on (see
   [WIRING.md](WIRING.md), Power).
2. Send the PC's current UTC time to the RTC:

   Windows (PowerShell):
   ```
   mpremote exec "import settime; settime.set_unix($([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()))"
   ```
   macOS / Linux:
   ```
   mpremote exec "import settime; settime.set_unix($(date +%s))"
   ```
   It prints `RTC set to ... UTC` (one hour behind CET, two behind CEST).
3. During first-time setup: continue with step 7. Later: `mpremote reset`, unplug USB,
   check the clock on the LCD.

Set it again only after replacing the coin cell, when `RTC` shows up, or if the clock
is off by more than a few minutes (DS3231: about 1 minute per year). `RTC` also shows
up when the clock stopped once, e.g. a power cut with a flat coin cell; setting the
time clears it.

## Hardware checks (before wiring)

Details in [WIRING.md](WIRING.md).

1. **DS3231** – power it from 3.3V, then SDA/SCL are 3.3V. Battery: LIR2032
   (rechargeable); at 3.3V the module hardly charges it, which is fine for a backup.
2. **SD module MISO** – the RP2040 pins are not 5V tolerant. Power the microSD module
   from the 5V supply with only VCC and GND connected and a card inserted, then measure MISO to
   GND: it must stay below 3.6 V. If it shows about 5 V, power the module from its
   3.3V pin instead (WIRING.md).
3. **Relays at 3.3V** – with the JD-VCC jumper removed (WIRING.md), drive each relay
   input from the board: it must click at 0 V and release reliably at 3.3 V. If it
   does not click, see the fallback in WIRING.md, or use MOSFET modules.
4. **5V power budget** – measure the current of both pads together. The 5V supply must
   deliver that plus ~0.5 A for board and relays. Pad current must not flow through
   the board or its USB connector: wire the pads directly from the supply.
5. **Free pins** – check that GP2–GP7 and GP15–GP17 are broken out on your board
   revision.

After the first start:

6. **Status signal visibility** – check from the window position by day that the
   yellow flash is visible: unplug the outside sensor, after about 3 minutes `SENS_OUT`
   appears and the screen flashes every 10 s. Plug it back in.
7. **Sensors** – the outside one reads plausible values in the sun and in the shade.
8. **Sensor position** – the inside sensor near the lid reads the warmest spot while
   heating. Compare it once with a thermometer at the batteries; if the batteries are
   much colder, move the sensor down or raise the thresholds.

## Load on the RP2040

The control cycle runs once per minute and takes about 1 s, most of it waiting for the
DS18B20 conversion (750 ms). In between the board only times the LCD flash (one
screen transfer of ~25 ms at the start and end of a flash). RAM: the
display buffer needs 25 KB, the rest a few KB, out of ~190 KB free for MicroPython
(`mem_free` is logged at every boot). Optionally precompile the files with `mpy-cross`
to speed up the start.

## Files

| File | Content |
|---|---|
| `main.py` | setup, main loop, display, logging, fault evaluation, local time |
| `config.py` | all thresholds, pins and timings |
| `heating.py` | stage control |
| `sensors.py` | DS18B20 reading, fault counting, re-scan |
| `status.py` | fault list and LCD flash |
| `datalog.py` | SD mount/remount, CSV files |
| `settime.py` | sets the RTC to UTC |
| `sensorid.py` | lists the sensor ids with live temperatures (setup) |
| `lib/` | drivers: official `sdcard.py`, `ds3231.py`, `st7789.py` (also ST7735S) |
