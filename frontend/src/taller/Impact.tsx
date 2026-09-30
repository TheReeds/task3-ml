import { useEffect, useState } from 'react'
import { API_BASE, api, ApiError } from '../lib/api'
import { agreement, typeLabel, type Impact as ImpactData } from './model'

const nf = new Intl.NumberFormat('es-PE')
const fmtDay = new Intl.DateTimeFormat('es-PE', { day: 'numeric', month: 'short', timeZone: 'UTC' })
const dayLabel = (d: string) => fmtDay.format(new Date(`${d}T12:00:00Z`))

export function Impact({ onReview }: { onReview: () => void }) {
  const [data, setData] = useState<ImpactData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api<ImpactData>('/taller/impact?days=30').then(setData, (e: unknown) =>
      setError(e instanceof ApiError ? e.message : 'No se pudo cargar el panel.'),
    )
  }, [])

  if (error) return <p role="alert" className="phase-card text-center">{error}</p>
  if (!data)
    return (
      <div className="space-y-3" aria-busy="true" aria-label="Cargando el impacto">
        <div className="skeleton h-28 w-full" />
        <div className="skeleton h-40 w-full" />
      </div>
    )

  const c = data.contributions
  const ag = agreement(data.fleiss_kappa)
  const byType = Object.entries(data.accepted_by_type).sort((a, b) => b[1] - a[1])
  const maxType = Math.max(1, ...byType.map(([, n]) => n))
  const quiet = data.timeline.every((d) => !d.created && !d.accepted && !d.reviews)

  return (
    <div className="space-y-5">
      <section className="phase-card">
        <p className="eyebrow">Lo que la comunidad sumó al corpus</p>
        <p className="hero-number">{nf.format(c.accepted)}</p>
        <p className="text-muted">
          {c.accepted === 1 ? 'aporte aceptado' : 'aportes aceptados'} por consenso
          {c.accepted === 0 && ' — el primero puede salir de tu próxima revisión'}
        </p>
        <div className="mt-4 grid grid-cols-2 gap-3">
          <Tile value={c.pending} label="esperando revisión" />
          <Tile value={data.reviews} label="juicios emitidos" />
          <Tile value={data.contributors} label={data.contributors === 1 ? 'persona aportó' : 'personas aportaron'} />
          <Tile value={data.reviewers} label={data.reviewers === 1 ? 'persona revisó' : 'personas revisaron'} />
        </div>
        {c.pending > 0 && (
          <button className="btn-primary mt-4 w-full" onClick={onReview}>
            Revisar lo pendiente
          </button>
        )}
      </section>

      <section className="phase-card">
        <p className="eyebrow">¿Cuánto coinciden quienes revisan?</p>
        <p className="mt-1 text-xl font-bold">{ag.label}</p>
        <div className="agree" aria-hidden>
          {[1, 2, 3, 4, 5].map((l) => (
            <span key={l} data-on={l <= ag.level || undefined} />
          ))}
        </div>
        <p className="mt-2 text-sm text-muted">{ag.detail}</p>
      </section>

      <section className="phase-card">
        <p className="eyebrow">Últimos 30 días</p>
        {quiet ? (
          <p className="mt-2 text-muted">Todavía no hubo actividad en estos días. Cada corrección y cada revisión aparecerán aquí.</p>
        ) : (
          <>
            <Columns title="Aportes recibidos" days={data.timeline} field="created" />
            <Columns title="Aportes aceptados" days={data.timeline} field="accepted" />
            <Columns title="Revisiones" days={data.timeline} field="reviews" />
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer font-bold">Ver como tabla</summary>
              <table className="data-table mt-2">
                <thead>
                  <tr>
                    <th scope="col">Día</th>
                    <th scope="col">Recibidos</th>
                    <th scope="col">Aceptados</th>
                    <th scope="col">Revisiones</th>
                  </tr>
                </thead>
                <tbody>
                  {data.timeline.map((d) => (
                    <tr key={d.day}>
                      <th scope="row">{dayLabel(d.day)}</th>
                      <td>{d.created}</td>
                      <td>{d.accepted}</td>
                      <td>{d.reviews}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </details>
          </>
        )}
      </section>

      {byType.length > 0 && (
        <section className="phase-card">
          <p className="eyebrow mb-3">Aceptados por tipo</p>
          <ul className="space-y-2">
            {byType.map(([t, n]) => (
              <li key={t} className="hbar">
                <span className="text-sm">{typeLabel(t)}</span>
                <span className="hbar-track">
                  <span className="hbar-fill" style={{ width: `${(n / maxType) * 100}%` }} />
                </span>
                <span className="text-sm font-bold tabular-nums">{nf.format(n)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="phase-card">
        <p className="eyebrow">De vuelta a la comunidad</p>
        <p className="mt-1">
          Todo lo aprobado se puede descargar en formato abierto, con atribución por seudónimo anónimo. Es de quienes lo
          hicieron.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          <a className="btn-primary" href={`${API_BASE}/taller/export?format=csv`} download>
            Descargar CSV
          </a>
          <a className="btn-soft" href={`${API_BASE}/taller/export?format=jsonl`} download>
            Descargar JSONL
          </a>
        </div>
        <p className="mt-2 text-xs text-muted">
          {c.accepted ? `Incluye ${nf.format(c.accepted)} ${c.accepted === 1 ? 'aporte' : 'aportes'}.` : 'Por ahora el archivo está vacío.'}
        </p>
      </section>
    </div>
  )
}

function Tile({ value, label }: { value: number; label: string }) {
  return (
    <div className="tile">
      <p className="text-2xl font-bold tabular-nums">{nf.format(value)}</p>
      <p className="text-sm text-muted">{label}</p>
    </div>
  )
}

type Day = ImpactData['timeline'][number]

/** Columnas de una sola serie (sin leyenda: el título la nombra). Tooltip por barra; los valores también están en la tabla. */
function Columns({ title, days, field }: { title: string; days: Day[]; field: 'created' | 'accepted' | 'reviews' }) {
  const [hover, setHover] = useState<number | null>(null)
  const values = days.map((d) => d[field])
  const max = Math.max(...values)
  const peak = values.lastIndexOf(max)
  const total = values.reduce((a, b) => a + b, 0)
  const H = 56
  return (
    <figure className="mt-4">
      <figcaption className="flex items-baseline justify-between text-sm">
        <span className="font-bold">{title}</span>
        <span className="text-muted tabular-nums">{nf.format(total)} en total</span>
      </figcaption>
      <div className="cols" style={{ height: H + 18 }} onPointerLeave={() => setHover(null)}>
        {days.map((d, i) => {
          const v = values[i]
          const h = max ? Math.max(v ? 3 : 0, (v / max) * H) : 0
          return (
            <button
              key={d.day}
              className="col"
              aria-label={`${dayLabel(d.day)}: ${v}`}
              onPointerEnter={() => setHover(i)}
              onFocus={() => setHover(i)}
              onBlur={() => setHover(null)}
            >
              {max > 0 && i === peak && v > 0 && (
                <span className="col-label" style={{ bottom: h + 2 }}>
                  {v}
                </span>
              )}
              <span className="col-bar" data-hover={hover === i || undefined} style={{ height: h }} />
            </button>
          )
        })}
        {hover != null && (
          <span className="col-tip" style={{ left: `${((hover + 0.5) / days.length) * 100}%` }} role="status">
            {dayLabel(days[hover].day)} · <b>{values[hover]}</b>
          </span>
        )}
      </div>
      <div className="flex justify-between text-xs text-muted">
        <span>{dayLabel(days[0].day)}</span>
        <span>{dayLabel(days[days.length - 1].day)}</span>
      </div>
    </figure>
  )
}
