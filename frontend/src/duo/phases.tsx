import { useState, type CSSProperties, type FormEvent } from 'react'
import { Icon, Qu } from '../ui/bits'
import { toast } from '../ui/toast'
import { roomLink, shareRoom } from './share'
import { Photo, QR, RoomCode } from './parts'
import type { DuoImage, DuoState, RoundView } from './useDuoRoom'

const MAX = 280

// ── Esperando a la otra persona ────────────────────────────────────────────
export function Invite({ code }: { code: string }) {
  return (
    <div className="phase-card text-center">
      <p className="eyebrow">Invita a alguien</p>
      <RoomCode code={code} />
      <p className="text-muted">Dicta este código, comparte el enlace o que escaneen el QR.</p>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        <button className="btn-primary" onClick={() => void shareRoom(code)}>
          Compartir enlace
        </button>
        <button
          className="btn-soft"
          onClick={() => void navigator.clipboard?.writeText(code).then(() => toast('Código copiado'), () => {})}
        >
          Copiar código
        </button>
      </div>
      <div className="mt-5 inline-block rounded-2xl bg-surface p-3 text-ink">
        <QR text={roomLink(code)} />
      </div>
      <p className="waiting-dots mt-4 text-sm font-bold" aria-live="polite">
        Esperando a tu pareja de juego
      </p>
    </div>
  )
}

// ── Listas para empezar ────────────────────────────────────────────────────
export function Ready({ youDescribe, onStart, busy }: { youDescribe: boolean; onStart: () => void; busy: boolean }) {
  return (
    <div className="phase-card text-center">
      <p className="font-qu text-3xl font-semibold">¡Ya están las dos personas!</p>
      <p className="mt-2 text-muted">
        Una describe una imagen en quechua; la otra la busca entre cuatro. Ganan o pierden juntas.
      </p>
      <p className="mt-3 font-bold">{youDescribe ? 'Empiezas describiendo tú.' : 'Empieza describiendo tu pareja; tú adivinas.'}</p>
      <button className="btn-primary mt-5" onClick={onStart} disabled={busy}>
        {busy ? 'Preparando…' : 'Empezar'}
      </button>
    </div>
  )
}

// ── Describir ──────────────────────────────────────────────────────────────
type DescribeProps = {
  round: RoundView
  consent: boolean
  busy: 'describe' | 'skip' | null
  error: string | null
  onDescribe: (text: string) => void
  onSkip: () => void
  onConsent: () => void
}

export function Describe({ round, consent, busy, error, onDescribe, onSkip, onConsent }: DescribeProps) {
  const [text, setText] = useState('')
  const clean = text.trim()

  function submit(e: FormEvent) {
    e.preventDefault()
    if (clean) onDescribe(clean)
  }

  return (
    <div className="space-y-4">
      <p className="phase-title">
        <span className="phase-tag">Te toca describir</span>
        Tu pareja no ve esta imagen
      </p>
      {round.image && <Photo img={round.image} alt="Imagen que debes describir" className="photo-hero" />}

      <form onSubmit={submit} className="space-y-2">
        <label htmlFor="duo-desc" className="eyebrow block">
          Descríbela en quechua, sin decir su nombre en español
        </label>
        <textarea
          id="duo-desc"
          className="field font-qu"
          lang="qu"
          rows={3}
          maxLength={MAX}
          placeholder="Kayqa…"
          autoCapitalize="sentences"
          spellCheck={false}
          value={text}
          aria-invalid={!!error}
          aria-describedby="duo-desc-help"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              if (clean) onDescribe(clean)
            }
          }}
        />
        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}
        <div id="duo-desc-help" className="flex items-center justify-between gap-2 text-sm text-muted">
          <button type="button" className="underline decoration-dotted underline-offset-4" onClick={onConsent}>
            {consent ? 'Tu frase se guardará para el corpus' : 'Tu frase no se guardará'}
          </button>
          <span className="tabular-nums">
            {text.length}/{MAX}
          </span>
        </div>
        <button className="btn-primary w-full" disabled={!clean || !!busy}>
          {busy === 'describe' ? 'Enviando…' : 'Enviar a mi pareja'}
        </button>
      </form>

      <details className="hints">
        <summary>¿Te falta una palabra?</summary>
        <p className="mt-2 text-sm text-muted">
          Palabras del corpus relacionadas con la imagen. Las glosas vienen del diccionario y pueden tener errores.
        </p>
        <ul className="mt-2 flex flex-wrap gap-2">
          {round.hints?.map((h) => (
            <li key={h.lemma} className="hint">
              <Qu className="font-semibold">{h.lemma}</Qu>
              {h.gloss && <span className="text-muted"> · {h.gloss}</span>}
            </li>
          ))}
        </ul>
      </details>

      <button className="btn-ghost mx-auto flex" onClick={onSkip} disabled={!!busy}>
        No sé describirla · pasar
      </button>
    </div>
  )
}

// ── Esperas ────────────────────────────────────────────────────────────────
export function WaitDescription() {
  return (
    <div className="phase-card text-center">
      <span className="phase-tag">Te toca adivinar</span>
      <div className="wait-cards" aria-hidden>
        {[0, 1, 2, 3].map((i) => (
          <span key={i} style={{ animationDelay: `${i * 120}ms` }} />
        ))}
      </div>
      <p className="waiting-dots font-bold" aria-live="polite">
        Tu pareja está mirando una imagen y la describe en quechua
      </p>
      <p className="mt-1 text-sm text-muted">Después elegirás cuál de cuatro imágenes es.</p>
    </div>
  )
}

