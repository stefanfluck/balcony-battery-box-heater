# Configuration for Akkubox Heizung

# Heating stages, controlled by the inside temperature (C).
# Stage 1 = one pad, stage 2 = both pads.
T_STAGE1_ON = 13.0   # stage 0 -> 1 at or below
T_STAGE2_ON = 10.0   # -> stage 2 at or below
T_STAGE2_OFF = 12.0  # stage 2 -> 1 at or above (on/off gap for pad 2)
T_OFF = 15.0         # -> stage 0 at or above

# Stage 1 uses pad 1 (relay 1). Wire the bottom pad to relay 1: it heats the
# batteries; the side pad near the sensor would warm the sensor first and switch
# off before the batteries are warm. True alternates pad 1 and 2 instead.
ROTATE_PADS = False

# Stage used when neither sensor gives a valid reading (pads are 5V and safe to run
# continuously). If only the inside sensor fails, the outside sensor is used instead.
FAILSAFE_STAGE = 2
# ... but only while the RTC chip (DS3231, in the electronics enclosure, about +-3 C)
# reads at or below FAILSAFE_RTC_ON, and off again at or above FAILSAFE_RTC_OFF, so a
# sensor failure in summer does not heat. Without an RTC reading FAILSAFE_STAGE applies.
FAILSAFE_RTC_ON = 15.0
FAILSAFE_RTC_OFF = 17.0

# Alarms on the inside temperature (C)
T_ALARM_LOW = 5.0     # red below
T_ALARM_HIGH = 40.0   # red above (summer)
T_ALARM_HYST = 1.0    # alarm clears this far back inside the limit
STATUS_TEMP = 10.0    # LCD status bar turns blue below (info only)

# Relay settings
RELAY1_PIN = 16
RELAY2_PIN = 17
RELAY_ACTIVE_LOW = True
RELAY1_ENABLED = True
RELAY2_ENABLED = True

# DS18B20 one-wire bus. Set the ROM ids as hex strings, e.g. "28ff641e80160495".
# Find them with: mpremote exec "import sensorid" (README, Setup step 5).
# Without them the scan order decides, which can swap inside and outside.
ONEWIRE_PIN = 15
SENSOR_IN_ROM  = "282318321100001d"
SENSOR_OUT_ROM = "28211c45d4a52148"
SENSOR_FAIL_COUNT = 3       # consecutive bad reads before a sensor counts as lost
SENSOR_RESCAN_S = 600       # bus re-scan interval while a sensor is missing

# Status signal on the LCD. OK: no flashing, the green status bar shows all is fine.
# Warning / alarm: the whole screen flashes yellow / red this often.
FLASH_INTERVAL_S = 10
FLASH_MS = 500

# Watchdog (RP2040 maximum is 8388 ms)
WDT_ENABLED = True
WDT_TIMEOUT_MS = 8000
MAX_CONSECUTIVE_ERRORS = 5  # reset the board after this many failed loop cycles

# LCD (fixed pins on RP2040-LCD-0.96, ST7735S controller, 80x160 panel)
LCD_SPI_ID = 1
LCD_SCK = 10
LCD_MOSI = 11
LCD_CS = 9
LCD_DC = 8
LCD_RST = 12
LCD_BL = 25
LCD_WIDTH = 160
LCD_HEIGHT = 80
LCD_XSTART = 1      # Waveshare demo values for landscape; verify on the device
LCD_YSTART = 26
LCD_BAUD = 10000000
LCD_ROTATION = 3
LCD_BGR = True
LCD_INVERT = True

# SD card (SPI0)
SD_SPI_ID = 0
SD_SCK = 2
SD_MOSI = 3
SD_MISO = 4
SD_CS = 5
SD_BAUD = 1320000
SD_RETRY_S = 600    # remount interval after an SD error

# RTC (I2C1), DS3231 module (ZS-042; its AT24C32 EEPROM at 0x57 is unused).
# The RTC holds UTC, see settime.py.
I2C_ID = 1
I2C_SDA = 6
I2C_SCL = 7
I2C_FREQ = 100000
RTC_SYNC_S = 3600   # copy external RTC to the internal clock this often

# Local time = UTC + UTC_OFFSET_H, plus 1 h in summer if DST_EU (last Sunday of March
# to last Sunday of October, as in CH/EU). Used for timestamps, files and the display.
UTC_OFFSET_H = 1
DST_EU = True

# Timing
# With a set clock both run at round clock times: the cycle at every full minute, the
# log at :00, :05, :10 ... Use divisors of 3600 (60, 120, 300, 600, ...).
LOG_INTERVAL_S = 300    # log line with average/min/max since the last one
LOOP_INTERVAL_S = 60    # control cycle: read sensors, switch relays, update the display
TEMP_DECIMALS = 1
LOG_DIR = "/sd/log"             # one measurement file per day: YYYYMMDD.csv
EVENT_PATH = "/sd/events.csv"
DAILY_PATH = "/sd/daily.csv"
