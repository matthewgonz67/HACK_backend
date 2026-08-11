from machine import Pin, ADC, UART
from time import sleep_us
import os

print(os.listdir("/"))

# =========================================================
# UART OUTPUT TO SOUND BOARD -- 2-byte framed messages
# =========================================================

uart = UART(0, baudrate=115200, tx=Pin(0), rx=Pin(1))
uart_to_server = UART(1, baudrate=115200, tx=Pin(20), rx=Pin(21))

CMD_SELECT_INSTRUMENT = 1
CMD_PLAY_NOTE = 2

def select_instrument(instrument_index):
    uart.write(bytes([CMD_SELECT_INSTRUMENT, instrument_index]))
    uart_to_server.write(bytes([CMD_SELECT_INSTRUMENT, instrument_index]))
   


def play(note_num):
    uart.write(bytes([CMD_PLAY_NOTE, note_num]))
    uart_to_server.write(bytes([CMD_PLAY_NOTE, note_num]))
# =========================================================
# KEYPAD -- mapped to a musical scale, and is the trigger
# =========================================================

rows = [Pin(2, Pin.IN), Pin(3, Pin.IN), Pin(4, Pin.IN), Pin(5, Pin.IN)]
columns = [Pin(6, Pin.IN, Pin.PULL_UP), Pin(7, Pin.IN, Pin.PULL_UP), Pin(8, Pin.IN, Pin.PULL_UP)]

KEY_LAYOUT = (
    ("1", "2", "3"),
    ("4", "5", "6"),
    ("7", "8", "9"),
    ("*", "0", "#")
)

# Major scale intervals. Change this list to change the scale.
SCALE_STEPS = [0, 2, 4, 5, 7, 9, 11, 12, 14, 16, 17, 19]
root_note = 60  # C4

KEY_TO_MIDI = {
    key: root_note + SCALE_STEPS[i]
    for i, key in enumerate(("1", "2", "3", "4", "5", "6", "7", "8", "9", "*", "0", "#"))
}


def scan_keypad():
    for row in rows:
        row.init(Pin.IN)
    for row_index, row in enumerate(rows):
        row.init(Pin.OUT, value=0)
        sleep_us(10)
        for column_index, column in enumerate(columns):
            if column.value() == 0:
                key = KEY_LAYOUT[row_index][column_index]
                row.init(Pin.IN)
                return key
        row.init(Pin.IN)
    return None


# =========================================================
# FORCE SENSOR -- selects the instrument
# =========================================================

FORCE_SENSOR_PINS = (26, 27, 28)
force_sensors = [ADC(pin_number) for pin_number in FORCE_SENSOR_PINS]
INSTRUMENT_NAMES = ("Trumpet", "Oboe", "Flute")

FORCE_THRESHOLDS = (18_000, 18_000, 18_000)
FORCE_HYSTERESIS = 2_500

filtered_force = [sensor.read_u16() for sensor in force_sensors]
sensor_pressed = [False, False, False]


def update_force_sensors():
    """Returns the index of a newly-pressed force sensor, or None."""
    newly_pressed = None
    for sensor_index, sensor in enumerate(force_sensors):
        raw_value = sensor.read_u16()
        filtered_force[sensor_index] += (raw_value - filtered_force[sensor_index]) // 4
        threshold = FORCE_THRESHOLDS[sensor_index]

        if not sensor_pressed[sensor_index] and filtered_force[sensor_index] >= threshold:
            sensor_pressed[sensor_index] = True
            newly_pressed = sensor_index
        elif sensor_pressed[sensor_index] and filtered_force[sensor_index] <= threshold - FORCE_HYSTERESIS:
            sensor_pressed[sensor_index] = False

    return newly_pressed


# =========================================================
# MAIN LOOP
# =========================================================

active_key = None
previous_key = None
current_instrument = 0

print("=== Sensors board booted, version 2 (no mic) ===")

while True:
    detected_key = scan_keypad()

    if detected_key is not None and detected_key != previous_key:
        active_key = detected_key
        note_num = KEY_TO_MIDI.get(active_key, root_note)
        print("Key", active_key, "-> note", note_num)
        play(note_num)

    previous_key = detected_key

    newly_selected = update_force_sensors()
    if newly_selected is not None:
        current_instrument = newly_selected
        print("Instrument ->", INSTRUMENT_NAMES[current_instrument])
        select_instrument(current_instrument)
