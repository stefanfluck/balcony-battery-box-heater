# Print the ROM id and temperature of every DS18B20 on the bus, every 2 s for 1 minute.
# Hold one sensor in your hand: its temperature rises. See README, Setup step 5.
#   mpremote exec "import sensorid"

import time
import binascii
from machine import Pin

import onewire
import ds18x20

import config

ds = ds18x20.DS18X20(onewire.OneWire(Pin(config.ONEWIRE_PIN)))
roms = ds.scan()
print("found %d sensor(s)" % len(roms))
for _ in range(30):
    ds.convert_temp()
    time.sleep_ms(750)
    print("   ".join('"%s" %.2f C' % (binascii.hexlify(r).decode(), ds.read_temp(r)) for r in roms))
    time.sleep_ms(1250)
