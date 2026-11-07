# Akkubox Heizung: keeps a LiPo storage box warm with two 5V heat pads.
# See README.md for behavior, status signal and log format.

import gc
import sys
import time
import framebuf
import machine
from machine import Pin, SPI, I2C

import config
import heating
import sensors
import status
from datalog import DataLog
from lib import ds3231
from lib import st7789

VERSION = "2.4"
TICK_MS = 50
RESET_WARN_S = 6 * 3600  # an unexpected (watchdog) reset is shown as warning this long
ERROR_HOLD_S = 3600      # ERR stays active this long after the last failed loop cycle
FATAL_FAILSAFE_S = 600   # after a fatal error: heat in failsafe mode this long, then reset


def rgb565(r, g, b):
    # framebuf stores pixels little-endian, the panel expects big-endian: swap bytes
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((c & 0xFF) << 8) | (c >> 8)


def relay_level(on):
    if config.RELAY_ACTIVE_LOW:
        return 0 if on else 1
    return 1 if on else 0


def fmt(t, empty="", decimals=2):
    if t is None:
        return empty
    return ("%0." + str(decimals) + "f") % t


def fmt_lcd(t):
    return fmt(t, "--.-", config.TEMP_DECIMALS)


def fmt_hours(s):
    # Seconds as hours, at most 4 characters: "3.1h", "12h"
    if s is None:
        return "--"
    h = s / 3600
    return ("%.1fh" if h < 9.95 else "%.0fh") % h


def is_night(hour):
    return hour >= 20 or hour < 8


class Agg:
    def __init__(self):
        self.n = 0
        self.total = 0.0
        self.min = None
        self.max = None

    def add(self, v):
        if v is None:
            return
        self.n += 1
        self.total += v
        if self.min is None or v < self.min:
            self.min = v
        if self.max is None or v > self.max:
            self.max = v

    def avg(self):
        return self.total / self.n if self.n else None


class Stats:
    def __init__(self):
        self.t_in = Agg()
        self.t_out = Agg()
        self.on_s = [0.0, 0.0]


# Monotonic uptime in ms. time.ticks_ms() wraps after ~12 days on the RP2040.
_mono = 0
_last_ticks = time.ticks_ms()


def mono_ms():
    global _mono, _last_ticks
    now = time.ticks_ms()
    _mono += time.ticks_diff(now, _last_ticks)
    _last_ticks = now
    return _mono


class Schedule:
    """Due every interval_s. With a valid clock at round clock times (full minutes,
    :00/:05/...), otherwise by uptime. A slot never repeats, so a clock set back a
    little by the RTC sync does not run a cycle twice."""

    def __init__(self, interval_s):
        self.interval_s = interval_s
        self.slot = None
        self.next_ms = 0

    def due(self, now_ms):
        if time_valid:
            slot = time.time() // self.interval_s
            if self.slot is not None and slot <= self.slot:
                return False
            self.slot = slot
            return True
        if now_ms < self.next_ms:
            return False
        self.next_ms = now_ms + self.interval_s * 1000
        return True


# Colors
BLACK = rgb565(0, 0, 0)
WHITE = rgb565(255, 255, 255)
RED = rgb565(220, 40, 40)
GREEN = rgb565(40, 200, 80)
BLUE = rgb565(40, 120, 200)
YELLOW = rgb565(255, 255, 0)  # pure yellow looks yellow on the tuned panel
DARK = rgb565(50, 50, 50)
GRAY = rgb565(140, 140, 140)
LEVEL_COLORS = {status.OK: GREEN, status.WARN: YELLOW, status.ALARM: RED}
BAR_H = 12  # status bar at the bottom of the LCD, one text line; grows for 2 lines
COL_NOW, COL_MIN, COL_MAX = 68, 112, 156  # right edges of the table columns (px)

# Hardware and state, filled in by setup()
relay_pins = [None, None]
wdt = None
flash = None
lcd = None
fb = None
buf = None
ext_rtc = None
sens = None
heat = None
datalog = DataLog(config)

time_valid = False
prev_relays = [False, False]
last_cycle_ms = None
interval = Stats()
day_stats = Stats()
cur_day = None
cycle_schedule = Schedule(config.LOOP_INTERVAL_S)
log_schedule = Schedule(config.LOG_INTERVAL_S)
next_rtc_ms = 0
next_sd_ms = 0
next_scan_ms = 0
reset_warn_until_ms = 0
reset_cause = ""
consecutive_errors = 0
last_error_ms = None
night = None       # Stats of the running night (20:00-08:00), None by day
last_night = None  # Stats of the last complete night
last_t_in = None
last_t_out = None


