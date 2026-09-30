import type { ComponentProps } from 'react'
import type { Origin } from '../lib/types'

/** Texto en quechua: siempre lang="qu" y tipografía de protagonista. */
export function Qu({ className = '', ...rest }: ComponentProps<'span'>) {
  return <span lang="qu" className={`font-qu ${className}`} {...rest} />
}

const ORIGIN_LABEL: Record<string, { text: string; title: string }> = {
  synthetic: { text: 'voz sintética', title: 'Audio generado por computadora mientras llega el corpus grabado' },
  model: { text: 'traducción automática', title: 'Traducción propuesta por un modelo; puede tener errores' },
  community: { text: 'corregido por la comunidad', title: 'Validado por revisión comunitaria' },
}

/** Marca discreta de procedencia del dato. No muestra nada para datos originales del corpus. */
export function Provenance({ origin }: { origin: Origin | null | undefined }) {
  const o = origin ? ORIGIN_LABEL[origin] : undefined
  if (!o) return null
  return (
    <span className="chip" data-origin={origin} title={o.title}>
      <span className="chip-dot" aria-hidden />
      {o.text}
    </span>
  )
}

type IconName = 'replay' | 'play' | 'pause' | 'next' | 'repeat' | 'speaker' | 'pencil' | 'eye' | 'eye-off' | 'close' | 'check'

const PATHS: Record<IconName, string> = {
  replay: 'M4.5 12a7.5 7.5 0 1 0 2.2-5.3M4.5 4.5v4h4',
  play: 'M8 5.5v13a1 1 0 0 0 1.5.86l10.4-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5Z',
  pause: 'M7 5h3.5v14H7zM13.5 5H17v14h-3.5z',
  next: 'M5 5.8v12.4a.8.8 0 0 0 1.25.66L15 12.66a.8.8 0 0 0 0-1.32L6.25 5.14A.8.8 0 0 0 5 5.8ZM17 5h2.5v14H17z',
  repeat: 'M4 12a6 6 0 0 1 6-6h8m0 0-3-3m3 3-3 3M20 12a6 6 0 0 1-6 6H6m0 0 3 3m-3-3 3-3',
  speaker: 'M4 9.5h3.5L12 5.5v13l-4.5-4H4zM15.5 9a4 4 0 0 1 0 6M18 6.5a7.5 7.5 0 0 1 0 11',
  pencil: 'M4 20h4L19 9l-4-4L4 16v4ZM13.5 6.5l4 4',
  eye: 'M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Zm9.5 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z',
  'eye-off': 'M3 3l18 18M10.6 5.6A9.7 9.7 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-3 3.7M6.3 6.9A16.6 16.6 0 0 0 2.5 12S6 18.5 12 18.5c1.6 0 3-.4 4.2-1M9.9 9.9a3 3 0 0 0 4.2 4.2',
  close: 'M6 6l12 12M18 6 6 18',
  check: 'M5 12.5l4.5 4.5L19 7.5',
}
const FILLED: IconName[] = ['play', 'pause', 'next']

export function Icon({ name, className = 'size-5' }: { name: IconName; className?: string }) {
  const filled = FILLED.includes(name)
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      aria-hidden
      fill={filled ? 'currentColor' : 'none'}
      stroke={filled ? 'none' : 'currentColor'}
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={PATHS[name]} />
    </svg>
  )
}
