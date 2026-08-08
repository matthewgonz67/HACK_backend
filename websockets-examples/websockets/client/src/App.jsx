import { useState, useEffect, useRef } from 'react'
import './App.css'

// Replace with your Pico 2 W's IP address (printed to the serial console
// when it connects to WiFi, e.g. "192.168.1.42")
const PICO_IP = '192.168.0.123'

function App() {
  const [pinStatus, setPinStatus] = useState('unknown')
  const wsRef = useRef(null)

  // Initialize WebSocket connection
  useEffect(() => {
    // Connect to WebSocket server running on the Pico
    wsRef.current = new WebSocket(`ws://${PICO_IP}:8765/ws`)

    wsRef.current.onopen = () => {
      console.log('Connected to WebSocket server')
    }

    wsRef.current.onmessage = (event) => {
      console.log('Message from server:', event.data)
      try {
        const data = JSON.parse(event.data)
        if (data.status === 'on' || data.status === 'off') {
          setPinStatus(data.status)
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

  // Send a GPIO toggle command to the Pico
  const handleToggleGPIO = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'toggle' }))
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
            <img src = "/name_pic.png" alt = "Name Picture" className="personal-pictures"></img>
            <h3>Matthew Gonzalez</h3>
            <p>Introduction</p>
          </div>
          <div className = "intro-entry">
            <img src = "/name_pic.png" alt = "Name Picture" className="personal-pictures"></img>
            <h3>Andy Viche</h3>
            <p>Introduction</p>
          </div>
          <div className = "intro-entry">
            <img src = "/name_pic.png" alt = "Name Picture" className="personal-pictures"></img>
            <h3>Teppei Yoshikawa</h3>
            <p>Introduction</p>
          </div>
          <div className = "intro-entry">
            <img src = "/name_pic.png" alt = "Name Picture" className="personal-pictures"></img>
            <h3>Sean Stokowski</h3>
            <p>Introduction</p>
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
        <button className="gpio-button" onClick={handleToggleGPIO}>
          Toggle GPIO 16
        </button>
        <p className="gpio-status">Pin status: {pinStatus}</p>
      </div>
    </div>
  )
}

export default App
