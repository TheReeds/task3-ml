import { useEffect, useRef, type KeyboardEvent } from 'react'
import { FAMILY_LABEL, type DialStation } from './stations'

type Props = {
  stations: DialStation[]
  current: string
  tuning: boolean
  onTune: (id: string) => void
}

/** Banda de sintonía: las emisoras viven en un dial que se desliza; la aguja queda al centro. */
export function Dial({ stations, current, tuning, onTune }: Props) {
  const band = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = band.current?.querySelector<HTMLElement>(`[data-id="${CSS.escape(current)}"]`)
    const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches
    el?.scrollIntoView({ inline: 'center', block: 'nearest', behavior: reduce ? 'auto' : 'smooth' })
  }, [current, stations.length])

  function onKey(e: KeyboardEvent) {
    const i = stations.findIndex((s) => s.id === current)
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!d || i < 0) return
    e.preventDefault()
    const next = stations[(i + d + stations.length) % stations.length]
    onTune(next.id)
    band.current?.querySelector<HTMLElement>(`[data-id="${CSS.escape(next.id)}"]`)?.focus()
  }

  return (
    <div className="dial" data-tuning={tuning || undefined}>
      <div className="dial-needle" aria-hidden />
      <div ref={band} className="dial-band" role="radiogroup" aria-label="Emisoras" onKeyDown={onKey}>
        <div className="dial-pad" aria-hidden />
        {stations.map((s, i) => {
          const on = s.id === current
          const firstOfFamily = i === 0 || stations[i - 1].family !== s.family
          return (
            <button
              key={s.id}
              data-id={s.id}
              data-family={s.family}
              role="radio"
              aria-checked={on}
              tabIndex={on ? 0 : -1}
              className="dial-station"
              title={s.description}
              onClick={() => onTune(s.id)}
            >
              <span className="dial-family" aria-hidden={!firstOfFamily}>
                {firstOfFamily ? FAMILY_LABEL[s.family] : ''}
              </span>
              <span className="dial-freq" aria-hidden>
                {s.freq}
              </span>
              <span className="dial-name">{s.name}</span>
            </button>
          )
        })}
        <div className="dial-pad" aria-hidden />
      </div>
    </div>
  )
}
