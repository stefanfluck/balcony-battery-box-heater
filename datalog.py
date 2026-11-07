# SD card logging: daily measurement files, event log, daily summary.
# On a write error the card is unmounted and the caller retries mount() later.
# Events are kept in RAM until the card is back; measurements are counted as dropped.

import os
from machine import Pin, SPI

from lib import sdcard

MEAS_HEADER = ("timestamp,uptime_s,t_in,t_in_min,t_in_max,t_out,t_out_min,t_out_max,"
               "pad1_on_s,pad2_on_s,stage,source,faults,t_rtcmodule\n")
EVENT_HEADER = "timestamp,uptime_s,event,detail\n"
DAILY_HEADER = "date,t_in_min,t_in_max,t_out_min,t_out_max,pad1_on_h,pad2_on_h,faults\n"
MAX_PENDING = 100


class DataLog:
    def __init__(self, cfg):
        self.cfg = cfg
        self.ok = False
        self.error = ""
        self.pending = []  # event lines waiting for the SD card
        self.dropped = 0  # measurement lines lost since the last successful mount
        self._spi = None
        self._cs = None

    def mount(self):
        self._umount()
        try:
            if self._spi is None:
                c = self.cfg
                self._spi = SPI(c.SD_SPI_ID, sck=Pin(c.SD_SCK), mosi=Pin(c.SD_MOSI), miso=Pin(c.SD_MISO))
                self._cs = Pin(c.SD_CS, Pin.OUT, value=1)
            sd = sdcard.SDCard(self._spi, self._cs, self.cfg.SD_BAUD)
            os.mount(sd, "/sd")
            try:
                os.mkdir(self.cfg.LOG_DIR)
            except OSError:
                pass  # exists
            self.ok = True
            self.error = ""
        except Exception as exc:
            self.ok = False
            self.error = repr(exc)
        return self.ok

    def _umount(self):
        try:
            os.umount("/sd")
        except Exception:
            pass

    def _append(self, path, header, line):
        if not self.ok:
            return False
        try:
            try:
                os.stat(path)
                new = False
            except OSError:
                new = True
            with open(path, "a") as f:
                if new:
                    f.write(header)
                f.write(line)
            return True
        except Exception as exc:
            self.ok = False
            self.error = repr(exc)
            self._umount()
            return False

    def event(self, line):
        self.pending.append(line)
        if len(self.pending) > MAX_PENDING:
            self.pending.pop(0)
        self.flush()

    def flush(self):
        while self.pending and self.ok:
            if not self._append(self.cfg.EVENT_PATH, EVENT_HEADER, self.pending[0]):
                return False
            self.pending.pop(0)
        return not self.pending

    def measurement(self, day, line):
        if self._append("%s/%s.csv" % (self.cfg.LOG_DIR, day), MEAS_HEADER, line):
            return True
        self.dropped += 1
        return False

    def daily(self, line):
        return self._append(self.cfg.DAILY_PATH, DAILY_HEADER, line)
