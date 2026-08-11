import { useState, useEffect, useRef } from 'react'
import './App.css'

// Replace with your Pico 2 W's IP address (printed to the serial console
// when it connects to WiFi, e.g. "192.168.1.42")
const PICO_IP = '192.168.50.113'
//192.168.50.113
//192.168.0.123

function App() {
  const wsRef = useRef(null)
  const volumeThrottleRef = useRef(null)   // holds pending throttle timer
  const pendingVolumeRef = useRef(null)    // holds the latest value not yet sent
  const [volume, setVolume] = useState("0")
  const [realism, setRealism] = useState(true)
  const [gateOpen, setGateOpen] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [instrument, setInstrument] = useState("Trumpet")
  const [lastNote, setLastNote] = useState(null)
  const [noteHistory, setNoteHistory] = useState([])
  const lastNoteRef = useRef(null)     // tracks previous note so we only log actual changes
  const instrumentRef = useRef("Trumpet")   // onmessage is defined once (empty deps
                                              // below), so reading `instrument` state
                                              // directly inside it would always see the
                                              // initial value, not the latest - this ref
                                              // is what history entries actually read

  const INSTRUMENT_COLORS = {
    Trumpet: "#f4a300",
    Oboe: "#c2185b",
    Flute: "#2196f3",
  }

  const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

  // MIDI note number -> name, e.g. 74 -> "D5". Works for any MIDI note,
  // not just the 12 keys the sensor board's scale currently uses.
  const midiToName = (midiNote) => {
    if (midiNote === null || midiNote === undefined) return "-"
    const name = NOTE_NAMES[midiNote % 12]
    const octave = Math.floor(midiNote / 12) - 1
    return `${name}${octave}`
  }

  // Initialize WebSocket connection
  useEffect(() => {
    //connect to websocket server running on the Pico
    wsRef.current = new WebSocket(`ws://${PICO_IP}:8765/ws`)

    wsRef.current.onopen = () => {
      console.log('Connected to WebSocket server')
    }

    wsRef.current.onmessage = (event) => {
      console.log('Message from server:', event.data)
      try {
        const data = JSON.parse(event.data)
        if (typeof data.volume === "number") {
          // Ignore volume echoes from the server while we're actively
          // dragging - otherwise our own throttled updates and the
          // server's broadcast fight each other and the slider jitters.
          if (!volumeThrottleRef.current) {
            setVolume(String(data.volume))
          }
        }
        if (typeof data.realism === "boolean") {
          setRealism(data.realism)
        }
        if (typeof data.gate_open === "boolean") {
          setGateOpen(data.gate_open)
        }
        if (typeof data.playing === "boolean") {
          setPlaying(data.playing)
        }
        if (typeof data.instrument === "string") {
          setInstrument(data.instrument)
          instrumentRef.current = data.instrument
        }
        if (data.last_note !== undefined) {
          setLastNote(data.last_note)

          // broadcast_state() fires on volume/gate/realism changes too,
          // each carrying whatever last_note currently is - only log
          // an entry when the note itself actually changed.
          if (data.last_note !== null && data.last_note !== lastNoteRef.current) {
            lastNoteRef.current = data.last_note
            setNoteHistory(prev => [
              ...prev,
              {
                note: data.last_note,
                name: midiToName(data.last_note),
                instrument: instrumentRef.current,
                time: new Date().toLocaleTimeString(),
              },
            ])
          }
        }
      } catch (e) {
        console.error('Error parsing message:', e)
      }
    }

    wsRef.current.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    wsRef.current.onclose = () => {
      console.log('Disconnected from WebSocket server')
    }

    // Cleanup on unmount
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  // Send a volume update to the Pico
  //
  // The slider fires onChange dozens of times per second while
  // dragging. Sending a WebSocket message for every single one floods
  // the Pico - each message triggers a UART write, an LED update, and
  // a broadcast to every connected tab, and the async handler can't
  // keep up, so messages queue and the slider feels laggy/glitchy.
  //
  // Fix: update the visible slider position immediately (free, local
  // state), but only actually send over the network at most once
  // every THROTTLE_MS. The most recent value always wins - if the
  // user moves fast, intermediate values are dropped, not queued.
  const VOLUME_THROTTLE_MS = 60

  const sendVolume = (newVolume) => {
    setVolume(newVolume)              // slider stays responsive, no lag
    pendingVolumeRef.current = newVolume

    if (volumeThrottleRef.current) return  // a send is already scheduled
    //incldue a delay so the slider isn't super laggy when syncing with other clients
    volumeThrottleRef.current = setTimeout(() => { 
      volumeThrottleRef.current = null
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ volume: Number(pendingVolumeRef.current) }))
      } else {
        console.error('WebSocket is not open')
      }
    }, VOLUME_THROTTLE_MS)
  }

  // Toggle realism mode on the Pico
  const sendRealism = () => {
    const newRealism = !realism
    setRealism(newRealism)
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ realism: newRealism }))
    } else {
      console.error('WebSocket is not open')
    }
  }

  return (
    <div className = "Webpage">
      <div className = "Intro">
          <h1 className = "Heading">
            Meet the masterminds behind
          </h1>
          <div className = "image-intro-container">
            <img src = "/team_logo.png" alt ="Team Logo" className="intro-pictures"></img>
            <img src = "/team_picture.jpg" alt ="Team Picture" className="intro-pictures"></img>
          </div>
        <div className = "intro-container">
          <div className = "intro-entry">
            <img src = "/matthew_pic.jpg" alt = "Name Picture" className="personal-pictures"></img>
            <h3>Matthew Gonzalez</h3>
            <p>Hello there! My name is Matthew Gonzalez and I'm an incoming computer engineering transfer at UCLA. In my free time I like to grapple or hike, especially longer trails. Aside from academics, I'm especially excited to join UCLA's wrestling club.</p>
          </div>
          <div className = "intro-entry">
            <img src = "/andy_pic.jpg" alt = "Name Picture" className="personal-pictures"></img>
            <h3>Andy Viche</h3>
            <p>Hi, my name is Andy. I am an electrical engineer transferring from Los Angeles City College. I like reading and playing video games. I'm excited to eat at the dining halls and I'm planning on tasting all of them.</p>
          </div>
          <div className = "intro-entry">
            <img src = "/teppei_pic.jpg" alt = "Name Picture" className="personal-pictures"></img>
            <h3>Teppei Yoshikawa</h3>
            <p>Hi I’m Teppei, transferring to Aerospace engineering. I like to read when I have free time. I'm excited for the club activity at UCLA and plan on joining Rocket Project at UCLA.</p>
          </div>
          <div className = "intro-entry">
            <img src = "/sean_pic.png" alt = "Name Picture" className="personal-pictures"></img>
            <h3>Sean Stokowski</h3>
            <p>Hi, my name is Sean, and I'm a mechanical engineering major. I transferred from Contra Costa College, and in my free time, I like to play baseball, basketball, and ultimate frisbee. I also play musical instruments such as the trumpet and baritone.</p>
          </div>
        </div>
      </div>
      <h1 className = "video-heading">Demonstration Videos</h1>
      <div className="video-row">
        <div className="video-container">
          <iframe
            src="https://www.youtube.com/embed/VIDEO_ID_1"
            title="Video 1"
            frameBorder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
          ></iframe>
        </div>
        <div className="video-container">
          <iframe
            src="https://www.youtube.com/embed/VIDEO_ID_2"
            title="Video 2"
            frameBorder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
          ></iframe>
        </div>
        <div className="video-container">
          <iframe
            src="https://www.youtube.com/embed/VIDEO_ID_3"
            title="Video 3"
            frameBorder="0"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
          ></iframe>
        </div>
      </div>

      <div className="gpio-control">
        <h1 className="gpio-heading">Pico Control</h1>
        <input type="range" min="0" max="100" value={volume} onChange={(e) => sendVolume(e.target.value)} />
        <p className="gpio-status">Volume: {volume}</p>
        <button className="realism-button" onClick={() => sendRealism()}>Realism: {realism?"Enabled":"Disabled"}</button>

        <div
          className="visualizer"
          style={{
            width: `${80 + Number(volume) * 1.6}px`,
            height: `${80 + Number(volume) * 1.6}px`,
            borderRadius: "50%",
            margin: "30px auto",
            backgroundColor: INSTRUMENT_COLORS[instrument] || "#888",
            opacity: playing ? 1 : 0.25,
            border: realism ? "4px solid white" : "4px dashed white",
            boxShadow: playing
              ? `0 0 ${20 + Number(volume)}px ${INSTRUMENT_COLORS[instrument] || "#888"}`
              : "none",
            transition: "all 120ms ease-out",
          }}
        />
        <p className="gpio-status">
          Instrument: {instrument}
        </p>
        <p className="gpio-status">
          Note: {midiToName(lastNote)}
        </p>
      </div>

      <div className="note-history">
        <h1 className="video-heading">Notes Played</h1>
        {noteHistory.length === 0 ? (
          <p className="gpio-status">No notes played yet</p>
        ) : (
          <ul className="note-history-list">
            {noteHistory.map((entry, index) => (
              <li key={index}>
                <span className="note-history-name">{entry.instrument}: {entry.name}</span>
                <span className="note-history-time">{entry.time}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default App
