import { useEffect, useRef } from 'react'

export default function DeltaCanvas() {
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

    // ADSR parameters
    const sustainLevel = 0.6
    const decayLevel = 0.6
    const releaseEnd = 0

    const draw = (dt) => {
      t += dt
      ctx.clearRect(0, 0, w, h)

      // Attack time oscillates
      const attackTime = 0.08 + 0.35 * (0.5 + 0.5 * Math.sin(t * 0.7))
      const decayTime = 0.2
      const sustainTime = 0.35
      const releaseTime = 0.25
      const totalTime = attackTime + decayTime + sustainTime + releaseTime

      // --- ADSR Envelope (upper area) ---
      const envLeft = w * 0.06
      const envRight = w * 0.65
      const envTop = h * 0.15
      const envBottom = h * 0.62
      const envW = envRight - envLeft
      const envH = envBottom - envTop

      // Axes
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)'
      ctx.lineWidth = 1
      ctx.beginPath()
      ctx.moveTo(envLeft, envBottom)
      ctx.lineTo(envRight, envBottom)
      ctx.stroke()
      ctx.beginPath()
      ctx.moveTo(envLeft, envTop)
      ctx.lineTo(envLeft, envBottom)
      ctx.stroke()

      // Build ADSR path
      const adsrPoints = []
      const addPoint = (tNorm, val) => {
        adsrPoints.push({
          x: envLeft + tNorm * envW,
          y: envBottom - val * envH,
          t: tNorm,
          val
        })
      }

      // Start
      addPoint(0, 0)
      // Attack peak
      const aEnd = attackTime / totalTime
      addPoint(aEnd, 1.0)
      // Decay to sustain
      const dEnd = (attackTime + decayTime) / totalTime
      addPoint(dEnd, sustainLevel)
      // Sustain
      const sEnd = (attackTime + decayTime + sustainTime) / totalTime
      addPoint(sEnd, sustainLevel)
      // Release
      addPoint(1.0, 0)

      // Draw envelope fill
      ctx.beginPath()
      ctx.moveTo(adsrPoints[0].x, adsrPoints[0].y)
      for (let i = 1; i < adsrPoints.length; i++) {
        ctx.lineTo(adsrPoints[i].x, adsrPoints[i].y)
      }
      ctx.lineTo(envRight, envBottom)
      ctx.lineTo(envLeft, envBottom)
      ctx.closePath()
      const envGrad = ctx.createLinearGradient(envLeft, envTop, envLeft, envBottom)
      envGrad.addColorStop(0, 'rgba(0, 220, 150, 0.2)')
      envGrad.addColorStop(1, 'rgba(0, 220, 150, 0.02)')
      ctx.fillStyle = envGrad
      ctx.fill()

      // Draw envelope line
      ctx.beginPath()
      ctx.moveTo(adsrPoints[0].x, adsrPoints[0].y)
      for (let i = 1; i < adsrPoints.length; i++) {
        ctx.lineTo(adsrPoints[i].x, adsrPoints[i].y)
      }
      ctx.strokeStyle = 'rgba(0, 220, 150, 0.9)'
      ctx.lineWidth = 2.5
      ctx.stroke()

      // ADSR section labels
      const sections = [
        { label: 'A', start: 0, end: aEnd },
        { label: 'D', start: aEnd, end: dEnd },
        { label: 'S', start: dEnd, end: sEnd },
        { label: 'R', start: sEnd, end: 1.0 },
      ]
      sections.forEach(sec => {
        const mx = envLeft + (sec.start + sec.end) / 2 * envW
        ctx.fillStyle = 'rgba(255, 255, 255, 0.3)'
        ctx.font = '14px monospace'
        ctx.textAlign = 'center'
        ctx.fillText(sec.label, mx, envBottom + 20)

        // Separator lines
        if (sec.start > 0) {
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)'
          ctx.setLineDash([3, 5])
          ctx.beginPath()
          ctx.moveTo(envLeft + sec.start * envW, envTop)
          ctx.lineTo(envLeft + sec.start * envW, envBottom)
          ctx.stroke()
          ctx.setLineDash([])
        }
      })

      // Playhead
      const playT = (t * 0.25) % 1
      const playX = envLeft + playT * envW

      // Get envelope value at playhead
      let envVal = 0
      for (let i = 0; i < adsrPoints.length - 1; i++) {
        if (playT >= adsrPoints[i].t && playT <= adsrPoints[i + 1].t) {
          const localT = (playT - adsrPoints[i].t) / (adsrPoints[i + 1].t - adsrPoints[i].t)
          envVal = adsrPoints[i].val + localT * (adsrPoints[i + 1].val - adsrPoints[i].val)
          break
        }
      }

      // Playhead line
      ctx.strokeStyle = 'rgba(255, 215, 0, 0.6)'
      ctx.lineWidth = 2
      ctx.beginPath()
      ctx.moveTo(playX, envTop)
      ctx.lineTo(playX, envBottom)
      ctx.stroke()

      // Playhead dot on curve
      const playY = envBottom - envVal * envH
      ctx.shadowColor = 'rgba(255, 215, 0, 0.6)'
      ctx.shadowBlur = 12
      ctx.fillStyle = '#ffd700'
      ctx.beginPath()
      ctx.arc(playX, playY, 6, 0, Math.PI * 2)
      ctx.fill()
      ctx.shadowBlur = 0

      // Value label
      ctx.fillStyle = '#ffd700'
      ctx.font = '13px monospace'
      ctx.textAlign = 'left'
      ctx.fillText(`val = ${envVal.toFixed(2)}`, playX + 12, playY - 8)

      // --- Slope calculation ---
      const epsilon = 0.001
      let envValNext = 0
      const playT2 = Math.min(playT + epsilon, 1)
      for (let i = 0; i < adsrPoints.length - 1; i++) {
        if (playT2 >= adsrPoints[i].t && playT2 <= adsrPoints[i + 1].t) {
          const localT = (playT2 - adsrPoints[i].t) / (adsrPoints[i + 1].t - adsrPoints[i].t)
          envValNext = adsrPoints[i].val + localT * (adsrPoints[i + 1].val - adsrPoints[i].val)
          break
        }
      }
      const slope = (envValNext - envVal) / epsilon

      // --- RIGHT: Slope gauge ---
      const gaugeX = w * 0.82
      const gaugeY = h * 0.38
      const gaugeR = Math.min(w * 0.12, h * 0.18)

      // Gauge arc background
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)'
      ctx.lineWidth = 8
      ctx.beginPath()
      ctx.arc(gaugeX, gaugeY, gaugeR, Math.PI, 0)
      ctx.stroke()

      // Colored arc sections
      const arcSections = [
        { start: Math.PI, end: Math.PI * 0.75, color: 'rgba(0, 200, 100, 0.6)' },      // positive steep
        { start: Math.PI * 0.75, end: Math.PI * 0.55, color: 'rgba(0, 200, 100, 0.3)' }, // positive mild
        { start: Math.PI * 0.55, end: Math.PI * 0.45, color: 'rgba(255, 255, 255, 0.2)' }, // near zero
        { start: Math.PI * 0.45, end: Math.PI * 0.25, color: 'rgba(255, 80, 80, 0.3)' },  // negative mild
        { start: Math.PI * 0.25, end: 0, color: 'rgba(255, 80, 80, 0.6)' },              // negative steep
      ]
      arcSections.forEach(sec => {
        ctx.strokeStyle = sec.color
        ctx.lineWidth = 8
        ctx.beginPath()
        ctx.arc(gaugeX, gaugeY, gaugeR, sec.start, sec.end, true)
        ctx.stroke()
      })

      // Needle — map slope to angle
      const maxSlope = 8
      const clampedSlope = Math.max(-maxSlope, Math.min(maxSlope, slope))
      const needleAngle = Math.PI * (1 - (clampedSlope + maxSlope) / (2 * maxSlope))

      const needleLen = gaugeR * 0.85
      const nx = gaugeX + Math.cos(needleAngle) * needleLen
      const ny = gaugeY - Math.abs(Math.sin(needleAngle)) * needleLen

      ctx.strokeStyle = '#ffd700'
      ctx.lineWidth = 2.5
      ctx.beginPath()
      ctx.moveTo(gaugeX, gaugeY)
      ctx.lineTo(nx, ny)
      ctx.stroke()

      // Needle center dot
      ctx.fillStyle = '#ffd700'
      ctx.beginPath()
      ctx.arc(gaugeX, gaugeY, 5, 0, Math.PI * 2)
      ctx.fill()

      // Needle tip
      ctx.shadowColor = 'rgba(255, 215, 0, 0.5)'
      ctx.shadowBlur = 10
      ctx.beginPath()
      ctx.arc(nx, ny, 4, 0, Math.PI * 2)
      ctx.fill()
      ctx.shadowBlur = 0

      // Slope value
      ctx.fillStyle = slope > 0.5 ? '#00dc96' : slope < -0.5 ? '#ff5050' : 'rgba(255, 255, 255, 0.7)'
      ctx.font = 'bold 18px monospace'
      ctx.textAlign = 'center'
      ctx.fillText(`\u0394 = ${slope.toFixed(1)}`, gaugeX, gaugeY + 30)

      // Label
      ctx.fillStyle = 'rgba(255, 255, 255, 0.4)'
      ctx.font = '12px monospace'
      ctx.fillText('instantaneous slope', gaugeX, gaugeY + 48)

      // Gauge min/max labels
      ctx.fillStyle = 'rgba(0, 200, 100, 0.5)'
      ctx.font = '11px monospace'
      ctx.textAlign = 'right'
      ctx.fillText(`+${maxSlope}`, gaugeX - gaugeR - 5, gaugeY + 5)
      ctx.fillStyle = 'rgba(255, 80, 80, 0.5)'
      ctx.textAlign = 'left'
      ctx.fillText(`-${maxSlope}`, gaugeX + gaugeR + 5, gaugeY + 5)

      // --- Bottom: Tangent line visualization ---
      const tangentY = h * 0.78
      ctx.fillStyle = 'rgba(255, 255, 255, 0.3)'
      ctx.font = '12px monospace'
      ctx.textAlign = 'center'

      // Draw small tangent line at the playhead point
      const tanLen = 40
      const tanAngle = Math.atan(slope * 0.15)
      ctx.strokeStyle = 'rgba(255, 215, 0, 0.5)'
      ctx.lineWidth = 1.5
      ctx.beginPath()
      ctx.moveTo(playX - Math.cos(tanAngle) * tanLen, playY + Math.sin(tanAngle) * tanLen)
      ctx.lineTo(playX + Math.cos(tanAngle) * tanLen, playY - Math.sin(tanAngle) * tanLen)
      ctx.stroke()

      // Attack time indicator
      ctx.fillStyle = 'rgba(0, 220, 150, 0.5)'
      ctx.font = '12px monospace'
      ctx.textAlign = 'center'
      ctx.fillText(`attack = ${(attackTime * 1000).toFixed(0)}ms`, envLeft + aEnd * envW / 2, envTop - 10)

      // Title
      ctx.fillStyle = '#ffd700'
      ctx.font = 'bold 22px monospace'
      ctx.textAlign = 'center'
      ctx.fillText('\u0394  Rate of Change', w * 0.5, h * 0.06)
      ctx.fillStyle = 'rgba(255, 255, 255, 0.4)'
      ctx.font = '13px monospace'
      ctx.fillText('ADSR Envelope  |  Instantaneous Slope', w * 0.5, h * 0.06 + 22)
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
