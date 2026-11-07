# Fault tracking and the status signal on the LCD.

OK = 0
WARN = 1
ALARM = 2


class Faults:
    def __init__(self, on_change):
        self.active = {}  # code -> severity
        self.seen = set()  # codes raised since the last daily summary
        self.on_change = on_change  # callback(event, detail)

    def set(self, code, active, severity=WARN, detail=""):
        if active:
            if self.active.get(code) != severity:
                self.active[code] = severity
                self.seen.add(code)
                self.on_change("FAULT", code + (" " + detail if detail else ""))
        elif code in self.active:
            del self.active[code]
            self.on_change("CLEAR", code)

    def level(self):
        return max(self.active.values()) if self.active else OK

    def codes(self):
        return sorted(self.active)


class ScreenFlash:
    """On a warning or alarm the whole LCD flashes in the level color, at once and then
    every interval_ms. OK: no flashing, the status bar of the UI shows all is fine.
    The UI stays in the frame buffer; ending a flash sends it to the panel again."""

    def __init__(self, lcd, buf, colors, interval_ms, on_ms):
        self.lcd = lcd
        self.buf = buf
        self.interval_ms = interval_ms
        self.on_ms = on_ms
        # One pixel row per level, in frame buffer byte order (colors are from rgb565())
        self.rows = {}
        for level, c in colors.items():
            if level != OK:
                self.rows[level] = bytes((c & 0xFF, c >> 8)) * lcd.width
        self.level = OK
        self.next_ms = 0  # start of the next flash
        self.end_ms = None  # end of the current flash, None while not flashing

    def update(self, level, now_ms):
        if level != self.level:
            self.level = level
            self.next_ms = now_ms  # a new or changed fault level flashes at once
            self.end()
        if self.end_ms is not None:
            if now_ms >= self.end_ms:
                self.end()
        elif level != OK and now_ms >= self.next_ms:
            self.lcd.fill(self.rows[level])
            self.end_ms = now_ms + self.on_ms
            self.next_ms = now_ms + self.interval_ms

    def end(self):
        if self.end_ms is not None:
            self.end_ms = None
            self.lcd.blit_buffer(self.buf, 0, 0, self.lcd.width, self.lcd.height)