export function WaitGuess({ round }: { round: RoundView }) {
  return (
    <div className="space-y-4">
      <p className="phase-title">
        <span className="phase-tag">Enviado</span>
        <span className="waiting-dots">Tu pareja está eligiendo</span>
      </p>
      {round.image && <Photo img={round.image} alt="La imagen que describiste" className="photo-hero photo-dim" />}
      <blockquote className="said">
        <Qu>{round.description}</Qu>
      </blockquote>
    </div>
  )
}

// ── Adivinar ───────────────────────────────────────────────────────────────
export function Guess({ round, busy, error, onGuess }: { round: RoundView; busy: boolean; error: string | null; onGuess: (id: number) => void }) {
  const [pick, setPick] = useState<number | null>(null)
  return (
    <div className="space-y-4">
      <p className="phase-title">
        <span className="phase-tag">Te toca adivinar</span>
        Tu pareja escribió:
      </p>
      <blockquote className="said said-big">
        <Qu>{round.description}</Qu>
      </blockquote>
      <p className="eyebrow">¿Cuál es? Toca una y confirma</p>
      <div className="options" role="radiogroup" aria-label="Cuatro imágenes">
        {round.options?.map((o, i) => (
          <Photo key={o.id} img={o} alt="" className="option">
            <button
              type="button"
              role="radio"
              aria-checked={pick === o.id}
              aria-label={`Imagen ${i + 1}`}
              className="option-pick"
              onClick={() => setPick(o.id)}
            />
          </Photo>
        ))}
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <div className="sticky-action">
        <button className="btn-primary w-full" disabled={pick == null || busy} onClick={() => pick != null && onGuess(pick)}>
          {busy ? 'Enviando…' : pick == null ? 'Elige una imagen' : 'Es esta'}
        </button>
      </div>
    </div>
  )
}

// ── Resultado ──────────────────────────────────────────────────────────────
type ResultProps = {
  round: RoundView
  chosen: DuoImage | null
  busy: boolean
  onNext: () => void
}

export function Result({ round, chosen, busy, onNext }: ResultProps) {
  const r = round.result!
  const t = r.target
  const nextRole = r.skipped ? round.role : round.role === 'describer' ? 'guesser' : 'describer'
  const iGuessedWrong = round.role === 'guesser' && r.success === false && chosen && chosen.id !== t.id
  return (
    <div className="space-y-4" data-result={r.skipped ? 'skip' : r.success ? 'win' : 'miss'}>
      {r.success && <Celebration />}
      <div className="text-center" aria-live="polite">
        <p className="result-title">{r.skipped ? 'Pasaron esta imagen' : r.success ? '¡Se entendieron!' : 'Esta vez no'}</p>
        <p className="text-muted">
          {r.skipped
            ? 'No cuenta como fallo.'
            : r.success
              ? 'Un nudo más en su khipu.'
              : 'Pasa hasta en la mejor pareja. La siguiente sale.'}
        </p>
      </div>

      <div className={iGuessedWrong ? 'grid grid-cols-[2fr_1fr] items-end gap-3' : ''}>
        <Photo img={t} alt={`${t.concept_lemma}: ${t.concept_es}`} className="photo-hero">
          <span className="photo-badge">
            <Qu className="font-semibold">{t.concept_lemma}</Qu> · {t.concept_es}
          </span>
        </Photo>
        {iGuessedWrong && (
          <div>
            <p className="eyebrow mb-1">Elegiste</p>
            <Photo img={chosen} alt="La imagen que elegiste" className="photo-dim" />
          </div>
        )}
      </div>

      {round.description && (
        <blockquote className="said">
          <Qu>{round.description}</Qu>
        </blockquote>
      )}

      <button className="btn-primary w-full" onClick={onNext} disabled={busy}>
        {busy ? 'Preparando…' : nextRole === 'describer' ? 'Siguiente · ahora describes tú' : 'Siguiente · ahora adivinas tú'}
        <Icon name="next" className="size-4" />
      </button>
    </div>
  )
}

function Celebration() {
  return (
    <div className="celebrate" aria-hidden>
      {Array.from({ length: 14 }, (_, i) => (
        <i key={i} style={{ '--k': i } as CSSProperties} />
      ))}
    </div>
  )
}

// ── Sala cerrada ───────────────────────────────────────────────────────────
export function Closed({ state, onNew }: { state: DuoState | null; onNew: () => void }) {
  const played = state?.room.rounds_played ?? 0
  return (
    <div className="phase-card text-center">
      <p className="font-qu text-3xl font-semibold">La sala se cerró</p>
      <p className="mt-2 text-muted">
        {played
          ? `Jugaron ${played} ${played === 1 ? 'ronda' : 'rondas'} y acertaron ${state!.room.score}. Lo que compartieron se conserva.`
          : 'Alguien salió o pasó mucho tiempo sin actividad.'}
      </p>
      <button className="btn-primary mt-5" onClick={onNew}>
        Crear otra sala
      </button>
    </div>
  )
}
