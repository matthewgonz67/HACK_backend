"""
SOUND BOARD  (Pico 2 W, CircuitPython + synthio)

Listens on TWO UARTs:
    uart_sensors (GP0/GP1) <- sensors board: keypad notes, FSR instrument
    uart_wifi    (GP4/GP5) <- WiFi bridge board: website volume/instrument

Two separate UARTs rather than one shared RX line, so the two senders
can never collide mid-frame.

Frames are 2 bytes: [command, value]

WIRING:
    sensors board GP0 -> THIS GP1
    wifi board    GP0 -> THIS GP5
    both boards   GND -> THIS GND      <- required

    I2S amp: GP16 bit clock, GP17 word select, GP22 data
"""

import board
import synthio
import audiobusio
import audiomixer
import busio
import array
import math
import time

print("=== code.py booted, version 3 (dual UART + trumpet/ocarina/flute) ===")

SAMPLE_RATE = 44100


def build_harmonic_wave(length=512, harmonics=None, amplitude=20000):
    if harmonics is None:
        harmonics = [(1, 1.0)]
    wave = array.array("h", [0] * length)
    total_weight = sum(w for _, w in harmonics)
    for i in range(length):
        theta = 2 * math.pi * i / length
        s = sum(w * math.sin(n * theta) for n, w in harmonics)
        s /= total_weight
        wave[i] = max(-32768, min(32767, int(s * amplitude)))
    return wave


def loudness_compensation(note_num):
    # rough equal-loudness style curve: boost below ~A4 (69),
    # tune by ear against your speaker
    if note_num < 60:
        return 1.0 + (60 - note_num) * 0.02   # boost bass, cap it
    return 1.0


audio = audiobusio.I2SOut(bit_clock=board.GP16, word_select=board.GP17, data=board.GP22)
mixer = audiomixer.Mixer(sample_rate=SAMPLE_RATE, channel_count=1, buffer_size=2048)
synth = synthio.Synthesizer(sample_rate=SAMPLE_RATE, channel_count=1)
audio.play(mixer)
mixer.voice[0].play(synth)
mixer.voice[0].level = 0.2   # kept from the tested trumpet/ocarina/flute session;
                              # CMD_SET_VOLUME from the wifi board will override this anyway


# =========================================================
# TRUMPET
# =========================================================

TRUMPET_WAVE = build_harmonic_wave(harmonics=[(n, 1.0 / n) for n in range(1, 11)])  # sawtooth

TRUMPET_ENVELOPE = synthio.Envelope(
    attack_time=0.09, decay_time=0.10,
    attack_level=1.0, sustain_level=0.75, release_time=0.10
)

TRUMPET_FILTER_MIN = 800
TRUMPET_FILTER_PEAK = 4500
TRUMPET_FILTER_SUSTAIN = 2200
TRUMPET_DETUNE_CENTS = 6

trumpet_filter = synthio.Biquad(mode=synthio.FilterMode.LOW_PASS,
                                 frequency=TRUMPET_FILTER_MIN, Q=1.2)

FILTER_ENV_OFFSET = (TRUMPET_FILTER_MIN + TRUMPET_FILTER_PEAK) / 2   # 2650
FILTER_ENV_SCALE = (TRUMPET_FILTER_PEAK - TRUMPET_FILTER_MIN) / 2    # 1850

sustain_normalized = (TRUMPET_FILTER_SUSTAIN - FILTER_ENV_OFFSET) / FILTER_ENV_SCALE  # ≈ -0.243

trumpet_filter_env = synthio.LFO(
    rate=1 / 0.05, once=True,
    offset=FILTER_ENV_OFFSET,
    scale=FILTER_ENV_SCALE,
    waveform=array.array("h", [-32767, 32767, int(sustain_normalized * 32767), int(sustain_normalized * 32767)])
)

trumpet_filter.frequency = trumpet_filter_env

trumpet_vibrato_lfo = synthio.LFO(rate=5.5, scale=0.02)
trumpet_vibrato_delay = synthio.LFO(rate=1 / 0.4, once=True,
                                     waveform=array.array("h", [0, 0, 32767]))
