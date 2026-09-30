import type { CSSProperties } from 'react'
import { sameWord, splitStem } from '../lib/morph'
import { Icon, Qu } from '../ui/bits'
import { heat, radius, type Answer, type Guess, type GuessResult } from './model'

const pct = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 1 })

/** Forma escrita → raíz, resaltando lo que comparten: wasi|kunapi → wasi */
export function Reduction({ word, lemma }: { word: string; lemma: string }) {
  if (sameWord(word, lemma)) return <Qu className="font-semibold">{lemma}</Qu>
  const s = splitStem(word, lemma)
  return (
    <span className="inline-flex flex-wrap items-baseline gap-x-2">
      <Qu className="text-muted">
        {s ? (
          <>
            <span className="morph-stem">{s.stem}</span>
            {s.formRest}
          </>
        ) : (
          word
        )}
      </Qu>
      <span aria-label="se reduce a" className="text-muted">
        →
      </span>
      <Qu className="font-semibold">{lemma}</Qu>
    </span>
  )
}

/** Barra de cercanía con etiqueta textual: nunca solo color. */
export function Meter({ rank, vocab, compact = false }: { rank: number; vocab: number; compact?: boolean }) {
  const h = heat(rank)
  const fill = 1 - radius(rank, vocab)
  return (
    <span className="meter" data-heat={h.key} data-compact={compact || undefined}>
      <span className="meter-track" aria-hidden>
        <span className="meter-fill" style={{ '--fill': Math.max(0.03, fill) } as CSSProperties} />
      </span>
      <span className="meter-label">{h.label}</span>
    </span>
  )
}

export type Notice =
  | { kind: 'pending'; word: string }
  | { kind: 'result'; guess: GuessResult }
  | { kind: 'duplicate'; word: string; lemma: string }
  | { kind: 'error'; text: string }

type CardProps = {
  notice: Notice
  vocab: number
  onContribute: (g: GuessResult) => void
}

/** Tarjeta del último intento. */
export function LastGuess({ notice, vocab, onContribute }: CardProps) {
  if (notice.kind === 'pending') {
    return (
      <div className="guess-card" data-pending>
        <Qu className="text-2xl font-semibold">{notice.word}</Qu>
        <p className="mt-1 text-sm text-muted">Midiendo la distancia…</p>
      </div>
    )
  }
  if (notice.kind === 'error') {
    return (
      <div className="guess-card" role="alert">
        <p>{notice.text}</p>
      </div>
    )
  }
  if (notice.kind === 'duplicate') {
    return (
      <div className="guess-card">
        <p className="text-xl">
          <Reduction word={notice.word} lemma={notice.lemma} />
        </p>
        <p className="mt-1 text-sm text-muted">
          Ya probaste <Qu>{notice.lemma}</Qu>: las formas flexionadas cuentan como su raíz.
        </p>
      </div>
    )
  }

  const g = notice.guess
  if (!g.known || g.rank == null || !g.lemma) {
    return (
      <div className="guess-card" data-heat="unknown">
        <Qu className="text-2xl font-semibold">{g.word}</Qu>
        <p className="mt-1 text-muted">No está en el vocabulario del corpus. Puede estar mal escrita… o puede faltar.</p>
        {g.can_contribute && g.suggestion && (
          <button className="btn-soft mt-3" onClick={() => onContribute(g)}>
            <Icon name="pencil" className="size-4" /> Aportar esta palabra
          </button>
        )}
      </div>
    )
  }

  return (
    <div className="guess-card" data-heat={heat(g.rank).key} key={g.word}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <p className="text-2xl">
          <Reduction word={g.word} lemma={g.lemma} />
        </p>
        <p className="font-qu text-3xl font-semibold tabular-nums">
          <span className="sr-only">puesto </span>#{g.rank}
        </p>
      </div>
      {g.gloss && <p className="text-muted">«{g.gloss}»</p>}
      <div className="mt-3">
        <Meter rank={g.rank} vocab={vocab} />
      </div>
      {g.percentile != null && g.rank > 1 && (
        <p className="mt-1.5 text-sm text-muted">Más cerca que el {pct.format(g.percentile)} % del vocabulario</p>
      )}
    </div>
  )
}

