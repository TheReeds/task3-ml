import qrcode from 'qrcode-generator'
import { useMemo, useState, type ReactNode } from 'react'
import { mediaUrl } from '../lib/api'
import type { DuoImage } from './useDuoRoom'

/** Imagen de Wikimedia Commons con su atribución (obligatoria) tras un botón ⓘ. */
export function Photo({ img, alt, className = '', children }: { img: DuoImage; alt: string; className?: string; children?: ReactNode }) {
  const [info, setInfo] = useState(false)
  const a = img.attribution
  return (
    <figure className={`photo ${className}`}>
      <img src={mediaUrl(img.url)} alt={alt} decoding="async" draggable={false} />
      {children}
      <button
        type="button"
        className="photo-info"
        aria-expanded={info}
        aria-label="Autoría y licencia de la imagen"
        onClick={(e) => {
          e.stopPropagation()
          setInfo(!info)
        }}
      >
        i
      </button>
      {info && (
        <figcaption className="photo-credit">
          {a.author ?? 'Autoría desconocida'} · {a.license ?? 'licencia libre'}
          {a.source && (
            <>
              {' · '}
              <a href={a.source} target="_blank" rel="noopener noreferrer">
                Wikimedia Commons
              </a>
            </>
          )}
        </figcaption>
      )}
    </figure>
  )
}

/**
 * Khipu de la sesión: una cuerda principal y una colgante por ronda jugada.
 * Acierto = nudo; fallo = cuerda sin nudo. La última se anuda con animación.
 */
export function Khipu({ results }: { results: boolean[] }) {
  const shown = results.slice(-16)
  const step = 17
  const width = Math.max(120, 24 + shown.length * step)
  const wins = results.filter(Boolean).length
  return (
    <svg
      className="khipu"
      viewBox={`0 0 ${width} 50`}
      width={width}
      height={50}
      role="img"
      aria-label={results.length ? `${wins} aciertos en ${results.length} rondas` : 'Aún no han jugado rondas'}
    >
      <path className="khipu-main" d={`M4 8 Q ${width / 2} 13 ${width - 4} 8`} />
      {shown.map((ok, i) => {
        const x = 16 + i * step
        const last = i === shown.length - 1
        return (
          <g key={results.length - shown.length + i} className="khipu-pendant" data-ok={ok || undefined} data-new={last || undefined}>
            <path d={`M${x} 10 C ${x - 1.5} 22, ${x + 1.5} 32, ${x} ${ok ? 46 : 40}`} />
            {ok && (
              <g className="khipu-knot">
                <ellipse cx={x} cy={24} rx={3.4} ry={2.4} />
                <ellipse cx={x} cy={29} rx={3.4} ry={2.4} />
                <ellipse cx={x} cy={34} rx={3.4} ry={2.4} />
              </g>
            )}
          </g>
        )
      })}
    </svg>
  )
}

type Person = { label: string; connected: boolean; role: string | null; me?: boolean }

/** Las dos personas unidas por una cuerda: viva si ambas están conectadas. */
export function Cord({ you, partner, pulse }: { you: Person; partner: Person | null; pulse: boolean }) {
  const live = you.connected && !!partner?.connected
  return (
    <div className="cord" data-live={live || undefined} data-pulse={pulse || undefined}>
      <Avatar {...you} me />
      <div className="cord-line" aria-hidden>
        <span />
      </div>
      {partner ? (
        <Avatar {...partner} />
      ) : (
        <Avatar label="Pareja" connected={false} role={null} />
      )}
    </div>
  )
}

function Avatar({ label, connected, role, me }: Person) {
  return (
    <div className="avatar" data-me={me || undefined} data-connected={connected || undefined}>
      <span className="avatar-dot" aria-hidden>
        {me ? 'Tú' : ''}
      </span>
      <span className="text-sm font-bold">{label}</span>
      <span className="text-xs text-muted">{!connected ? (me ? 'reconectando…' : 'sin conexión') : (role ?? 'en la sala')}</span>
    </div>
  )
}

/** QR dibujado con currentColor: funciona en tema claro y oscuro. */
export function QR({ text, size = 168 }: { text: string; size?: number }) {
  const cells = useMemo(() => {
    const q = qrcode(0, 'M')
    q.addData(text)
    q.make()
    const n = q.getModuleCount()
    let d = ''
    for (let r = 0; r < n; r++) for (let c = 0; c < n; c++) if (q.isDark(r, c)) d += `M${c} ${r}h1v1h-1z`
    return { n, d }
  }, [text])
  return (
    <svg viewBox={`-2 -2 ${cells.n + 4} ${cells.n + 4}`} width={size} height={size} className="qr" role="img" aria-label="Código QR para entrar a la sala">
      <rect x={-2} y={-2} width={cells.n + 4} height={cells.n + 4} className="qr-bg" />
      <path d={cells.d} fill="currentColor" shapeRendering="crispEdges" />
    </svg>
  )
}

/** Código de sala en dos grupos, fácil de dictar: XV4 · FWR */
export function RoomCode({ code }: { code: string }) {
  return (
    <p className="room-code" aria-label={`Código de sala: ${code.split('').join(' ')}`}>
      <span aria-hidden>{code.slice(0, 3)}</span>
      <span aria-hidden className="room-code-sep">
        ·
      </span>
      <span aria-hidden>{code.slice(3)}</span>
    </p>
  )
}
