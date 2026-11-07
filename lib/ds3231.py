# DS3231 RTC driver (minimal). The AT24C32 EEPROM on the module (address 0x57) is
# not used.

_STATUS = 0x0F
_CONTROL = 0x0E
_OSF = 0x80  # status: the oscillator stopped since the time was last set
_EOSC = 0x80  # control: 1 stops the oscillator while running on the battery


class DS3231:
    def __init__(self, i2c, addr=0x68):
        self.i2c = i2c
        self.addr = addr

    def _bcd2bin(self, value):
        return (value & 0x0F) + ((value >> 4) * 10)

    def _bin2bcd(self, value):
        return (value // 10 << 4) | (value % 10)

    def _clear_bit(self, reg, bit):
        value = self.i2c.readfrom_mem(self.addr, reg, 1)[0]
        if value & bit:
            self.i2c.writeto_mem(self.addr, reg, bytes([value & ~bit]))

    def datetime(self):
        data = self.i2c.readfrom_mem(self.addr, 0x00, 7)
        sec = self._bcd2bin(data[0] & 0x7F)
        minute = self._bcd2bin(data[1] & 0x7F)
        hour = self._bcd2bin(data[2] & 0x3F)
        weekday = self._bcd2bin(data[3] & 0x07)
        mday = self._bcd2bin(data[4] & 0x3F)
        month = self._bcd2bin(data[5] & 0x1F)  # bit 7 is the century flag
        year = self._bcd2bin(data[6]) + 2000
        return (year, month, mday, weekday, hour, minute, sec, 0)

    def temperature(self):
        # Chip temperature in C: 0.25 C steps, about +-3 C, updated every 64 s
        msb, lsb = self.i2c.readfrom_mem(self.addr, 0x11, 2)
        if msb & 0x80:
            msb -= 256  # two's complement
        return msb + (lsb >> 6) * 0.25

    def halted(self):
        # OSF: the oscillator stopped at some point, e.g. a power cut with a flat coin
        # cell. The time may look plausible but is wrong until it is set again.
        return bool(self.i2c.readfrom_mem(self.addr, _STATUS, 1)[0] & _OSF)

    def set_datetime(self, dt):
        year, month, mday, weekday, hour, minute, sec, _ = dt
        data = bytearray(7)
        data[0] = self._bin2bcd(sec)
        data[1] = self._bin2bcd(minute)
        data[2] = self._bin2bcd(hour)  # bit 6 = 0: 24-hour mode
        data[3] = self._bin2bcd(weekday)
        data[4] = self._bin2bcd(mday)
        data[5] = self._bin2bcd(month)
        data[6] = self._bin2bcd(year - 2000)
        self.i2c.writeto_mem(self.addr, 0x00, data)
        self._clear_bit(_CONTROL, _EOSC)  # keep running on the battery
        self._clear_bit(_STATUS, _OSF)  # the time is valid again
