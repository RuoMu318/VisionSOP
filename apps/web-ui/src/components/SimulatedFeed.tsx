import { useEffect, useRef } from 'react'
import type { StationSnapshot } from '../types'

interface Props {
  snapshot: StationSnapshot
}

export function SimulatedFeed({ snapshot }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const context = canvas.getContext('2d')
    if (!context) return
    let frame = 0
    let animation = 0

    const resize = () => {
      const bounds = canvas.getBoundingClientRect()
      const ratio = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = Math.max(1, Math.floor(bounds.width * ratio))
      canvas.height = Math.max(1, Math.floor(bounds.height * ratio))
      context.setTransform(ratio, 0, 0, ratio, 0, 0)
    }

    const draw = () => {
      const width = canvas.clientWidth
      const height = canvas.clientHeight
      frame += 1
      context.fillStyle = '#1b2224'
      context.fillRect(0, 0, width, height)

      context.strokeStyle = '#293235'
      context.lineWidth = 1
      for (let x = 0; x < width; x += 36) {
        context.beginPath(); context.moveTo(x, 0); context.lineTo(x, height); context.stroke()
      }
      for (let y = 0; y < height; y += 36) {
        context.beginPath(); context.moveTo(0, y); context.lineTo(width, y); context.stroke()
      }

      const fixtureW = Math.min(width * 0.56, 520)
      const fixtureH = Math.min(height * 0.56, 300)
      const fx = (width - fixtureW) / 2
      const fy = (height - fixtureH) / 2 + 10
      context.fillStyle = '#394447'
      context.strokeStyle = '#899496'
      context.lineWidth = 2
      context.fillRect(fx, fy, fixtureW, fixtureH)
      context.strokeRect(fx, fy, fixtureW, fixtureH)

      context.fillStyle = '#aeb8b8'
      context.fillRect(fx + fixtureW * 0.14, fy + fixtureH * 0.16, fixtureW * 0.72, fixtureH * 0.68)
      context.fillStyle = '#687577'
      context.fillRect(fx + fixtureW * 0.22, fy + fixtureH * 0.25, fixtureW * 0.56, fixtureH * 0.5)

      const completed = new Set(snapshot.cycle.completed_step_ids)
      if (completed.has('S03') || snapshot.cycle.current_step_id === 'S03') {
        context.beginPath()
        context.arc(fx + fixtureW * 0.5, fy + fixtureH * 0.5, 20, 0, Math.PI * 2)
        context.fillStyle = '#d8bc68'; context.fill()
        context.beginPath()
        context.arc(fx + fixtureW * 0.5, fy + fixtureH * 0.5, 9, 0, Math.PI * 2)
        context.fillStyle = '#687577'; context.fill()
      }
      if (completed.has('S04') || completed.has('S05')) {
        context.fillStyle = '#30383a'
        context.fillRect(fx + fixtureW * 0.48, fy + fixtureH * 0.33, fixtureW * 0.04, fixtureH * 0.34)
      }

      const stateColor = snapshot.cycle.lifecycle === 'ON_HOLD'
        ? '#d8a323'
        : snapshot.cycle.conformance === 'NONCONFORMING'
          ? '#d84c4c'
          : '#44b678'
      context.strokeStyle = stateColor
      context.lineWidth = 2
      context.strokeRect(fx + fixtureW * 0.1, fy + fixtureH * 0.1, fixtureW * 0.8, fixtureH * 0.8)

      context.font = '12px system-ui'
      context.fillStyle = stateColor
      context.fillRect(fx + fixtureW * 0.1, fy + fixtureH * 0.1 - 22, 154, 22)
      context.fillStyle = '#101516'
      context.fillText('product_in_fixture  0.98', fx + fixtureW * 0.1 + 7, fy + fixtureH * 0.1 - 7)

      const scanY = (frame * 0.8) % Math.max(height, 1)
      context.strokeStyle = 'rgba(83, 199, 138, 0.42)'
      context.lineWidth = 1
      context.beginPath(); context.moveTo(0, scanY); context.lineTo(width, scanY); context.stroke()

      context.fillStyle = 'rgba(10, 14, 15, 0.8)'
      context.fillRect(12, 12, 150, 27)
      context.fillStyle = '#f1f4f3'
      context.font = '600 12px system-ui'
      context.fillText('SIMULATION · CAM-01', 22, 30)

      context.fillStyle = 'rgba(10, 14, 15, 0.72)'
      context.fillRect(width - 156, height - 36, 144, 24)
      context.fillStyle = '#b8c2c0'
      context.font = '11px ui-monospace, monospace'
      context.fillText(`FRAME ${String(frame).padStart(6, '0')}`, width - 145, height - 20)
      animation = requestAnimationFrame(draw)
    }

    const observer = new ResizeObserver(resize)
    observer.observe(canvas)
    resize()
    draw()
    return () => {
      observer.disconnect()
      cancelAnimationFrame(animation)
    }
  }, [snapshot])

  return <canvas ref={canvasRef} className="simulated-feed" aria-label="ST01 模拟相机画面" />
}
