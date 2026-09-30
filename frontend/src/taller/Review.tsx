import { useCallback, useEffect, useRef, useState } from 'react'
import { api, ApiError } from '../lib/api'
import { Icon } from '../ui/bits'
import { toast } from '../ui/toast'
import { useClip } from './clip'
import { ItemCard } from './ItemCard'
import { loadFilters, loadStrand, saveFilters, saveStrand, TYPES, type ContribType, type ReviewItem, type ReviewResult, type Verdict } from './model'

type Load = { kind: 'loading' } | { kind: 'item'; item: ReviewItem } | { kind: 'empty' } | { kind: 'error'; text: string }

const VERDICTS: { v: Verdict; label: string; key: string; icon: 'close' | 'check' | null }[] = [
  { v: 'reject', label: 'Rechazar', key: 'r', icon: 'close' },
  { v: 'unsure', label: 'No estoy seguro', key: 'n', icon: null },
  { v: 'accept', label: 'Aceptar', key: 'a', icon: 'check' },
]

function feedback(v: Verdict, r: ReviewResult): string {
  if (r.status === 'accepted') return '¡Con tu voto se aceptó! Ya es parte del corpus.'
  if (r.status === 'rejected') return 'Con tu voto la comunidad decidió no incluirlo.'
  if (r.status === 'stale') return 'Se aceptó, pero ese dato ya había cambiado: quedó registrado.'
  if (v === 'unsure') return 'Gracias por la honestidad: no suma ni resta.'
  return 'Anotado. Faltan más opiniones para decidir.'
}

