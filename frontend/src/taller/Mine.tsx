import { useEffect, useState } from 'react'
import { api, ApiError, storage } from '../lib/api'
import { Qu } from '../ui/bits'
import { STATUS, typeLabel, type Mine as MineItem } from './model'

const fmt = new Intl.DateTimeFormat('es-PE', { day: 'numeric', month: 'short' })
const str = (v: unknown) => (typeof v === 'string' && v ? v : null)

/** Qué propuso la persona, según el tipo. */
function describe(m: MineItem) {
  const p = m.payload
  const proposed = str(p.proposed) ?? str(p.gloss) ?? str(p.token) ?? str(p.text)
  return { original: str(p.original), proposed, lemma: str(p.lemma) }
}

export function Mine() {
  const hasToken = !!storage.get('cv.token')
  const [items, setItems] = useState<MineItem[] | null>(hasToken ? null : [])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!hasToken) return
    api<MineItem[]>('/contributions/mine', { auth: true }).then(setItems, (e: unknown) =>
      setError(e instanceof ApiError ? e.message : 'No se pudieron cargar tus aportes.'),
    )
  }, [hasToken])

  if (error) return <p role="alert" className="phase-card text-center">{error}</p>
  if (!items)
    return (
      <div className="space-y-2" aria-busy="true" aria-label="Cargando tus aportes">
        <div className="skeleton h-16 w-full" />
        <div className="skeleton h-16 w-full" />
      </div>
    )

  if (!items.length)
    return (
      <div className="phase-card text-center">
        <p className="font-qu text-2xl font-semibold">Aún no has aportado</p>
        <p className="mt-2 text-muted">
          Corrige una palabra mientras escuchas la Radio, aporta una palabra que falte en Radar o comparte tus frases en Dúo.
          Aquí verás qué pasó con cada aporte.
        </p>
        <div className="mt-4 flex flex-wrap justify-center gap-2">
          <a className="btn-soft" href="#/radio">
            Ir a la Radio
          </a>
          <a className="btn-soft" href="#/radar">
            Ir a Radar
          </a>
        </div>
      </div>
    )

  const accepted = items.filter((i) => i.status === 'accepted').length
  return (
    <div className="space-y-3">
      <p className="text-muted">
        <b className="text-ink">{items.length}</b> {items.length === 1 ? 'aporte' : 'aportes'} ·{' '}
        <b className="text-ink">{accepted}</b> {accepted === 1 ? 'aceptado' : 'aceptados'} por la comunidad
      </p>
      <ul className="space-y-2">
        {items.map((m) => {
          const d = describe(m)
          const s = STATUS[m.status]
          return (
            <li key={m.id} className="mine-row" data-status={m.status}>
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold tracking-wide text-muted uppercase">{typeLabel(m.type)}</span>
                <span className="text-xs text-muted">{fmt.format(new Date(m.created_at))}</span>
              </div>
              <p className="mt-1">
                {d.original && (
                  <>
                    <del className="text-muted">{d.original}</del> →{' '}
                  </>
                )}
                {d.lemma && !d.original && (
                  <>
                    <Qu className="font-semibold">{d.lemma}</Qu>
                    {d.proposed && ' · '}
                  </>
                )}
                {d.proposed && <span className="font-bold">{d.proposed}</span>}
              </p>
              <p className="mt-1 text-sm">
                <span className="status-pill">{s.label}</span> <span className="text-muted">{s.detail}</span>
              </p>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
