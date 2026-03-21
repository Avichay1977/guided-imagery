import { useState, useEffect, useRef } from 'react'
import SqrtCanvas from './SqrtCanvas'
import PowersCanvas from './PowersCanvas'
import PiWavesCanvas from './PiWavesCanvas'
import DeltaCanvas from './DeltaCanvas'
import './MathCanvas.css'

const LESSONS = [
  { id: 'sqrt', symbol: '\u221a', label: 'Root' },
  { id: 'powers', symbol: '\u00b2', label: 'Powers' },
  { id: 'pi', symbol: '\u03c0', label: 'Waves' },
  { id: 'delta', symbol: '\u0394', label: 'Change' },
]

export default function MathCanvas({ onBack }) {
  const [active, setActive] = useState('sqrt')
  const [cursor, setCursor] = useState({ x: -100, y: -100 })
  const gridRef = useRef(null)

  // Track mouse for custom cursor
  useEffect(() => {
    const move = (e) => setCursor({ x: e.clientX, y: e.clientY })
    const leave = () => setCursor({ x: -100, y: -100 })
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseleave', leave)
    return () => {
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseleave', leave)
    }
  }, [])

  // Draw grid background
  useEffect(() => {
    const canvas = gridRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    let w, h

    const drawGrid = () => {
      w = canvas.width = window.innerWidth
      h = canvas.height = window.innerHeight
      ctx.clearRect(0, 0, w, h)

      const spacing = 40
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)'
      ctx.lineWidth = 0.5

      for (let x = 0; x < w; x += spacing) {
        ctx.beginPath()
        ctx.moveTo(x, 0)
        ctx.lineTo(x, h)
        ctx.stroke()
      }
      for (let y = 0; y < h; y += spacing) {
        ctx.beginPath()
        ctx.moveTo(0, y)
        ctx.lineTo(w, y)
        ctx.stroke()
      }

      // Slightly brighter major lines every 4
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)'
      for (let x = 0; x < w; x += spacing * 4) {
        ctx.beginPath()
        ctx.moveTo(x, 0)
        ctx.lineTo(x, h)
        ctx.stroke()
      }
      for (let y = 0; y < h; y += spacing * 4) {
        ctx.beginPath()
        ctx.moveTo(0, y)
        ctx.lineTo(w, y)
        ctx.stroke()
      }
    }

    drawGrid()
    window.addEventListener('resize', drawGrid)
    return () => window.removeEventListener('resize', drawGrid)
  }, [])

  const renderCanvas = () => {
    switch (active) {
      case 'sqrt': return <SqrtCanvas />
      case 'powers': return <PowersCanvas />
      case 'pi': return <PiWavesCanvas />
      case 'delta': return <DeltaCanvas />
      default: return <SqrtCanvas />
    }
  }

  return (
    <div className="math-canvas-app">
      {/* Grid background */}
      <canvas ref={gridRef} className="math-grid-bg" />

      {/* Custom cursor */}
      <div
        className="gold-cursor"
        style={{ left: cursor.x, top: cursor.y }}
      />

      {/* Navigation */}
      <nav className="math-nav">
        {LESSONS.map(l => (
          <button
            key={l.id}
            className={`math-nav-btn ${active === l.id ? 'active' : ''}`}
            onClick={() => setActive(l.id)}
          >
            {l.symbol} {l.label}
          </button>
        ))}
      </nav>

      {/* Back button */}
      {onBack && (
        <button className="math-back-btn" onClick={onBack}>
          &larr; Back
        </button>
      )}

      {/* Active canvas */}
      <div className="math-canvas-container">
        {renderCanvas()}
      </div>
    </div>
  )
}