type ListProps = {
  guesses: Guess[]
  vocab: number
  sort: 'near' | 'order'
  onSort: (s: 'near' | 'order') => void
  onFixGloss: (g: Guess) => void
  onContribute: (g: Guess) => void
}

export function GuessList({ guesses, vocab, sort, onSort, onFixGloss, onContribute }: ListProps) {
  const rows = [...guesses].sort((a, b) =>
    sort === 'order' ? b.n - a.n : (a.rank ?? Infinity) - (b.rank ?? Infinity) || b.n - a.n,
  )
  return (
    <section aria-labelledby="radar-history">
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 id="radar-history" className="eyebrow">
          Intentos · {guesses.length}
        </h2>
        <div className="segmented" role="group" aria-label="Ordenar intentos">
          <button aria-pressed={sort === 'near'} onClick={() => onSort('near')}>
            Cercanía
          </button>
          <button aria-pressed={sort === 'order'} onClick={() => onSort('order')}>
            Orden
          </button>
        </div>
      </div>
      <ol className="space-y-1.5">
        {rows.map((g) => (
          <li key={g.n} className="guess-row" data-heat={heat(g.rank).key}>
            <span className="w-7 shrink-0 text-right text-xs text-muted tabular-nums" aria-label={`intento ${g.n}`}>
              {g.n}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate">
                {g.lemma ? <Reduction word={g.word} lemma={g.lemma} /> : <Qu className="text-muted">{g.word}</Qu>}
              </span>
              <span className="block truncate text-sm text-muted">{g.gloss ?? (g.known ? '' : 'no está en el vocabulario')}</span>
            </span>
            {g.rank != null ? (
              <span className="flex shrink-0 flex-col items-end gap-1">
                <span className="text-sm font-bold tabular-nums">#{g.rank}</span>
                <Meter rank={g.rank} vocab={vocab} compact />
              </span>
            ) : null}
            {g.known && g.lexeme_id != null ? (
              <button className="btn-icon -mr-2 size-11" onClick={() => onFixGloss(g)} aria-label={`Corregir el significado de ${g.lemma}`}>
                <Icon name="pencil" className="size-4" />
              </button>
            ) : g.can_contribute && g.suggestion ? (
              <button className="btn-soft shrink-0" onClick={() => onContribute(g)}>
                Aportar
              </button>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  )
}

type RevealProps = {
  answer: Answer
  solved: boolean
  attempts: number
  onListen: () => void
  onFixGloss: () => void
  onShare: () => void
}

export function Reveal({ answer, solved, attempts, onListen, onFixGloss, onShare }: RevealProps) {
  return (
    <section className="reveal" data-solved={solved || undefined} aria-live="polite">
      <p className="eyebrow">{solved ? `¡La encontraste en ${attempts} ${attempts === 1 ? 'intento' : 'intentos'}!` : 'La palabra era'}</p>
      <div className="mt-1 flex items-center gap-3">
        <Qu className="reveal-word">{answer.lemma}</Qu>
        <button className="btn-icon" onClick={onListen} aria-label={`Oír «${answer.lemma}»`}>
          <Icon name="speaker" />
        </button>
      </div>
      <p className="text-xl">
        «{answer.gloss ?? 'sin glosa'}»
        <button className="btn-ghost ml-1 align-middle" onClick={onFixGloss}>
          <Icon name="pencil" className="size-4" /> ¿no es eso?
        </button>
      </p>

      <button className="btn-primary mt-4" onClick={onShare}>
        Compartir resultado
      </button>

      <h3 className="eyebrow mt-6 mb-2">Sus vecinas de significado</h3>
      <p className="mb-3 text-sm text-muted">
        Así las relaciona el modelo, entrenado con un corpus pequeño: algunas vecinas sorprenden.
      </p>
      <ol className="grid grid-cols-2 gap-x-4 gap-y-2">
        {answer.neighbors.map((n) => (
          <li key={n.lemma} className="flex items-baseline gap-2">
            <span className="w-6 shrink-0 text-right text-xs text-muted tabular-nums">{n.rank}</span>
            <span className="min-w-0">
              <Qu className="block font-semibold">{n.lemma}</Qu>
              <span className="block truncate text-sm text-muted">{n.gloss}</span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  )
}
