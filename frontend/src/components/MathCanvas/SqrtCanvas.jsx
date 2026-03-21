import { useEffect, useRef } from 'react'

export default function SqrtCanvas() {
  const canvasRef = useRef(null)
  const animRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    let w, h
    const resize = () => {
      w = canvas.width = window.innerWidth
      h = canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener('resize', resize)

    let t = 0

    // Ball physics
    let ballY = 0
    let ballVel = 0
    const gravity = 600
    let ballDropHeight = 0

    const draw = (dt) => {
      t += dt
      ctx.clearRect(0, 0, w, h)

      // --- LEFT SIDE: Expanding square with sqrt ---
      const cx = w * 0.3
      const cy = h * 0.5

      // Area oscillates between 100 and 40000
      const minArea = 400
      const maxArea = 40000
      const area = minArea + (maxArea - minArea) * (0.5 + 0.5 * Math.sin(t * 0.8))
      const side = Math.sqrt(area)
      const maxSide = Math.sqrt(maxArea)

      // Draw square
      const scale = (h * 0.4) / maxSide
      const drawSide = side * scale

      ctx.strokeStyle = 'rgba(255, 215, 0, 0.8)'
      ctx.lineWidth = 2
      ctx.shadowColor = 'rgba(255, 215, 0, 0.3)'
      ctx.shadowBlur = 15
      ctx.strokeRect(cx - drawSide / 2, cy - drawSide / 2, drawSide, drawSide)

      // Fill with subtle gradient
      const grad = ctx.createLinearGradient(cx - drawSide / 2, cy - drawSide / 2, cx + drawSide / 2, cy + drawSide / 2)
      grad.addColorStop(0, 'rgba(255, 215, 0, 0.05)')
      grad.addColorStop(1, 'rgba(255, 215, 0, 0.02)')
      ctx.fillStyle = grad
      ctx.fillRect(cx - drawSide / 2, cy - drawSide / 2, drawSide, drawSide)

      ctx.shadowBlur = 0

      // Area label inside square
      ctx.fillStyle = 'rgba(255, 255, 255, 0.9)'
      ctx.font = `${Math.max(14, drawSide * 0.12)}px monospace`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText(`A = ${Math.round(area)}`, cx, cy - 10)

      // Side label
      ctx.fillStyle = '#ffd700'
      ctx.font = `${Math.max(16, drawSide * 0.14)}px monospace`
      ctx.fillText(`\u221a${Math.round(area)} = ${side.toFixed(1)}`, cx, cy + 18)

      // Side length indicator (bottom)
      const y1 = cy + drawSide / 2 + 20
      ctx.strokeStyle = 'rgba(255, 215, 0, 0.5)'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(cx - drawSide / 2, y1)
      ctx.lineTo(cx + drawSide / 2, y1)
      ctx.stroke()
      // Arrows
      for (const dir of [-1, 1]) {
        ctx.beginPath()
        ctx.moveTo(cx + dir * drawSide / 2, y1 - 5)
        ctx.lineTo(cx + dir * drawSide / 2, y1 + 5)
        ctx.stroke()
      }
      ctx.fillStyle = 'rgba(255, 255, 255, 0.6)'
      ctx.font = '13px monospace'
      ctx.fillText(`side = ${side.toFixed(1)}`, cx, y1 + 18)

      // --- RIGHT SIDE: Falling ball with sqrt speed bar ---
      const bx = w * 0.72
      const floorY = h * 0.82
      const ceilY = h * 0.15
      const totalH = floorY - ceilY

      // Reset ball cycle
      const cycleDur = 3.0
      const cycleT = t % cycleDur
      if (cycleT < dt * 1.5) {
        ballY = 0
        ballVel = 0
        ballDropHeight = 0
      }

      // Physics
      ballVel += gravity * dt
      ballY += ballVel * dt
      ballDropHeight = Math.min(ballY, totalH)

      if (ballY > totalH) {
        ballY = totalH
        ballVel = 0
      }

      const ballScreenY = ceilY + ballDropHeight

      // Speed = sqrt(2 * g * h)
      const speed = Math.sqrt(2 * gravity * ballDropHeight)
      const maxSpeed = Math.sqrt(2 * gravity * totalH)

      // Draw drop zone
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)'
      ctx.setLineDash([4, 8])
      ctx.beginPath()
      ctx.moveTo(bx, ceilY)
      ctx.lineTo(bx, floorY)
      ctx.stroke()
      ctx.setLineDash([])

      // Floor
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(bx - 40, floorY)
      ctx.lineTo(bx + 40, floorY)
      ctx.stroke()

      // Ball
      const ballR = 14
      const ballGrad = ctx.createRadialGradient(ballScreenY < floorY - 5 ? bx - 3 : bx, ballScreenY - 3, 2, bx, ballScreenY, ballR)
      ballGrad.addColorStop(0, '#ff6b6b')
      ballGrad.addColorStop(1, '#cc3333')
      ctx.fillStyle = ballGrad
      ctx.beginPath()
      ctx.arc(bx, ballScreenY, ballR, 0, Math.PI * 2)
      ctx.fill()

      // Speed bar (to the right of ball)
      const barX = bx + 55
      const barW = 18
      const barH = totalH * 0.8
      const barTop = ceilY + totalH * 0.1

      // Bar background
      ctx.fillStyle = 'rgba(255, 255, 255, 0.05)'
      ctx.fillRect(barX, barTop, barW, barH)
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)'
      ctx.lineWidth = 1
      ctx.strokeRect(barX, barTop, barW, barH)

      // Bar fill
      const fillH = (speed / maxSpeed) * barH
      const barGrad = ctx.createLinearGradient(barX, barTop + barH - fillH, barX, barTop + barH)
      barGrad.addColorStop(0, 'rgba(255, 107, 107, 0.9)')
      barGrad.addColorStop(1, 'rgba(255, 50, 50, 0.6)')
      ctx.fillStyle = barGrad
      ctx.fillRect(barX, barTop + barH - fillH, barW, fillH)

      // Speed labels
      ctx.fillStyle = '#ff6b6b'
      ctx.font = '14px monospace'
      ctx.textAlign = 'left'
      ctx.fillText(`v = \u221a(2gh)`, barX + barW + 10, barTop + barH - fillH + 5)
      ctx.fillStyle = 'rgba(255, 255, 255, 0.7)'
      ctx.font = '13px monospace'
      ctx.fillText(`= ${speed.toFixed(0)} px/s`, barX + barW + 10, barTop + barH - fillH + 22)

      // Height label
      ctx.fillStyle = 'rgba(255, 255, 255, 0.4)'
      ctx.font = '12px monospace'
      ctx.textAlign = 'center'
      ctx.fillText(`h=${Math.round(ballDropHeight)}`, bx, ceilY - 8)

      // Title
      ctx.fillStyle = '#ffd700'
      ctx.font = 'bold 22px monospace'
      ctx.textAlign = 'center'
      ctx.fillText('\u221a  Square Root', w * 0.5, h * 0.06)
      ctx.fillStyle = 'rgba(255, 255, 255, 0.4)'
      ctx.font = '13px monospace'
      ctx.fillText('Area \u2194 Side  |  Height \u2192 Speed', w * 0.5, h * 0.06 + 22)
    }

    let lastTime = performance.now()
    const loop = (now) => {
      const dt = Math.min((now - lastTime) / 1000, 0.05)
      lastTime = now
      draw(dt)
      animRef.current = requestAnimationFrame(loop)
    }
    animRef.current = requestAnimationFrame(loop)

    return () => {
      cancelAnimationFrame(animRef.current)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return <canvas ref={canvasRef} style={{ width: '100%', height: '100%' }} />
}
