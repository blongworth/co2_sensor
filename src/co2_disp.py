# CO2 sensor based on Feather M4 express running circuitpython 8.0
# SCD-30 CO2 sensor
# Feather AirLift Wifi

# SPDX-FileCopyrightText: 2020 by Bryan Siepert, written for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense
import time
import board
import busio
import displayio
import terminalio
import adafruit_scd30
import adafruit_displayio_ssd1306
from adafruit_display_text import label
from adafruit_display_shapes.sparkline import Sparkline
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
from adafruit_esp32spi import adafruit_esp32spi
import adafruit_requests as requests
from adafruit_io.adafruit_io import IO_HTTP, AdafruitIO_RequestError
from digitalio import DigitalInOut

# Read wifi and IO credentials
# pylint: disable=no-name-in-module,wrong-import-order
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# Pins for AirLift Featherwing
esp32_cs = DigitalInOut(board.D13)
esp32_ready = DigitalInOut(board.D11)
esp32_reset = DigitalInOut(board.D12)

# Set up Airlift
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

print("Connecting to AP...")
while not esp.is_connected:
    try:
        esp.connect_AP(secrets["ssid"], secrets["password"])
    except RuntimeError as e:
        print("could not connect to AP, retrying: ", e)
        continue
print("Connected to", str(esp.ssid, "utf-8"), "\tRSSI:", esp.rssi)

socket.set_interface(esp)
requests.set_socket(socket, esp)

aio_username = secrets["aio_username"]
aio_key = secrets["aio_key"]

# Initialize an Adafruit IO HTTP API object
io = IO_HTTP(aio_username, aio_key, requests)

try:
    # Get the 'co2' feed from Adafruit IO
    co2_feed = io.get_feed("co2")
except AdafruitIO_RequestError:
    # If no 'co2' feed exists, create one
    co2_feed = io.create_new_feed("co2")

displayio.release_displays()

i2c = board.I2C()  # uses board.SCL and board.SDA

# set up display i2c
display_bus = displayio.I2CDisplay(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

# set up co2 i2c
scd = adafruit_scd30.SCD30(i2c)


## Splash screen

# Make the display context
splash = displayio.Group()
display.show(splash)

color_bitmap = displayio.Bitmap(128, 64, 1)
color_palette = displayio.Palette(1)
color_palette[0] = 0xFFFFFF  # White

bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette, x=0, y=0)
splash.append(bg_sprite)

# Draw a smaller inner rectangle
inner_bitmap = displayio.Bitmap(118, 48, 1)
inner_palette = displayio.Palette(1)
inner_palette[0] = 0x000000  # Black
inner_sprite = displayio.TileGrid(inner_bitmap, pixel_shader=inner_palette, x=5, y=4)
splash.append(inner_sprite)

# Draw a label
text = "CO2 monitor start"
text_area = label.Label(terminalio.FONT, text=text, color=0xFFFF00, x=20, y=30)
splash.append(text_area)

time.sleep(2)

# reset the display to show nothing.
display.show(None)

## Create background bitmaps and sparklines

# Baseline size of the sparkline chart, in pixels.
chart_width = display.width
chart_height = display.height - 20

# sparkline1 uses a vertical y range between 0 to 10 and will contain a
# maximum of 40 items
sparkline1 = Sparkline(
    width=chart_width,
    height=chart_height,
    #dyn_xpitch=False,
    max_items=100,
    y_min=None, y_max=None, x=0, y=20
)

# Create a group to hold the sparkline and append the sparkline into the
# group (my_group)
#
# Note: In cases where display elements will overlap, then the order the elements
# are added to the group will set which is on top.  Latter elements are displayed
# on top of former elements.
co2_display = displayio.Group()

# add the sparkline into my_group
co2_display.append(sparkline1)

# Draw a label
co2_text = label.Label(terminalio.FONT, text=" "*20, color=0xFFFF00, x=5, y=5)
co2_display.append(co2_text)

# Add my_group (containing the sparkline) to the display
display.show(co2_display)


## co2 sensor startup

# scd.temperature_offset = 10
print("Temperature offset:", scd.temperature_offset)

# scd.measurement_interval = 4
print("Measurement interval:", scd.measurement_interval)

# scd.self_calibration_enabled = True
print("Self-calibration enabled:", scd.self_calibration_enabled)

# scd.ambient_pressure = 1100
print("Ambient Pressure:", scd.ambient_pressure)

# scd.altitude = 100
print("Altitude:", scd.altitude, "meters above sea level")

# scd.forced_recalibration_reference = 409
print("Forced recalibration reference:", scd.forced_recalibration_reference)
print("")


# Main loop
while True:
    data = scd.data_available
    if data:
        co2 = scd.CO2
        co2_str = "CO2: " + str(co2) + "PPM"
        temp = "Temp: " + str(scd.temperature) + " C"
        humidity = "Humidity: " + str(scd.relative_humidity) + " %%rH"
        print(co2_str)
        print(temp)
        print(humidity)
        print("Waiting for new data...")
        print("")

        # Create the text label for ssd
        co2_text.text = co2_str
        # Show it
        #display.show(co2_text)
        
        # turn off the auto_refresh of the display while modifying the sparkline
        display.auto_refresh = False

        # add_value: add a new value to a sparkline
        # Note: The y-range for mySparkline1 is set to 0 to 10, so all these random
        # values (between 0 and 10) will fit within the visible range of this sparkline
        sparkline1.add_value(co2)

        # turn the display auto_refresh back on
        display.auto_refresh = True

        # Send co2 values to the feed
        print("Sending {0} to co2 feed...".format(co2))
        io.send_data(co2_feed["key"], co2)
        print("Data sent!")

    time.sleep(2)

