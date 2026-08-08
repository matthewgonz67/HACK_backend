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
import time
import json
from machine import Pin
from microdot import Microdot
from microdot.websocket import with_websocket
 
# ---- CONFIG: fill these in ----
WIFI_SSID = "HAcK-Project-WiFi"
WIFI_PASSWORD = "UCLA.HAcK.2026.Summer"
GPIO_PIN = 16
# --------------------------------
 
led_pin = Pin(GPIO_PIN, Pin.OUT)
led_pin.value(0)  # start OFF
 
app = Microdot()
 
 
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
 
 
@app.route('/ws')
@with_websocket
async def websocket_handler(request, ws):
    print("Client connected")
    while True:
        message = await ws.receive()
        print("Received:", message)
 
        try:
            data = json.loads(message)
            action = data.get("action")
        except ValueError:
            # If it's not JSON, treat the raw text as the action
            action = message
 
        if action == "on":
            led_pin.value(1)
            status = "on"
        elif action == "off":
            led_pin.value(0)
            status = "off"
        elif action == "toggle":
            led_pin.value(not led_pin.value())
            status = "on" if led_pin.value() else "off"
        else:
            status = "unknown_command"
 
        response = {
            "status": status,
            "pin": GPIO_PIN,
            "original_message": message,
        }
        await ws.send(json.dumps(response))
 
 
if __name__ == "__main__":
    ip_address = connect_wifi()
    if ip_address:
        print(f"WebSocket server starting at ws://{ip_address}:8765/ws")
        app.run(port=8765)
    else:
        print("Cannot start server without WiFi connection")
 