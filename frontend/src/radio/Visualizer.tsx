import { useEffect, useRef } from 'react'

type Props = { analyser: AnalyserNode | null; audio: HTMLAudioElement; size?: number }

const BARS = 56

/**
 * Onda circular alrededor del botón. Con analizador usa el espectro real; sin él (iOS),
 * se aproxima con una envolvente suave mientras suena. También publica --lvl (0..1) en
 * <html> para que el fondo respire con la voz.
 */
export function Visualizer({ analyser, audio, size = 208 }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const c = canvas.current
    const g = c?.getContext('2d')
    if (!c || !g) return
    const dpr = Math.min(2, window.devicePixelRatio || 1)
    c.width = c.height = size * dpr
    g.scale(dpr, dpr)

    const reduce = matchMedia('(prefers-reduced-motion: reduce)')
    const bins = new Uint8Array(analyser?.frequencyBinCount ?? 64)
    const smooth = new Float32Array(BARS)
    const root = document.documentElement.style
    let color = getComputedStyle(c).color
    let frame = 0
    let raf = 0
    let lastLvl = -1

    const draw = (now: number) => {
      if (++frame % 30 === 0) color = getComputedStyle(c).color
      const playing = !audio.paused
      let sum = 0

      if (analyser) analyser.getByteFrequencyData(bins)
      for (let b = 0; b < BARS; b++) {
        // Espejo: la mitad izquierda refleja la derecha para una forma simétrica.
        const k = b < BARS / 2 ? b : BARS - 1 - b
        let v: number
        if (analyser) v = bins[2 + Math.floor((k / (BARS / 2)) * 30)] / 255
        else v = playing ? 0.35 + 0.3 * Math.sin(now / 170 + k * 0.7) * Math.sin(now / 410 + k) : 0
        smooth[b] += (v - smooth[b]) * 0.35
        sum += smooth[b]
      }
      const lvl = sum / BARS
      if (Math.abs(lvl - lastLvl) > 0.01) {
        root.setProperty('--lvl', lvl.toFixed(3))
        lastLvl = lvl
      }

      g.clearRect(0, 0, size, size)
      const cx = size / 2
      const r0 = size * 0.3
      g.strokeStyle = color
      g.lineCap = 'round'
      g.lineWidth = 2.5
      for (let b = 0; b < BARS; b++) {
        const a = (b / BARS) * Math.PI * 2 - Math.PI / 2
        const len = 3 + (reduce.matches ? lvl : smooth[b]) * size * 0.17
        g.globalAlpha = 0.35 + smooth[b] * 0.65
        g.beginPath()
        g.moveTo(cx + Math.cos(a) * r0, cx + Math.sin(a) * r0)
        g.lineTo(cx + Math.cos(a) * (r0 + len), cx + Math.sin(a) * (r0 + len))
        g.stroke()
      }
      raf = requestAnimationFrame(draw)
    }
    raf = requestAnimationFrame(draw)
    return () => {
      cancelAnimationFrame(raf)
      root.setProperty('--lvl', '0')
    }
  }, [analyser, audio, size])

  return <canvas ref={canvas} className="viz" style={{ width: size, height: size }} aria-hidden />
}
