# Run the heating stages by hand, 1 minute each: stage 1 (pad 1), stage 2 (both pads),
# then off. Prints both temperatures every 10 s. The pads are switched off at the end,
# also on Ctrl-C. See README, Bench test commands.
#   mpremote run padtest.py

import time
from machine import Pin

import config
import sensors

STEP_S = 60
STAGES = (
    ("stage 1: pad 1 on", (True, False)),
    ("stage 2: both pads on", (True, True)),
)


def level(on):
    return int(not on) if config.RELAY_ACTIVE_LOW else int(on)


relays = [Pin(config.RELAY1_PIN, Pin.OUT, value=level(False)),
          Pin(config.RELAY2_PIN, Pin.OUT, value=level(False))]
sens = sensors.Sensors(config, Pin(config.ONEWIRE_PIN))


def fmt(t):
    return "--.--" if t is None else "%5.2f" % t


try:
    for name, on in STAGES:
        print(name)
        for pin, state in zip(relays, on):
            pin.value(level(state))
        start = time.time()
        while time.time() - start < STEP_S:
            t_in, t_out = sens.read()  # takes about 0.75 s
            print("  %2d s   in %s C   out %s C" % (time.time() - start, fmt(t_in), fmt(t_out)))
            time.sleep_ms(9250)
finally:
    for pin in relays:
        pin.value(level(False))
    print("off: both pads off")
