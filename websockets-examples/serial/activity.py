"""
SERVER BOARD  (Pico 2 W, MicroPython)
 
One of three boards:
 
    [sensors board] --UART--> [sound board] <--UART-- [THIS BOARD]
      keypad + FSRs             synthio              WiFi + website
 
This board runs the WebSocket server and forwards website commands to
the sound board over UART. It also keeps its own local mic gate and
LED indicator - those are unrelated to the audio, which is generated
entirely on the sound board.
 
REALISM MODE: when enabled, the instrument only actually sounds while
the mic detects real breath/sound - like an acoustic instrument that
needs air to make noise. Disabling it makes the instrument always
audible regardless of the mic.
 
WIRING:
    THIS GP0 (TX) -----> sound board GP5   (uart_wifi RX)
    THIS GND      -----> sound board GND   <- required, not optional
 
    GP16 --> resistor --> LED --> GND      (local indicator)
    GP26 --> microphone module out         (local mic gate)
"""
 
import network
import asyncio
import time
import json
from machine import Pin, PWM, ADC, UART
from microdot import Microdot
from microdot.websocket import with_websocket
 
# ---- CONFIG ----
WIFI_SSID = "HAcK-Project-WiFi"
WIFI_PASSWORD = "UCLA.HAcK.2026.Summer"
 
LED_PIN = 16
MIC_PIN = 26
 
UART_ID = 0
UART_TX = 0
UART_RX = 1
UART_BAUD = 115200
 
MIC_THRESHOLD = 62000
PRINT_MIC_VALUES = False   # True while calibrating MIC_THRESHOLD
# -----------------
 
CMD_SELECT_INSTRUMENT = 1
CMD_PLAY_NOTE = 2
CMD_SET_VOLUME = 3
 
INSTRUMENT_NAMES = ("Trumpet", "Oboe", "Flute")
 
uart = UART(UART_ID, baudrate=UART_BAUD, tx=Pin(UART_TX), rx=Pin(UART_RX))
 
mic = ADC(MIC_PIN)
led_pwm = PWM(Pin(LED_PIN))
led_pwm.freq(1000)
led_pwm.duty_u16(0)
 
app = Microdot()
 
current_volume = 0
current_instrument = 0
sound_open = False
realism_enabled = True
 
 
# =========================================================
# UART -> SOUND BOARD
# =========================================================
 
def send_command(cmd, value):
    """Send one 2-byte frame. The sound board reads exactly two bytes."""
    value = max(0, min(255, int(value)))
    uart.write(bytes([cmd, value]))
    print("UART ->", cmd, value)
 
 
def push_volume_to_audio():
    """
    The single source of truth for what volume the audio board should
    hear right now. Called whenever volume, the mic gate, OR the
    realism toggle changes - any of the three can change the
    effective output level, so all three funnel through here rather
    than each sending its own command.
    """
    if not realism_enabled or sound_open:
        send_command(CMD_SET_VOLUME, current_volume)
    else:
        send_command(CMD_SET_VOLUME, 0)
    apply_output()
 
 
def set_volume(volume):
    """Set volume on the sound board AND on the local LED indicator."""
    global current_volume
    current_volume = max(0, min(100, int(volume)))
    push_volume_to_audio()
 
 
def set_instrument(index):
    global current_instrument
    index = int(index)
    if 0 <= index < len(INSTRUMENT_NAMES):
        current_instrument = index
        send_command(CMD_SELECT_INSTRUMENT, index)
        return True
    return False
 
 
def play_note(midi_note):
    """
    MIDI note number. 60 is middle C. The sound board clamps to 21-108.
 
    Not gated directly - it doesn't need to be. When realism is on and
    the mic is closed, push_volume_to_audio() has already told the
    audio board its mixer level is 0, so any note played is silent
    until the gate opens. One source of truth (volume) instead of
    gating every command separately.
    """
    send_command(CMD_PLAY_NOTE, int(midi_note))
 
 
def change_realism(realism):
    global realism_enabled
    realism_enabled = bool(realism)
    print("Realism:", "ON" if realism_enabled else "OFF")
    push_volume_to_audio()
 
 
# =========================================================
# LOCAL LED INDICATOR
# =========================================================
 
def apply_output():
    """
    Local LED only. Brightness tracks volume, gated the same way the
    audio is (mic + realism). This does not affect the audio itself -
    that lives on the sound board, driven by push_volume_to_audio().
    """
    if not realism_enabled or sound_open:
        duty = int((current_volume / 100) * 65535)
    else:
        duty = 0
    led_pwm.duty_u16(duty)
 
 
# =========================================================
# MIC GATE
# =========================================================
 
def is_sound_detected(window_ms=50):
    samples = []
    t_end = time.ticks_add(time.ticks_ms(), window_ms)
    while time.ticks_diff(t_end, time.ticks_ms()) > 0:
        samples.append(mic.read_u16())
    spread = max(samples) - min(samples)
    if PRINT_MIC_VALUES:
        print("mic spread:", spread)
    return spread > MIC_THRESHOLD
 
 
async def check_for_sound():
    global sound_open
    while True:
        detected = is_sound_detected()
        if detected != sound_open:
            sound_open = detected
            print("Sound gate:", "OPEN" if sound_open else "CLOSED")
            push_volume_to_audio()   # re-push - the gate itself changed
        await asyncio.sleep_ms(20)
 
 
# =========================================================
# WIFI
# =========================================================
 
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
 
    print("Connecting to WiFi", end="")
    timeout = 20
    while not wlan.isconnected() and timeout > 0:
        print(".", end="")
        time.sleep(1)
        timeout -= 1
 
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print(f"\nConnected! Pico IP address: {ip}")
        return ip
 
    print("\nFailed to connect to WiFi")
    return None
 
 
# =========================================================
# WEBSOCKET
# =========================================================
 
@app.route('/ws')
@with_websocket
async def websocket_handler(request, ws):
    print("Client connected")
 
    push_volume_to_audio()
 
    while True:
        message = await ws.receive()
 
        try:
            data = json.loads(message)
        except ValueError:
            print("Not valid JSON, ignoring:", message)
            continue
 
        if "volume" in data and data["volume"] is not None:
            set_volume(data["volume"])
 
        if "instrument" in data and data["instrument"] is not None:
            set_instrument(data["instrument"])
 
        if "note" in data and data["note"] is not None:
            play_note(data["note"])
 
        if "realism" in data and data["realism"] is not None:
            change_realism(data["realism"])
 
        response = {
            "volume": current_volume,
            "instrument": INSTRUMENT_NAMES[current_instrument],
            "instrument_index": current_instrument,
            "gate_open": sound_open,
            "realism": realism_enabled,
        }
        await ws.send(json.dumps(response))
 
 
# =========================================================
# MAIN
# =========================================================
 
async def main():
    ip_address = connect_wifi()
    if not ip_address:
        print("Cannot start server without WiFi connection")
        return
 
    print(f"WebSocket server starting at ws://{ip_address}:8765/ws")
    print(f"UART{UART_ID} TX on GP{UART_TX} -> sound board GP5")
 
    asyncio.create_task(check_for_sound())
    await app.start_server(port=8765)
 
 
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        led_pwm.duty_u16(0)
        print("Stopped")
 