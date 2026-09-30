import { Fragment, useEffect, useRef, useState, type CSSProperties } from 'react'
import type { Entry, Token } from '../lib/types'

type Props = {
  entry: Entry
  audio: HTMLAudioElement
  onWord: (t: Token) => void
}

const PUNCT = /^[.,;:!?)»”…]+$/

/**
 * Frase con resaltado sincronizado. Un bucle rAF lee audio.currentTime (más fino que
 * timeupdate) y escribe el avance dentro de la palabra directo en el DOM (--p); React solo
 * re-renderiza cuando cambia la palabra.
 */
export function Phrase({ entry, audio, onWord }: Props) {
  const tokens = entry.tokens
  const [cursor, setCursor] = useState({ i: -1, inside: false })
  const words = useRef<(HTMLButtonElement | null)[]>([])
  const bar = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let raf = 0
    let last = { i: -2, inside: false }
    const total = entry.duration_ms || audio.duration * 1000 || 1
    const frame = () => {
      const t = audio.currentTime * 1000
      let i = -1
      for (let k = 0; k < tokens.length && tokens[k].start_ms <= t; k++) i = k
      const inside = i >= 0 && t < tokens[i].end_ms
      if (i !== last.i || inside !== last.inside) {
        last = { i, inside }
        setCursor(last)
      }
      const el = i >= 0 ? words.current[i] : null
      if (el) {
        const tk = tokens[i]
        const p = inside ? (t - tk.start_ms) / Math.max(1, tk.end_ms - tk.start_ms) : 1
        el.style.setProperty('--p', p.toFixed(3))
      }
      if (bar.current) bar.current.style.transform = `scaleX(${Math.min(1, t / total).toFixed(4)})`
      raf = requestAnimationFrame(frame)
    }
    raf = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(raf)
  }, [audio, entry, tokens])

  return (
    <div>
      <p className="phrase" lang="qu" data-long={entry.text.length > 60 || undefined}>
        {tokens.map((tk, i) => {
          const state = i < cursor.i ? 'past' : i === cursor.i ? (cursor.inside ? 'active' : 'past') : 'future'
          return (
            <Fragment key={`${entry.id}-${tk.position}`}>
              {i > 0 && !PUNCT.test(tk.token) && ' '}
              <button
                ref={(el) => {
                  words.current[i] = el
                }}
                className="word"
                data-state={state}
                data-lemma={tk.lexeme_id != null || undefined}
                style={{ '--i': i } as CSSProperties}
                onClick={() => onWord(tk)}
                aria-current={state === 'active' ? 'true' : undefined}
              >
                {tk.token}
              </button>
            </Fragment>
          )
        })}
      </p>
      <div className="phrase-track" aria-hidden>
        <div ref={bar} className="phrase-bar" />
        {tokens.map((tk) => (
          <span
            key={tk.position}
            className="phrase-tick"
            style={{ left: `${(tk.start_ms / (entry.duration_ms || 1)) * 100}%` }}
          />
        ))}
      </div>
    </div>
  )
}
