import { useState, type FormEvent } from 'react'
import { api, ApiError } from '../lib/api'
import type { Entry, Module, Token } from '../lib/types'
import { Icon, Qu } from '../ui/bits'
import { toast } from '../ui/toast'

export type Correction =
  | { kind: 'transcription'; entry: Entry; token: Token }
  | { kind: 'translation'; entry: Entry }
  | { kind: 'gloss'; lexeme: { id: number; lemma: string; gloss: string | null } }
  /** `suggestion` es el cuerpo que devuelve el servidor (p. ej. Radar), listo para enviar. */
  | { kind: 'new_lemma'; suggestion: { lemma: string } & Record<string, unknown> }

type Props = {
  correction: Correction
  module: Module
  onDone: () => void
  onStale?: () => void
}

function describe(c: Correction) {
  switch (c.kind) {
    case 'transcription':
      return { title: '¿Cómo se escribe?', label: 'Debería decir', original: c.token.token, qu: true }
    case 'translation':
      return {
        title: 'Mejorar la traducción',
        label: 'Traducción propuesta',
        original: c.entry.translation?.text ?? '',
        qu: false,
      }
    case 'gloss':
      return { title: `¿Qué significa «${c.lexeme.lemma}»?`, label: 'Significado propuesto', original: c.lexeme.gloss ?? '', qu: false }
    case 'new_lemma':
      return { title: `Aporta «${c.suggestion.lemma}»`, label: 'Qué significa, en español (opcional)', original: '', qu: false }
  }
}

function body(c: Correction, value: string) {
  switch (c.kind) {
    case 'transcription':
      return { type: 'transcription_fix', entry_id: c.entry.id, position: c.token.position, token: value }
    case 'translation':
      return { type: 'translation_fix', translation_id: c.entry.translation!.id, text: value }
    case 'gloss':
      return { type: 'gloss_fix', lexeme_id: c.lexeme.id, gloss: value }
    case 'new_lemma':
      return value ? { ...c.suggestion, gloss: value } : c.suggestion
  }
}

/** Patrón "aportar/corregir": el dato actual arriba, la propuesta abajo, un botón. */
export function CorrectForm({ correction, module, onDone, onStale }: Props) {
  const d = describe(correction)
  const isNew = correction.kind === 'new_lemma'
  const [value, setValue] = useState(d.original)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const long = correction.kind === 'translation'
  const clean = value.trim()

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!isNew && (!clean || clean === d.original.trim())) return setError('Escribe una versión distinta a la actual.')
    setBusy(true)
    setError(null)
    try {
      await api('/contributions', { method: 'POST', body: body(correction, clean), auth: true, module })
      toast('¡Yusulpayki! Tu aporte pasará por revisión comunitaria.')
      onDone()
    } catch (err) {
      if (err instanceof ApiError && err.status === 404 && onStale) {
        toast('Alguien ya corrigió este dato. Cargamos la versión nueva.', 'error')
        onStale()
        onDone()
      } else setError(err instanceof ApiError ? err.message : 'No se pudo enviar. Inténtalo otra vez.')
    } finally {
      setBusy(false)
    }
  }

  const Field = long ? 'textarea' : 'input'
  return (
    <form onSubmit={submit} className="space-y-4">
      <h2 className="font-qu text-2xl font-semibold">{d.title}</h2>
      {isNew ? (
        <p className="text-muted">
          Esta palabra aún no está en el vocabulario. Si la usas o la conoces, súmala: la comunidad la revisará.
        </p>
      ) : (
        <div>
          <p className="eyebrow mb-1">Dice ahora</p>
          {d.qu ? <Qu className="text-xl line-through decoration-tint/60">{d.original}</Qu> : <p className="text-lg">{d.original || '—'}</p>}
        </div>
      )}
      <label className="block">
        <span className="eyebrow mb-1 block">{d.label}</span>
        <Field
          className="field"
          lang={d.qu ? 'qu' : 'es'}
          value={value}
          autoFocus
          autoCapitalize="off"
          spellCheck={!d.qu}
          rows={long ? 3 : undefined}
          maxLength={long ? 2000 : d.qu ? 128 : 500}
          placeholder={isNew ? 'p. ej. auto, carro' : undefined}
          onChange={(e: { target: { value: string } }) => setValue(e.target.value)}
        />
      </label>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <p className="text-sm text-muted">Sin registro. La comunidad revisa cada aporte antes de que entre al corpus.</p>
      <button className="btn-primary w-full" disabled={busy}>
        {busy ? 'Enviando…' : (
          <>
            <Icon name="check" className="size-5" /> {isNew ? 'Aportar palabra' : 'Enviar corrección'}
          </>
        )}
      </button>
    </form>
  )
}
