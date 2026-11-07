# DS18B20 sensors: inside/outside assignment, fault counting, bus re-scan.

import time
import binascii

import onewire
import ds18x20


def rom_hex(rom):
    return binascii.hexlify(rom).decode() if rom else "-"


def _rom_bytes(value):
    if value is None:
        return None
    if isinstance(value, str):
        return binascii.unhexlify(value.replace(" ", "").replace(":", ""))
    return bytes(value)


class Sensor:
    def __init__(self, name, rom):
        self.name = name
        self.rom = rom
        self.fixed = rom is not None  # configured in config.py, never reassigned
        self.value = None  # last good reading, None once the sensor counts as lost
        self.fails = 0


class Sensors:
    def __init__(self, cfg, pin):
        self.cfg = cfg
        self.ds = ds18x20.DS18X20(onewire.OneWire(pin))
        self.inside = Sensor("in", _rom_bytes(cfg.SENSOR_IN_ROM))
        self.outside = Sensor("out", _rom_bytes(cfg.SENSOR_OUT_ROM))
        self.found = []
        self.scan()

    def scan(self):
        """Scan the bus. Sensors without a configured ROM take unused ROMs in scan order."""
        try:
            self.found = [bytes(r) for r in self.ds.scan()]
        except Exception:
            self.found = []
        for s in (self.inside, self.outside):
            if s.rom is None:
                for r in self.found:
                    if r != self.inside.rom and r != self.outside.rom:
                        s.rom = r
                        break
        return self.found

    def read(self):
        """Read both sensors. A sensor keeps its last value until SENSOR_FAIL_COUNT
        reads in a row failed, then its value becomes None."""
        active = [s for s in (self.inside, self.outside) if s.rom is not None]
        converted = False
        if active:
            try:
                self.ds.convert_temp()
                time.sleep_ms(750)
                converted = True
            except Exception:
                pass
        for s in (self.inside, self.outside):
            t = None
            if converted and s.rom is not None:
                try:
                    t = self.ds.read_temp(s.rom)
                except Exception:
                    t = None
            # 85.0 is the power-on value, i.e. no conversion happened
            if t is not None and (t == 85.0 or t < -55 or t > 125):
                t = None
            if t is None:
                s.fails += 1
                if s.fails >= self.cfg.SENSOR_FAIL_COUNT:
                    s.value = None
            else:
                s.fails = 0
                s.value = t
        return self.inside.value, self.outside.value
