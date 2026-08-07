import { useState, useEffect, useRef } from 'react'
import './App.css'

function App() {
  const [count, setCount] = useState(0)
  const [message, setMessage] = useState('')
  const [chatLogs, setChatLogs] = useState([])
  const wsRef = useRef(null)

  // Initialize WebSocket connection
  useEffect(() => {
    // Connect to WebSocket server
    wsRef.current = new WebSocket('ws://localhost:8765')

    wsRef.current.onopen = () => {
      console.log('Connected to WebSocket server')
    }

    wsRef.current.onmessage = (event) => {
      console.log('Message from server:', event.data)
      try {
        const data = JSON.parse(event.data)
        setChatLogs(prev => [...prev, {
          message: data.original_message,
          timestamp: data.timestamp,
          type: 'received'
        }])
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

  // Send message on Enter key
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && message.trim() && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(message)

      setMessage('')
    }
  }

  return (
    <>
      <section id="center">

        {/* WebSocket Message Input */}
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Type message and press Enter to send"
          style={{
            marginTop: '20px',
            padding: '10px',
            borderRadius: '4px',
            border: '1px solid #ccc',
            width: '300px',
            fontSize: '16px'
          }}
        />

        {/* Chat Logs Display */}
        <div style={{
          marginTop: '30px',
          padding: '15px',
          border: '1px solid #ddd',
          borderRadius: '4px',
          width: '350px',
          maxHeight: '400px',
          overflowY: 'auto',
          backgroundColor: '#f9f9f9'
        }}>
          <h3 style={{ marginTop: 0 }}>Chat Logs</h3>
          {chatLogs.length === 0 ? (
            <p style={{ color: '#999' }}>No messages yet</p>
          ) : (
            chatLogs.map((log, index) => (
              <div key={index} style={{
                marginBottom: '10px',
                padding: '8px',
                backgroundColor: '#f0f0f0',
                borderRadius: '3px',
                borderLeft: `3px solid #666`
              }}>
                <div style={{ fontSize: '12px', color: '#666' }}>
                  {log.timestamp}
                </div>
                <div style={{ fontSize: '14px', marginTop: '4px' }}>
                  {log.message}
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </>
  )
}

export default App