trumpet_vibrato = synthio.Math(synthio.MathOperation.PRODUCT,
                                trumpet_vibrato_lfo, trumpet_vibrato_delay)


def build_trumpet_notes(note_num):
    freq = synthio.midi_to_hz(note_num)
    detune_ratio = 2 ** (TRUMPET_DETUNE_CENTS / 1200)
    notes = (
        synthio.Note(frequency=freq, waveform=TRUMPET_WAVE,
                     envelope=TRUMPET_ENVELOPE, filter=trumpet_filter),
        synthio.Note(frequency=freq * detune_ratio, waveform=TRUMPET_WAVE,
                     envelope=TRUMPET_ENVELOPE, filter=trumpet_filter),
        synthio.Note(frequency=freq / detune_ratio, waveform=TRUMPET_WAVE,
                     envelope=TRUMPET_ENVELOPE, filter=trumpet_filter),
    )
    for n in notes:
        n.bend = trumpet_vibrato
    return notes


# =========================================================
# Ocarina / Flute
# =========================================================

ocarina_wave = build_harmonic_wave(harmonics=[(2, 1.0), (4, 0.6), (6, 0.35), (8, 0.15)])
flute_wave = build_harmonic_wave(harmonics=[(1, 1.0)])

WAVEFORMS = {0: TRUMPET_WAVE, 1: ocarina_wave, 2: flute_wave}

ENVELOPES = {
    0: TRUMPET_ENVELOPE,
    1: synthio.Envelope(attack_time=0.01, decay_time=0.20,
                        attack_level=1.0, sustain_level=0.4, release_time=0.15),
    2: synthio.Envelope(attack_time=0.12, decay_time=0.10,
                        attack_level=1.0, sustain_level=0.85, release_time=0.15),
}

# timeout=0 makes read() non-blocking. Without this, CircuitPython's
# default 1s timeout means each empty read stalls the loop - and with
# two UARTs that is up to 2 seconds of dead time per iteration.
uart_sensors = busio.UART(board.GP0, board.GP1, baudrate=115200, timeout=0)
uart_wifi = busio.UART(board.GP4, board.GP5, baudrate=115200, timeout=0)

CMD_SELECT_INSTRUMENT = 1
CMD_PLAY_NOTE = 2
CMD_SET_VOLUME = 3

current_instrument = 0
note_playing = False


def handle_command(cmd, value, source):
    global current_instrument, note_playing

    if cmd == CMD_SELECT_INSTRUMENT:
        if 0 <= value < len(WAVEFORMS):
            current_instrument = value
            print(source, "-> instrument", current_instrument)

    elif cmd == CMD_SET_VOLUME:
        # 0-100 from the website maps to the mixer's 0.0-1.0 level
        level = max(0, min(100, value)) / 100.0
        mixer.voice[0].level = level
        print(source, "-> volume", value)

    elif cmd == CMD_PLAY_NOTE and not note_playing:
        note_playing = True
        note_num = max(21, min(108, value))

        if current_instrument == 0:
            notes = build_trumpet_notes(note_num)
            synth.change(press=notes, retrigger=(trumpet_filter_env, trumpet_vibrato_delay))
            time.sleep(0.3)
            synth.release(notes)
        else:
            waveform = WAVEFORMS.get(current_instrument, flute_wave)
            envelope = ENVELOPES.get(current_instrument, ENVELOPES[2])
            note = synthio.Note(frequency=synthio.midi_to_hz(note_num),
                                waveform=waveform, envelope=envelope,
                                amplitude=min(1.0, loudness_compensation(note_num)))
            synth.press(note)
            time.sleep(0.2)
            synth.release(note)

        note_playing = False
        print(source, "-> note", note_num)


print("sound board ready, waiting on both UARTs...")

while True:
    for uart, source in ((uart_sensors, "sensors"), (uart_wifi, "wifi")):
        data = uart.read(2)
        if data and len(data) == 2:
            handle_command(data[0], data[1], source)

