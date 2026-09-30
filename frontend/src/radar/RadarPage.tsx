import { useEffect, useRef, useState, type FormEvent } from 'react'
import { CorrectForm, type Correction } from '../contribute/CorrectForm'
import { api, ApiError, pickAudio } from '../lib/api'
import { track } from '../lib/events'
import type { Lexeme } from '../lib/types'
import { Sheet } from '../ui/Sheet'
import { toast } from '../ui/toast'
import {
  dayLabel,
  loadGame,
  markSolved,
  peekStatus,
  saveGame,
  shareText,
  streak,
  type Answer,
  type Game,
  type GuessResult,
  type PuzzleItem,
  type Today,
} from './model'
import { GuessList, LastGuess, Reveal, type Notice } from './parts'
import { Scope } from './Scope'

const STATUS_MARK = { new: '', playing: '·', solved: '✓', gave_up: '⚑' } as const

export default function RadarPage() {
  const [today, setToday] = useState<Today | null>(null)
  const [puzzles, setPuzzles] = useState<PuzzleItem[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [game, setGame] = useState<Game | null>(null)
  const [isToday, setIsToday] = useState(true)

  const [input, setInput] = useState('')
  const [inputError, setInputError] = useState<string | null>(null)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [flash, setFlash] = useState<string | null>(null)
  const [sort, setSort] = useState<'near' | 'order'>('near')
  const [confirmGiveUp, setConfirmGiveUp] = useState(false)
  const [revealing, setRevealing] = useState(false)
  const [correction, setCorrection] = useState<Correction | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const vocab = today?.vocabulary_size ?? 800
  const pending = notice?.kind === 'pending'

  useEffect(() => {
    let alive = true
    Promise.all([api<Today>('/radar/today'), api<PuzzleItem[]>('/radar/puzzles?days=7').catch(() => [])]).then(
      ([t, list]) => {
        if (!alive) return
        setToday(t)
        setPuzzles(list.length ? list : [{ puzzle_id: t.puzzle_id, day: t.day, letters: t.letters, is_today: true }])
        setGame(loadGame(t))
      },
      (e: unknown) => {
        if (!alive) return
        setLoadError(
          e instanceof ApiError && e.status === 503
            ? 'Todavía no hay vocabulario para jugar en esta lengua.'
            : e instanceof ApiError
              ? e.message
              : 'No se pudo cargar el juego de hoy.',
        )
      },
    )
    return () => {
      alive = false
    }
  }, [])

  function update(g: Game) {
    saveGame(g)
    setGame(g)
  }

  function choose(p: PuzzleItem) {
    setGame(loadGame(p))
    setIsToday(p.is_today)
    setNotice(null)
    setConfirmGiveUp(false)
    track('radar.open_puzzle', 'radar', { day: p.day, today: p.is_today })
  }

  async function fetchAnswer(g: Game, giveUp: boolean): Promise<Answer> {
    return api<Answer>(`/radar/puzzles/${g.puzzleId}/answer${giveUp ? '?give_up=true' : ''}`)
  }

  function doFlash(lemma: string) {
    setFlash(lemma)
    window.setTimeout(() => setFlash((f) => (f === lemma ? null : f)), 1400)
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (!game || game.status !== 'playing' || pending) return
    const word = input.trim()
    if (!word) return
    if (/\s/.test(word)) return setInputError('Propón una sola palabra.')
    const dup = game.guesses.find((g) => g.word.toLocaleLowerCase('es') === word.toLocaleLowerCase('es'))
    if (dup) {
      setInputError(null)
      setInput('')
      setNotice(dup.lemma ? { kind: 'duplicate', word, lemma: dup.lemma } : { kind: 'result', guess: dup })
      if (dup.lemma) doFlash(dup.lemma)
      return
    }

    // Optimista: el intento se ve al instante y el radar pulsa mientras llega la respuesta.
    setInputError(null)
    setInput('')
    setNotice({ kind: 'pending', word })
    try {
      const r = await api<GuessResult>('/radar/guess', {
        method: 'POST',
        body: { word, puzzle_id: game.puzzleId },
        module: 'radar',
      })
      const same = r.known && game.guesses.find((g) => g.lemma === r.lemma)
      if (same) {
        setNotice({ kind: 'duplicate', word, lemma: r.lemma! })
        doFlash(r.lemma!)
        return
      }
      const next: Game = {
        ...game,
        guesses: [...game.guesses, { ...r, n: game.guesses.length + 1 }],
        status: r.solved ? 'solved' : 'playing',
      }
      update(next)
      setNotice({ kind: 'result', guess: r })
      if (r.lemma) doFlash(r.lemma)
      if (r.solved) {
        if (isToday) markSolved(game.day)
        track('radar.solved', 'radar', { attempts: next.guesses.length, today: isToday })
        // Tras acertar, give_up solo sirve para leer los vecinos (el servidor no lo registra).
        fetchAnswer(next, isToday).then((answer) => update({ ...next, answer }), () => {})
      }
    } catch (err) {
      setInput(word)
      setNotice({ kind: 'error', text: err instanceof ApiError ? err.message : 'No se pudo medir la palabra. Inténtalo otra vez.' })
    } finally {
      inputRef.current?.focus()
    }
  }

  async function giveUp() {
    if (!game) return
    if (!confirmGiveUp && isToday) {
      setConfirmGiveUp(true)
      window.setTimeout(() => setConfirmGiveUp(false), 5000)
      return
    }
    setRevealing(true)
    try {
      const answer = await fetchAnswer(game, isToday)
      update({ ...game, status: game.status === 'solved' ? 'solved' : 'gave_up', answer })
      setNotice(null)
      track('radar.gave_up', 'radar', { attempts: game.guesses.length, today: isToday })
    } catch (err) {
      toast(err instanceof ApiError ? err.message : 'No se pudo revelar la palabra.', 'error')
    } finally {
      setRevealing(false)
      setConfirmGiveUp(false)
    }
  }

  async function listen(lexemeId: number) {
    try {
      const lx = await api<Lexeme>(`/lexemes/${lexemeId}`)
      const src = pickAudio(lx.audio_url, lx.audio_url_m4a)
      if (src) await new Audio(src).play()
    } catch {
      toast('No se pudo reproducir la pronunciación.', 'error')
    }
  }

  async function share() {
    if (!game) return
    const text = shareText(game)
    try {
      if (navigator.share) await navigator.share({ text })
      else {
        await navigator.clipboard.writeText(text)
        toast('Resultado copiado. ¡Pégalo donde quieras!')
      }
      track('radar.share', 'radar')
    } catch {
      /* compartir cancelado */
    }
  }

  const contribute = (g: GuessResult) => g.suggestion && setCorrection({ kind: 'new_lemma', suggestion: g.suggestion })

  if (loadError) {
    return (
      <div className="mx-auto max-w-md px-6 py-24 text-center" role="alert">
        <p className="font-qu text-2xl">Radar</p>
        <p className="mt-2 text-muted">{loadError}</p>
        <button className="btn-soft mt-4" onClick={() => location.reload()}>
          Volver a intentar
        </button>
      </div>
    )
  }

  if (!today || !game) {
    return (
      <div className="radar px-5 pt-6" aria-busy="true" aria-label="Cargando el juego de hoy">
        <div className="skeleton mx-auto h-8 w-40" />
        <div className="skeleton mx-auto mt-6 aspect-square w-full max-w-sm rounded-full" />
      </div>
    )
  }

  const finished = game.status !== 'playing'
  const days = streak(today.day)

  return (
    <section className="radar" aria-label="Radar">
      <div className="glow" aria-hidden />
      <header className="relative z-10 px-5 pt-4 text-center">
        <p className="eyebrow">
          {isToday ? 'Palabra de hoy' : 'Archivo'} · {dayLabel(game.day)}
        </p>
        <h1 className="mt-1 font-qu text-[clamp(1.6rem,6vw,2.2rem)] font-semibold leading-tight">Radar</h1>
        <p className="mt-0.5 text-sm text-muted">
          Una palabra secreta de {game.letters} letras. Acércate por el <em>significado</em>.
          {days > 0 && (
            <span className="ml-1 whitespace-nowrap font-bold text-ink">
              · racha {days} {days === 1 ? 'día' : 'días'}
            </span>
          )}
        </p>
      </header>

      {puzzles.length > 1 && (
        <nav className="days" aria-label="Días">
          {puzzles.map((p) => {
            const st = peekStatus(p.puzzle_id)
            return (
              <button key={p.puzzle_id} aria-pressed={p.puzzle_id === game.puzzleId} onClick={() => choose(p)} className="chip-btn shrink-0">
                {p.is_today ? 'Hoy' : dayLabel(p.day)}
                {st !== 'new' && (
                  <span aria-label={st === 'solved' ? 'resuelto' : st === 'gave_up' ? 'rendido' : 'en curso'} className="text-tint">
                    {STATUS_MARK[st]}
                  </span>
                )}
              </button>
            )
          })}
        </nav>
      )}

      <div className="relative z-10 mx-auto mt-4 w-full max-w-sm px-5">
        <Scope
          guesses={game.guesses}
          vocab={vocab}
          letters={game.letters}
          answer={game.answer}
          solved={game.status === 'solved'}
          scanning={pending}
          flash={flash}
        />
      </div>

      <div className="relative z-10 mx-auto mt-5 w-full max-w-md space-y-5 px-5">
        {!finished && (
          <form onSubmit={submit} className="guess-form">
            <label htmlFor="radar-input" className="sr-only">
              Una palabra en quechua
            </label>
            <input
              id="radar-input"
              ref={inputRef}
              className="field"
              lang="qu"
              placeholder="Escribe una palabra…"
              autoComplete="off"
              autoCapitalize="off"
              autoCorrect="off"
              spellCheck={false}
              enterKeyHint="go"
              maxLength={40}
              value={input}
              aria-invalid={!!inputError}
              aria-describedby={inputError ? 'radar-input-error' : undefined}
              onChange={(e) => {
                setInput(e.target.value)
                setInputError(null)
              }}
            />
            <button className="btn-primary shrink-0" disabled={pending || !input.trim()}>
              Probar
            </button>
          </form>
        )}
        {inputError && (
          <p id="radar-input-error" role="alert" className="-mt-3 text-sm text-danger">
            {inputError}
          </p>
        )}

        <div aria-live="polite">
          {notice && !game.answer && <LastGuess notice={notice} vocab={vocab} onContribute={contribute} />}
        </div>

        {game.answer ? (
          <Reveal
            answer={game.answer}
            solved={game.status === 'solved'}
            attempts={game.guesses.length}
            onListen={() => void listen(game.answer!.lexeme_id)}
            onFixGloss={() => setCorrection({ kind: 'gloss', lexeme: { id: game.answer!.lexeme_id, lemma: game.answer!.lemma, gloss: game.answer!.gloss } })}
            onShare={() => void share()}
          />
        ) : finished ? (
          <p className="text-center text-muted">Cargando sus vecinas…</p>
        ) : null}

        {game.guesses.length > 0 && (
          <GuessList
            guesses={game.guesses}
            vocab={vocab}
            sort={sort}
            onSort={setSort}
            onFixGloss={(g) => setCorrection({ kind: 'gloss', lexeme: { id: g.lexeme_id!, lemma: g.lemma!, gloss: g.gloss } })}
            onContribute={contribute}
          />
        )}

        {!finished && (
          <div className="flex flex-wrap items-center justify-center gap-2 pt-2 pb-4">
            <button className="btn-ghost" onClick={() => void giveUp()} disabled={revealing}>
              {revealing ? 'Revelando…' : confirmGiveUp ? '¿Seguro? Toca otra vez para ver la palabra' : isToday ? 'Rendirme' : 'Ver la respuesta'}
            </button>
            {game.guesses.length > 0 && (
              <button className="btn-ghost" onClick={() => void share()}>
                Compartir progreso
              </button>
            )}
          </div>
        )}
      </div>

      <Sheet open={!!correction} onClose={() => setCorrection(null)} label="Aportar">
        {correction && <CorrectForm correction={correction} module="radar" onDone={() => setCorrection(null)} />}
      </Sheet>
    </section>
  )
}
