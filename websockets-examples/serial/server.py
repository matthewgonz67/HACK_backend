import network
import asyncio
import time
import json
from machine import Pin, PWM, ADC, UART
from microdot import Microdot
from microdot.websocket import with_websocket
 
WIFI_SSID = "HAcK-Project-WiFi"
WIFI_PASSWORD = "UCLA.HAcK.2026.Summer"
 
LED_PIN = 16
MIC_PIN = 26
 
UART_ID = 0
UART_TX = 0
UART_RX = 1
UART_BAUD = 115200
 
MIC_THRESHOLD = 62000
PRINT_MIC_VALUES = False   # sanity check
 
CMD_SELECT_INSTRUMENT = 1
CMD_PLAY_NOTE = 2
CMD_SET_VOLUME = 3
 
INSTRUMENT_NAMES = ("Trumpet", "Oboe", "Flute")
 
uart_sound = UART(UART_ID, baudrate=UART_BAUD, tx=Pin(UART_TX), rx=Pin(UART_RX))
uart_sensors = UART(1, baudrate=115200, tx=Pin(20), rx=Pin(21))
 
mic = ADC(MIC_PIN)
led_pwm = PWM(Pin(LED_PIN))
led_pwm.freq(1000)
led_pwm.duty_u16(0)
 
app = Microdot()
 
current_volume = 0
current_instrument = 0
sound_open = False
realism_enabled = True
last_note = None
connected_clients = set()
 
 

# UART -> SOUND BOARD
 
def send_command(cmd, value):
    value = max(0, min(255, int(value)))
    uart_sound.write(bytes([cmd, value]))
    print("UART ->", cmd, value)
 
 
def push_volume_to_audio():
    #called on change of relevant global variables
    if not realism_enabled or sound_open:
        send_command(CMD_SET_VOLUME, current_volume)
    else:
        send_command(CMD_SET_VOLUME, 0)
    apply_output()
 
 
def set_volume(volume):
    #Set volume on the sound board AND on the local LED indicator
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

# SENSOR BOARD -> UART
 
async def listen_for_sensor_board():
    global last_note, current_instrument
    while True:
        data = uart_sensors.read(2)
        if data and len(data) == 2:
            cmd, value = data[0], data[1]

            if cmd == CMD_PLAY_NOTE:
                last_note = value
                print("Note received from sensor board:", last_note)
                await broadcast_state()

            elif cmd == CMD_SELECT_INSTRUMENT:
                if 0 <= value < len(INSTRUMENT_NAMES):
                    current_instrument = value
                    print("Instrument received from sensor board:", INSTRUMENT_NAMES[current_instrument])
                    await broadcast_state()

        await asyncio.sleep_ms(5)

#LED INDICATOR
 
def apply_output(): #sanity check to see if web integration is working
    if not realism_enabled or sound_open:
        duty = int((current_volume / 100) * 65535)
    else:
        duty = 0
    led_pwm.duty_u16(duty)
 
# MIC GATE
 
def is_sound_detected(window_ms=50):
    samples = []
    t_end = time.ticks_add(time.ticks_ms(), window_ms)
    while time.ticks_diff(t_end, time.ticks_ms()) > 0:
        samples.append(mic.read_u16())
    spread = max(samples) - min(samples)
    if PRINT_MIC_VALUES: #for debugging
        print("mic spread:", spread)
    return spread > MIC_THRESHOLD
 
async def check_for_sound():
    global sound_open
    while True:
        detected = is_sound_detected()
        if detected != sound_open:
            sound_open = detected
            print("Sound gate:", "OPEN" if sound_open else "CLOSED")
            push_volume_to_audio() #change detected
        await asyncio.sleep_ms(20)
 
 
# WIFI

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
 

# SERVER CLIENTS

def build_state():
    return {
        "volume": current_volume,
        "instrument": INSTRUMENT_NAMES[current_instrument],
        "instrument_index": current_instrument,
        "gate_open": sound_open,
        "realism": realism_enabled,
        "last_note": last_note,
    }

async def broadcast_state():
    message = json.dumps(build_state())
    disconnected = set()
    for client in connected_clients:
        try:
            await client.send(message)
        except Exception:
            disconnected.add(client)
    for client in disconnected:
        connected_clients.discard(client)
 
# WEBSOCKET
 
@app.route('/ws')
@with_websocket
async def websocket_handler(request, ws):
    print("Client connected")
    connected_clients.add(ws)
    push_volume_to_audio()
    await ws.send(json.dumps(build_state()))
    try:
        while True:
            message = await ws.receive()
            try:
                #data is website input
                data = json.loads(message)
            except ValueError:
                print("Not valid JSON, ignoring:", message)
                continue

            if "volume" in data and data["volume"] is not None:
                set_volume(data["volume"])

            if "instrument" in data and data["instrument"] is not None: 
                set_instrument(data["instrument"])
            #not used, setup for for website integration, didnt have enough time to get to
            if "note" in data and data["note"] is not None:
                play_note(data["note"])
            #not used, setup for for website integration, didnt have enough time to get to
            if "realism" in data and data["realism"] is not None:
                change_realism(data["realism"])

            await broadcast_state()
    finally:
        connected_clients.discard(ws) 
        print("Client disconnected")
 
 
# MAIN
 
async def main():
    ip_address = connect_wifi()
    if not ip_address:
        print("Cannot start server without WiFi connection")
        return
 
    print(f"WebSocket server starting at ws://{ip_address}:8765/ws")
    print(f"UART{UART_ID} TX on GP{UART_TX} -> sound board GP5")
 
    asyncio.create_task(check_for_sound())
    asyncio.create_task(listen_for_sensor_board())
    await app.start_server(port=8765)
 
 
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted")
    finally:
        led_pwm.duty_u16(0)
        print("Stopped")
 