def log_event(kind, detail=""):
    detail = str(detail).replace(",", ";").replace("\n", " ")
    line = "%s,%d,%s,%s\n" % (timestamp(), mono_ms() // 1000, kind, detail)
    print(line, end="")
    datalog.event(line)


faults = status.Faults(log_event)


def feed():
    if wdt is not None:
        wdt.feed()


def disable_wdt():
    # machine.WDT cannot be stopped. Clear the RP2040 watchdog ENABLE bit (CTRL bit 30)
    # through the atomic-clear register alias so the REPL stays usable after Ctrl-C.
    try:
        machine.mem32[0x40058000 | 0x3000] = 1 << 30
    except Exception:
        pass


def set_relays(on):
    for pin, state in zip(relay_pins, on):
        if pin is not None:
            pin.value(relay_level(state))


def reset_cause_name():
    cause = machine.reset_cause()
    for name in ("PWRON_RESET", "HARD_RESET", "WDT_RESET", "DEEPSLEEP_RESET", "SOFT_RESET"):
        if getattr(machine, name, None) == cause:
            return name
    return str(cause)


# ---------------------------------------------------------------- time

def sync_time():
    """Copy the external RTC (UTC) to the internal clock. Returns True on success."""
    global time_valid
    if ext_rtc is None:
        return False
    try:
        if ext_rtc.halted():
            return False
        dt = ext_rtc.datetime()
    except Exception:
        return False
    year, month, mday, weekday, hour, minute, sec, _ = dt
    if not (2024 <= year <= 2099 and 1 <= month <= 12 and 1 <= mday <= 31 and hour < 24):
        return False
    machine.RTC().datetime((year, month, mday, (weekday - 1) % 7, hour, minute, sec, 0))  # RTC weekday 1-7
    time_valid = True
    return True


def _last_sunday_1utc(year, month):
    # 01:00 UTC on the last Sunday of a 31-day month (March, October)
    t = time.mktime((year, month, 31, 1, 0, 0, 0, 0))
    return t - ((time.gmtime(t)[6] + 1) % 7) * 86400  # gmtime weekday: Monday = 0


def local_time():
    """Local time tuple. The internal clock runs on UTC."""
    t = time.time()
    offset = config.UTC_OFFSET_H
    if config.DST_EU:
        year = time.gmtime(t)[0]
        if _last_sunday_1utc(year, 3) <= t < _last_sunday_1utc(year, 10):
            offset += 1
    return time.gmtime(t + offset * 3600)


def timestamp():
    if not time_valid:
        return ""
    return "%04d-%02d-%02d %02d:%02d:%02d" % local_time()[:6]


def today():
    if not time_valid:
        return "nodate"
    return "%04d%02d%02d" % local_time()[:3]


def update_night(t_in, t_out):
    """Night statistics. Returns the Stats to show: the running night, by day the last
    complete night (None if there is none yet). The heater on-time is added in
    control_cycle()."""
    global night, last_night
    if not time_valid:
        return None
    if is_night(local_time()[3]):
        if night is None:
            night = Stats()
        night.t_in.add(t_in)
        night.t_out.add(t_out)
        return night
    if night is not None:
        last_night = night
        night = None
        log_event("NIGHT", "in_min=%s in_max=%s out_min=%s out_max=%s pad1_h=%.2f pad2_h=%.2f" % (
            fmt(last_night.t_in.min), fmt(last_night.t_in.max),
            fmt(last_night.t_out.min), fmt(last_night.t_out.max),
            last_night.on_s[0] / 3600, last_night.on_s[1] / 3600))
    return last_night


# ---------------------------------------------------------------- display

def splash():
    # Color check: the three blocks must show red, green and blue in that order.
    # If not, adjust LCD_BGR / LCD_INVERT in config.py.
    fb.fill(BLACK)
    fb.text("Akkubox v" + VERSION, 0, 0, WHITE)
    for i, (color, label) in enumerate(((rgb565(255, 0, 0), "R"), (rgb565(0, 255, 0), "G"),
                                        (rgb565(0, 0, 255), "B"))):
        fb.fill_rect(i * 54, 16, 50, 36, color)
        fb.text(label, i * 54 + 21, 30, BLACK)
    fb.text("starting...", 0, 60, WHITE)
    fb.rect(0, 0, config.LCD_WIDTH, config.LCD_HEIGHT, WHITE)  # frame shows the offset
    lcd.blit_buffer(buf, 0, 0, config.LCD_WIDTH, config.LCD_HEIGHT)


def rtext(s, x_right, y, color):
    # Text right-aligned at x_right (8x8 font)
    fb.text(s, x_right - 8 * len(s), y, color)


def bar_lines(codes):
    # Fault codes wrapped to the bar width (20 characters), at most 2 lines
    lines = []
    for code in codes:
        if lines and len(lines[-1]) + 1 + len(code) <= 20:
            lines[-1] += " " + code
        else:
            lines.append(code)
    return lines[:2] or ["OK"]


def draw_ui(t_in, t_out, nt):
    # Table: now and night min/max (this night, by day the last one), see README Display
    w = config.LCD_WIDTH
    level = faults.level()
    fb.fill(BLACK)

    fb.text("%02d:%02d" % local_time()[3:5] if time_valid else "--:--", 0, 0, WHITE)
    for label, x in (("now", COL_NOW), ("min", COL_MIN), ("max", COL_MAX)):
        rtext(label, x, 0, GRAY)
    for y, label, t, agg in ((11, "In", t_in, nt and nt.t_in), (22, "Out", t_out, nt and nt.t_out)):
        fb.text(label, 0, y, WHITE)
        rtext(fmt_lcd(t), COL_NOW, y, WHITE)
        rtext(fmt_lcd(agg and agg.min), COL_MIN, y, WHITE)
        rtext(fmt_lcd(agg and agg.max), COL_MAX, y, WHITE)

    fb.text("Stage %d %s" % (heat.stage, heat.source), 0, 33, WHITE)
    for p in (0, 1):
        x = w - 30 + p * 16
        fb.fill_rect(x, 32, 14, 10, RED if prev_relays[p] else DARK)
        fb.text(str(p + 1), x + 3, 33, WHITE)

    fb.text("Night pads", 0, 44, GRAY)
    rtext("%s %s" % (fmt_hours(nt and nt.on_s[0]), fmt_hours(nt and nt.on_s[1])), COL_MAX, 44, WHITE)

    # Status bar, full width; the fault codes are written into it
    bar = LEVEL_COLORS[level]
    if level == status.OK and t_in is not None and t_in < config.STATUS_TEMP:
        bar = BLUE
    lines = bar_lines(faults.codes())
    top = config.LCD_HEIGHT - BAR_H - 11 * (len(lines) - 1)
    fb.fill_rect(0, top, w, config.LCD_HEIGHT - top, bar)
    for i, line in enumerate(lines):
        fb.text(line, (w - 8 * len(line)) // 2, top + 2 + 11 * i,
                BLACK if bar in (GREEN, YELLOW) else WHITE)

    lcd.blit_buffer(buf, 0, 0, config.LCD_WIDTH, config.LCD_HEIGHT)


def show_message(color, *lines):
    # Full-screen notice (fatal error, stopped) instead of the UI
    if lcd is None:
        return
    try:
        fb.fill(BLACK)
        for i, line in enumerate(lines):
            fb.text(line, 0, i * 12, color if i == 0 else WHITE)
        fb.fill_rect(0, config.LCD_HEIGHT - BAR_H, config.LCD_WIDTH, BAR_H, color)
        lcd.blit_buffer(buf, 0, 0, config.LCD_WIDTH, config.LCD_HEIGHT)
    except Exception:
        pass


def update_flash(level):
    if flash is not None:
        try:
            flash.update(level, mono_ms())
        except Exception:
            pass


def end_flash():
    if flash is not None:
        try:
            flash.end()
        except Exception:
            pass


# ---------------------------------------------------------------- logging

def write_measurement(now):
    s = interval
    line = "%s,%d,%s,%s,%s,%s,%s,%s,%d,%d,%d,%s,%s\n" % (
        timestamp(), now // 1000,
        fmt(s.t_in.avg()), fmt(s.t_in.min), fmt(s.t_in.max),
        fmt(s.t_out.avg()), fmt(s.t_out.min), fmt(s.t_out.max),
        int(s.on_s[0]), int(s.on_s[1]), heat.stage, heat.source,
        " ".join(faults.codes()),
    )
    datalog.measurement(today(), line)


def write_daily(day):
    d = day_stats
    line = "%s-%s-%s,%s,%s,%s,%s,%.2f,%.2f,%s\n" % (
        day[:4], day[4:6], day[6:],
        fmt(d.t_in.min), fmt(d.t_in.max), fmt(d.t_out.min), fmt(d.t_out.max),
        d.on_s[0] / 3600, d.on_s[1] / 3600,
        " ".join(sorted(faults.seen)),
    )
    datalog.daily(line)


# ---------------------------------------------------------------- setup

def setup():
    global wdt, flash, lcd, fb, buf, ext_rtc, sens, heat
    global reset_warn_until_ms, reset_cause

    # Relays first, off until the first control cycle
    if config.RELAY1_ENABLED:
        relay_pins[0] = Pin(config.RELAY1_PIN, Pin.OUT, value=relay_level(False))
    if config.RELAY2_ENABLED:
        relay_pins[1] = Pin(config.RELAY2_PIN, Pin.OUT, value=relay_level(False))

    if config.WDT_ENABLED:
        wdt = machine.WDT(timeout=config.WDT_TIMEOUT_MS)

    try:
        lcd_spi = SPI(config.LCD_SPI_ID, baudrate=config.LCD_BAUD, polarity=0, phase=0,
                      sck=Pin(config.LCD_SCK), mosi=Pin(config.LCD_MOSI))
        lcd = st7789.ST7789(
            lcd_spi, config.LCD_WIDTH, config.LCD_HEIGHT,
            dc=Pin(config.LCD_DC, Pin.OUT), cs=Pin(config.LCD_CS, Pin.OUT),
            rst=Pin(config.LCD_RST, Pin.OUT), bl=Pin(config.LCD_BL, Pin.OUT),
            xstart=config.LCD_XSTART, ystart=config.LCD_YSTART, rotation=config.LCD_ROTATION,
            bgr=config.LCD_BGR, invert=config.LCD_INVERT,
        )
        buf = bytearray(config.LCD_WIDTH * config.LCD_HEIGHT * 2)
        fb = framebuf.FrameBuffer(buf, config.LCD_WIDTH, config.LCD_HEIGHT, framebuf.RGB565)
        splash()
        flash = status.ScreenFlash(lcd, buf, LEVEL_COLORS, config.FLASH_INTERVAL_S * 1000,
                                   config.FLASH_MS)
    except Exception as exc:
        lcd = None
        print("LCD init failed:", exc)
    feed()

    try:
        i2c = I2C(config.I2C_ID, scl=Pin(config.I2C_SCL), sda=Pin(config.I2C_SDA), freq=config.I2C_FREQ)
        ext_rtc = ds3231.DS3231(i2c)
    except Exception as exc:
        print("RTC init failed:", exc)
    sync_time()
    feed()

    datalog.mount()
    feed()

    reset_cause = reset_cause_name()
    log_event("BOOT", "v%s reset=%s mem_free=%d" % (VERSION, reset_cause, gc.mem_free()))
    if reset_cause == "WDT_RESET":
        reset_warn_until_ms = mono_ms() + RESET_WARN_S * 1000
    if not datalog.ok:
        log_event("SD_FAIL", datalog.error)

    sens = sensors.Sensors(config, Pin(config.ONEWIRE_PIN))
    log_event("SENSORS", "found=%s in=%s%s out=%s%s" % (
        " ".join(sensors.rom_hex(r) for r in sens.found),
        sensors.rom_hex(sens.inside.rom), "" if sens.inside.fixed else "(scan)",
        sensors.rom_hex(sens.outside.rom), "" if sens.outside.fixed else "(scan)",
    ))
    feed()

    pads = [i for i, pin in enumerate(relay_pins) if pin is not None]
    heat = heating.Heating(config, pads)


# ---------------------------------------------------------------- control cycle

def control_cycle(now):
    global prev_relays, last_cycle_ms, interval, day_stats, cur_day
    global next_rtc_ms, next_sd_ms, next_scan_ms, last_t_in, last_t_out

    if (sens.inside.value is None or sens.outside.value is None) and now >= next_scan_ms:
        next_scan_ms = now + config.SENSOR_RESCAN_S * 1000
        sens.scan()
    t_in, t_out = sens.read()
    last_t_in, last_t_out = t_in, t_out
    feed()
    faults.set("SENS_IN", t_in is None, status.ALARM, sensors.rom_hex(sens.inside.rom))
    faults.set("SENS_OUT", t_out is None, status.WARN, sensors.rom_hex(sens.outside.rom))

    # Heater on-time of the period since the last cycle, with the relay state of that period
    if last_cycle_ms is not None:
        dt_s = (now - last_cycle_ms) / 1000
        for p in (0, 1):
            if prev_relays[p]:
                for s in (interval, day_stats, night):
                    if s is not None:
                        s.on_s[p] += dt_s
    last_cycle_ms = now

    prev_stage = heat.stage
    prev_source = heat.source
    relays = heat.update(t_in, t_out)
    set_relays(relays)
    if heat.source != prev_source:
        log_event("SOURCE", heat.source)
    if relays != prev_relays:
        log_event("STAGE", "%d->%d pads=%d%d in=%s out=%s" % (
            prev_stage, heat.stage, relays[0], relays[1], fmt(t_in, "-"), fmt(t_out, "-")))
    prev_relays = relays

    if t_in is not None:
        low = config.T_ALARM_LOW
        high = config.T_ALARM_HIGH
        hyst = config.T_ALARM_HYST
        cold = t_in < low or ("COLD" in faults.active and t_in < low + hyst)
        hot = t_in > high or ("HOT" in faults.active and t_in > high - hyst)
        faults.set("COLD", cold, status.ALARM, fmt(t_in))
        faults.set("HOT", hot, status.ALARM, fmt(t_in))

    faults.set("RESET", now < reset_warn_until_ms, status.WARN, reset_cause)

    interval.t_in.add(t_in)
    interval.t_out.add(t_out)
    day_stats.t_in.add(t_in)
    day_stats.t_out.add(t_out)
    nt = update_night(t_in, t_out)

    if not datalog.ok and now >= next_sd_ms:
        next_sd_ms = now + config.SD_RETRY_S * 1000
        feed()
        if datalog.mount():
            log_event("SD_OK", "dropped=%d" % datalog.dropped)
            datalog.dropped = 0
        feed()
    faults.set("SD", not datalog.ok, status.WARN, datalog.error)

    if log_schedule.due(now):
        write_measurement(now)
        interval = Stats()

    if time_valid:
        day = today()
        if cur_day is None:
            cur_day = day
        elif day != cur_day:
            write_daily(cur_day)
            day_stats = Stats()
            faults.seen = set(faults.active)
            cur_day = day

    # At the end of the cycle: the sync can move the clock by up to a second, which must
    # not shift this cycle's timestamps
    if now >= next_rtc_ms:
        next_rtc_ms = now + config.RTC_SYNC_S * 1000
        faults.set("RTC", not sync_time(), status.WARN)
    feed()

    if lcd is not None:
        draw_ui(t_in, t_out, nt)
    gc.collect()


def guarded_cycle(now):
    global consecutive_errors, last_error_ms
    try:
        control_cycle(now)
        consecutive_errors = 0
    except Exception as exc:
        consecutive_errors += 1
        last_error_ms = now
        sys.print_exception(exc)
        log_event("ERROR", "%d %r" % (consecutive_errors, exc))
        if consecutive_errors >= config.MAX_CONSECUTIVE_ERRORS:
            log_event("RESET", "too many errors")
            time.sleep_ms(200)
            machine.reset()
    faults.set("ERR", last_error_ms is not None and now - last_error_ms < ERROR_HOLD_S * 1000,
               status.WARN)


def run():
    setup()
    while True:
        now = mono_ms()
        feed()
        if cycle_schedule.due(now):  # at once after boot, then at full minutes
            end_flash()  # the cycle blocks for about 1 s: show the UI meanwhile
            guarded_cycle(now)
        update_flash(faults.level())
        time.sleep_ms(TICK_MS)


def fatal_failsafe():
    # Setup or the main loop died outside the per-cycle error handling. Keep heating
    # in failsafe mode with a red flashing screen for a while, then try a fresh start.
    on = [config.FAILSAFE_STAGE >= 2, config.FAILSAFE_STAGE >= 2]
    if config.FAILSAFE_STAGE == 1:
        on[0 if relay_pins[0] is not None else 1] = True
    set_relays(on)
    show_message(RED, "FATAL ERROR", "failsafe heating", "stage %d" % config.FAILSAFE_STAGE,
                 "reset in %d min" % (FATAL_FAILSAFE_S // 60))
    end = mono_ms() + FATAL_FAILSAFE_S * 1000
    while mono_ms() < end:
        feed()
        update_flash(status.ALARM)
        time.sleep_ms(TICK_MS)
    machine.reset()


def stop():
    # Ctrl-C (e.g. mpremote connecting): hand the board over to the REPL
    disable_wdt()
    set_relays([False, False])
    show_message(WHITE, "Stopped (REPL)", "watchdog off", "pads off")
    print("Stopped: watchdog disabled, pads off.")


try:
    run()
except KeyboardInterrupt:
    stop()
except Exception as exc:
    sys.print_exception(exc)
    try:
        log_event("FATAL", repr(exc))
    except Exception:
        pass
    try:
        fatal_failsafe()
    except KeyboardInterrupt:
        stop()
