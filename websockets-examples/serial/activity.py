"""
Runs directly on the Raspberry Pi Pico 2 W.
 
- Connects to WiFi
- Starts a WebSocket server on port 8765
- Listens for button-press messages from the website
- Turns GPIO pin 16 on/off in response
 
REQUIREMENTS (install once on the Pico, over Thonny, using the built-in
package manager `mip`):
 
    import mip
    mip.install("microdot")
    mip.install("microdot-websocket")
 
WIRING:
    GPIO 16 --> resistor --> LED --> GND
    (or GPIO 16 --> relay/transistor control pin, if switching something
    bigger than an LED)
"""
 
import network
import asyncio
import time
import json
from machine import Pin, PWM, ADC
from microdot import Microdot
from microdot.websocket import with_websocket
 
# ---- CONFIG: fill these in ----
WIFI_SSID = "HAcK-Project-WiFi"
WIFI_PASSWORD = "UCLA.HAcK.2026.Summer"
GPIO_PIN = 16
# --------------------------------

mic = ADC(26)
led_pwm = PWM(Pin(16))
led_pwm.duty_u16(0)  # start OFF
led_pwm.freq(1000)
 
app = Microdot()

current_volume = 0
sound_open = False

def apply_output():
    if sound_open:
        duty = int((current_volume / 100) * 65535)
    else:
        duty = 0
    led_pwm.duty_u16(duty)
 
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
 
    print("Connecting to WiFi", end="")
    timeout = 20  # seconds
    while not wlan.isconnected() and timeout > 0:
        print(".", end="")
        time.sleep(1)
        timeout -= 1
 
    if wlan.isconnected():
        ip = wlan.ifconfig()[0]
        print(f"\nConnected! Pico IP address: {ip}")
        return ip
    else:
        print("\nFailed to connect to WiFi")
        return None

def is_sound_detected(window_ms=50, threshold=60000):
    samples = []
    t_end = time.ticks_add(time.ticks_ms(), window_ms)
    while time.ticks_diff(t_end, time.ticks_ms()) > 0:
        samples.append(mic.read_u16())
    print(max(samples) - min(samples))
    return (max(samples) - min(samples)) > threshold

async def check_for_sound():
    global sound_open
    while True:
        detected = is_sound_detected()
        if detected != sound_open:
            sound_open = detected
            print("Sound gate:", "OPEN" if sound_open else "CLOSED")
            apply_output()
        await asyncio.sleep_ms(20)
 
@app.route('/ws')
@with_websocket
async def websocket_handler(request, ws):
    global current_volume
    print("Client connected")
    while True:
        message = await ws.receive()
        print("Received:", message)
 
        try:
            data = json.loads(message)
            volume = data.get("volume")
        except ValueError:
            # If it's not JSON, treat the raw text as the action
            volume = None

        volume = int(volume)
        current_volume = max(0, min(100, volume))
        apply_output()
 
        response = {
            "pin": GPIO_PIN,
            "original_message": message,
        }
        await ws.send(json.dumps(response))
 
 
async def main():
    ip_address = connect_wifi()
    if ip_address:
        print(f"WebSocket server starting at ws://{ip_address}:8765/ws")
        asyncio.create_task(check_for_sound())
        await app.start_server(port=8765)
    else:
        print("Cannot start server without WiFi connection")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted")