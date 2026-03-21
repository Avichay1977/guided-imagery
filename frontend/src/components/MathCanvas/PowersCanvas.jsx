import { useEffect, useRef } from 'react'

export default function PowersCanvas() {
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

    const draw = (dt) => {
      t += dt
      ctx.clearRect(0, 0, w, h)

      // --- LEFT: 11 exponential columns 2^0 to 2^10 ---
      const cols = 11
      const maxVal = Math.pow(2, 10) // 1024
      const chartLeft = w * 0.05
      const chartRight = w * 0.48
      const chartTop = h * 0.15
      const chartBottom = h * 0.88
      const chartW = chartRight - chartLeft
      const chartH = chartBottom - chartTop

      const barGap = 6
      const barW = (chartW - barGap * (cols + 1)) / cols

      // Highlight moves across columns
      const highlightIdx = Math.floor((t * 1.2) % cols)

      // Animate growth — columns grow in from left
      const growPhase = (t * 0.6) % (cols + 3)

      for (let i = 0; i < cols; i++) {
        const val = Math.pow(2, i)
        const targetH = (val / maxVal) * chartH * 0.9
        const growFactor = Math.min(1, Math.max(0, growPhase - i) * 1.5)
        const barH = targetH * growFactor

        const x = chartLeft + barGap + i * (barW + barGap)
        const y = chartBottom - barH

        const isHighlight = i === highlightIdx

        // Bar gradient
        const grad = ctx.createLinearGradient(x, y, x, chartBottom)
        if (isHighlight) {
          grad.addColorStop(0, 'rgba(255, 215, 0, 0.95)')
          grad.addColorStop(1, 'rgba(255, 170, 0, 0.6)')
        } else {
          grad.addColorStop(0, 'rgba(100, 180, 255, 0.7)')
          grad.addColorStop(1, 'rgba(60, 120, 200, 0.3)')
        }
        ctx.fillStyle = grad
        ctx.fillRect(x, y, barW, barH)

        // Border
        ctx.strokeStyle = isHighlight ? 'rgba(255, 215, 0, 0.8)' : 'rgba(100, 180, 255, 0.3)'
        ctx.lineWidth = isHighlight ? 2 : 1
        ctx.strokeRect(x, y, barW, barH)

        // Glow for highlight
        if (isHighlight) {
          ctx.shadowColor = 'rgba(255, 215, 0, 0.4)'
          ctx.shadowBlur = 20
          ctx.fillRect(x, y, barW, barH)
          ctx.shadowBlur = 0
        }

        // Label: 2^i
        ctx.fillStyle = isHighlight ? '#ffd700' : 'rgba(255, 255, 255, 0.6)'
        ctx.font = `${Math.max(10, barW * 0.4)}px monospace`
        ctx.textAlign = 'center'
        ctx.fillText(`2^${i}`, x + barW / 2, chartBottom + 16)

        // Value on top
        if (barH > 15) {
          ctx.fillStyle = isHighlight ? '#fff' : 'rgba(255, 255, 255, 0.5)'
          ctx.font = `${Math.max(9, barW * 0.35)}px monospace`
          ctx.fillText(val.toString(), x + barW / 2, y - 6)
        }
      }

      // Baseline
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(chartLeft, chartBottom)
      ctx.lineTo(chartRight, chartBottom)
      ctx.stroke()

      // --- RIGHT: 1/r² curve ---
      const curveLeft = w * 0.56
      const curveRight = w * 0.94
      const curveTop = h * 0.18
      const curveBottom = h * 0.82
      const curveW = curveRight - curveLeft
      const curveH = curveBottom - curveTop

      // Axes
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)'
      ctx.lineWidth = 1
      // Y axis
      ctx.beginPath()
      ctx.moveTo(curveLeft, curveTop)
      ctx.lineTo(curveLeft, curveBottom)
      ctx.stroke()
      // X axis
      ctx.beginPath()
      ctx.moveTo(curveLeft, curveBottom)
      ctx.lineTo(curveRight, curveBottom)
      ctx.stroke()

      // Draw 1/r² curve
      ctx.strokeStyle = 'rgba(180, 130, 255, 0.8)'
      ctx.lineWidth = 2
      ctx.beginPath()
      const rMin = 0.3
      const rMax = 5
      const steps = 200
      for (let i = 0; i <= steps; i++) {
        const frac = i / steps
        const r = rMin + frac * (rMax - rMin)
        const intensity = 1 / (r * r)
        const x = curveLeft + frac * curveW
        const y = curveBottom - (intensity / (1 / (rMin * rMin))) * curveH * 0.9
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.stroke()

      // Fill under curve
      ctx.lineTo(curveRight, curveBottom)
      ctx.lineTo(curveLeft, curveBottom)
      ctx.closePath()
      const fillGrad = ctx.createLinearGradient(curveLeft, curveTop, curveLeft, curveBottom)
      fillGrad.addColorStop(0, 'rgba(180, 130, 255, 0.15)')
      fillGrad.addColorStop(1, 'rgba(180, 130, 255, 0.02)')
      ctx.fillStyle = fillGrad
      ctx.fill()

      // Moving point on curve
      const pointPhase = ((t * 0.3) % 1)
      const pointR = rMin + pointPhase * (rMax - rMin)
      const pointIntensity = 1 / (pointR * pointR)
      const maxIntensity = 1 / (rMin * rMin)
      const pointX = curveLeft + pointPhase * curveW
      const pointY = curveBottom - (pointIntensity / maxIntensity) * curveH * 0.9

      // Point glow
      ctx.shadowColor = 'rgba(180, 130, 255, 0.6)'
      ctx.shadowBlur = 15
      ctx.fillStyle = '#b482ff'
      ctx.beginPath()
      ctx.arc(pointX, pointY, 6, 0, Math.PI * 2)
      ctx.fill()
      ctx.shadowBlur = 0

      // Dashed lines to axes
      ctx.setLineDash([3, 5])
      ctx.strokeStyle = 'rgba(180, 130, 255, 0.3)'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(pointX, pointY)
      ctx.lineTo(pointX, curveBottom)
      ctx.stroke()
      ctx.beginPath()
      ctx.moveTo(pointX, pointY)
      ctx.lineTo(curveLeft, pointY)
      ctx.stroke()
      ctx.setLineDash([])

      // Percentage label
      const pct = (pointIntensity / maxIntensity) * 100
      ctx.fillStyle = '#b482ff'
      ctx.font = '15px monospace'
      ctx.textAlign = 'left'
      ctx.fillText(`${pct.toFixed(1)}%`, pointX + 12, pointY - 4)

      ctx.fillStyle = 'rgba(255, 255, 255, 0.5)'
      ctx.font = '12px monospace'
      ctx.fillText(`r = ${pointR.toFixed(2)}`, pointX + 12, pointY + 14)

      // Axis labels
      ctx.fillStyle = 'rgba(255, 255, 255, 0.4)'
      ctx.font = '12px monospace'
      ctx.textAlign = 'center'
      ctx.fillText('r (distance)', curveLeft + curveW / 2, curveBottom + 24)
      ctx.save()
      ctx.translate(curveLeft - 18, curveTop + curveH / 2)
      ctx.rotate(-Math.PI / 2)
      ctx.fillText('1/r\u00b2 intensity', 0, 0)
      ctx.restore()

      // Title
      ctx.fillStyle = '#ffd700'
      ctx.font = 'bold 22px monospace'
      ctx.textAlign = 'center'
      ctx.fillText('\u00b2  Powers & Inverse Square', w * 0.5, h * 0.06)
      ctx.fillStyle = 'rgba(255, 255, 255, 0.4)'
      ctx.font = '13px monospace'
      ctx.fillText('Exponential Growth  |  1/r\u00b2 Decay', w * 0.5, h * 0.06 + 22)
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
