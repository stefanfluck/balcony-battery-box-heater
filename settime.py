# Set the DS3231 RTC to UTC from a Unix timestamp. See README,
# "Setting the time". Example (PowerShell):
#   mpremote exec "import settime; settime.set_unix($([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()))"

import time
import machine
from machine import I2C, Pin

import config
from lib import ds3231


def set_unix(unix_s):
    # time.gmtime() counts from 1970 or 2000 depending on the MicroPython port
    epoch_shift = 0 if time.gmtime(0)[0] == 1970 else 946684800
    year, month, mday, hour, minute, sec, weekday = time.gmtime(unix_s - epoch_shift)[:7]
    i2c = I2C(config.I2C_ID, scl=Pin(config.I2C_SCL), sda=Pin(config.I2C_SDA), freq=config.I2C_FREQ)
    rtc = ds3231.DS3231(i2c)
    rtc.set_datetime((year, month, mday, weekday + 1, hour, minute, sec, 0))  # RTC weekday 1-7
    machine.RTC().datetime((year, month, mday, weekday, hour, minute, sec, 0))
    dt = rtc.datetime()
    print("RTC set to %04d-%02d-%02d %02d:%02d:%02d UTC" % (dt[:3] + dt[4:7]))