export function Review({ onGoImpact }: { onGoImpact: () => void }) {
  const [load, setLoad] = useState<Load>({ kind: 'loading' })
  const [filters, setFilters] = useState<ContribType[]>(loadFilters)
  const [strand, setStrand] = useState<Verdict[]>(loadStrand)
  const [leaving, setLeaving] = useState<Verdict | null>(null)
  const [note, setNote] = useState<{ text: string; win: boolean } | null>(null)
  const clip = useClip()
  const seq = useRef(0)

  /** Pide el siguiente ítem; solo la última petición en vuelo actualiza la pantalla. */
  const fetchNext = useCallback((types: ContribType[]) => {
    const n = ++seq.current
    const qs = types.map((t) => `type=${t}`).join('&')
    return api<ReviewItem | undefined>(`/taller/next${qs ? `?${qs}` : ''}`, { auth: true, module: 'taller' }).then(
      (item): void => {
        if (n === seq.current) setLoad(item ? { kind: 'item', item } : { kind: 'empty' })
      },
      (err: unknown): void => {
        if (n === seq.current)
          setLoad({ kind: 'error', text: err instanceof ApiError ? err.message : 'No se pudo cargar el siguiente aporte.' })
      },
    )
  }, [])

  useEffect(() => {
    fetchNext(filters).catch(() => {})
  }, [fetchNext, filters])

  const item = load.kind === 'item' ? load.item : null

  const judge = useCallback(
    async (v: Verdict) => {
      if (!item || leaving) return
      clip.stop()
      setLeaving(v)
      setNote(null)
      try {
        const r = await api<ReviewResult>('/taller/reviews', {
          method: 'POST',
          body: { contribution_id: item.contribution_id, verdict: v },
          auth: true,
          module: 'taller',
        })
        setNote({ text: feedback(v, r), win: r.status === 'accepted' })
        setStrand((s) => {
          const next = [...s, v]
          saveStrand(next)
          return next
        })
      } catch (err) {
        if (err instanceof ApiError && [403, 404, 409].includes(err.status)) {
          toast(err.status === 409 ? 'Ese aporte ya se resolvió. Vamos con el siguiente.' : err.message)
        } else {
          setLeaving(null)
          toast(err instanceof ApiError ? err.message : 'No se pudo registrar tu juicio. Inténtalo otra vez.', 'error')
          return
        }
      }
      setLoad({ kind: 'loading' })
      await fetchNext(filters)
      setLeaving(null)
    },
    [item, leaving, clip, fetchNext, filters],
  )

  // Atajos de teclado: A aceptar · N no estoy seguro · R rechazar
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      const t = e.target as HTMLElement
      if (t.closest('input, textarea, select, dialog')) return
      const hit = VERDICTS.find((x) => x.key === e.key.toLowerCase())
      if (hit && item) {
        e.preventDefault()
        void judge(hit.v)
      }
    }
    addEventListener('keydown', onKey)
    return () => removeEventListener('keydown', onKey)
  }, [item, judge])

  function applyFilters(next: ContribType[]) {
    saveFilters(next)
    setFilters(next)
    setLoad({ kind: 'loading' })
  }
  const toggle = (t: ContribType) => applyFilters(filters.includes(t) ? filters.filter((x) => x !== t) : [...filters, t])

  return (
    <div className="space-y-4">
      <nav className="days -mx-5" aria-label="Qué revisar">
        <button className="chip-btn shrink-0" aria-pressed={filters.length === 0} onClick={() => applyFilters([])}>
          Todo
        </button>
        {TYPES.map((t) => (
          <button key={t.id} className="chip-btn shrink-0" aria-pressed={filters.includes(t.id)} onClick={() => toggle(t.id)}>
            {t.short}
          </button>
        ))}
      </nav>

      <Strand verdicts={strand} />

      <div aria-live="polite" className="min-h-6">
        {note && (
          <p className="review-note" data-win={note.win || undefined} key={note.text + strand.length}>
            {note.text}
          </p>
        )}
      </div>

      {load.kind === 'loading' && (
        <div className="review-card space-y-3" aria-busy="true" aria-label="Buscando el siguiente aporte">
          <div className="skeleton h-6 w-40" />
          <div className="skeleton h-16 w-full" />
          <div className="skeleton h-24 w-full" />
        </div>
      )}

      {load.kind === 'error' && (
        <div className="phase-card text-center" role="alert">
          <p>{load.text}</p>
          <button className="btn-soft mt-3" onClick={() => void fetchNext(filters)}>
            Volver a intentar
          </button>
        </div>
      )}

      {load.kind === 'empty' && (
        <div className="phase-card text-center">
          <p className="font-qu text-3xl font-semibold">¡Al día!</p>
          <p className="mt-2 text-muted">
            {filters.length
              ? 'No queda nada de este tipo por revisar.'
              : 'No queda nada por revisar ahora mismo. Cada aporte que llegue aparecerá aquí.'}
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {filters.length > 0 && (
              <button className="btn-primary" onClick={() => applyFilters([])}>
                Ver todos los tipos
              </button>
            )}
            <a className="btn-soft" href="#/radio">
              Escuchar la Radio y corregir
            </a>
            <button className="btn-soft" onClick={onGoImpact}>
              Ver lo logrado
            </button>
          </div>
        </div>
      )}

      {item && (
        <div key={item.contribution_id} className="review-stage" data-leaving={leaving ?? undefined}>
          <ItemCard item={item} clip={clip} />
        </div>
      )}

      {item && (
        <div className="verdicts" role="group" aria-label="Tu juicio">
          {VERDICTS.map((x) => (
            <button key={x.v} className="verdict" data-v={x.v} onClick={() => void judge(x.v)} disabled={!!leaving} aria-keyshortcuts={x.key}>
              {x.icon ? <Icon name={x.icon} className="size-6" /> : <span className="verdict-q" aria-hidden>?</span>}
              <span>{x.label}</span>
            </button>
          ))}
        </div>
      )}
      {item && (
        <p className="hidden text-center text-xs text-muted sm:block">
          Atajos: <kbd>A</kbd> aceptar · <kbd>N</kbd> no estoy seguro · <kbd>R</kbd> rechazar
        </p>
      )}
    </div>
  )
}

/** Tu tramo de hoy: un hilo por cada revisión. Todos del mismo color: importa cuidar, no el veredicto. */
function Strand({ verdicts }: { verdicts: Verdict[] }) {
  const n = verdicts.length
  return (
    <div className="strand">
      <div className="strand-band" aria-hidden>
        {verdicts.slice(-40).map((_, i, arr) => (
          <i key={n - arr.length + i} data-new={i === arr.length - 1 || undefined} />
        ))}
        {n === 0 && <span className="strand-empty" />}
      </div>
      <p className="text-sm text-muted">
        {n === 0 ? 'Tu tramo de hoy empieza con el primer juicio.' : `Tu tramo de hoy: ${n} ${n === 1 ? 'revisión' : 'revisiones'}`}
      </p>
    </div>
  )
}
