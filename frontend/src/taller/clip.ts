import { useCallback, useEffect, useRef, useState } from 'react'

// ── Reproductor de fragmentos (frase completa o un tramo exacto) ───────────
export function useClip() {
  const audio = useRef<HTMLAudioElement | null>(null)
  const [playing, setPlaying] = useState<string | null>(null)

  const stop = useCallback(() => {
    audio.current?.pause()
    setPlaying(null)
  }, [])

  const play = useCallback(
    (key: string, src: string | null, seg?: [number, number] | null) => {
      if (!src) return
      audio.current?.pause()
      const a = new Audio(src)
      audio.current = a
      setPlaying(key)
      const end = seg ? seg[1] + 60 : null
      if (seg) a.currentTime = Math.max(0, seg[0] - 60) / 1000
      const tick = () => {
        if (audio.current !== a) return
        if (end != null && a.currentTime * 1000 >= end) a.pause()
        if (!a.paused) requestAnimationFrame(tick)
      }
      a.onplaying = () => requestAnimationFrame(tick)
      a.onpause = a.onended = () => audio.current === a && setPlaying(null)
      a.play().catch(() => setPlaying(null))
    },
    [],
  )

  useEffect(() => stop, [stop])
  return { play, stop, playing }
}
