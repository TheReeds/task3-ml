import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { api, ApiError, storage } from '../lib/api'
import { track } from '../lib/events'
import { Sheet } from '../ui/Sheet'
import { toast } from '../ui/toast'
import { Cord, Khipu } from './parts'
import { Closed, Describe, Guess, Invite, Ready, Result, WaitDescription, WaitGuess } from './phases'
import { normalizeCode, useDuoRoom, type DuoState } from './useDuoRoom'

const LAST_ROOM = 'cv.duo.last'
const go = (code?: string) => {
  location.hash = code ? `#/duo/${code}` : '#/duo'
}

export default function DuoPage({ code }: { code: string | null }) {
  const clean = code ? normalizeCode(code) : null
  return (
    <section className="duo" aria-label="Dúo">
      <div className="glow" aria-hidden />
      {clean ? <Room key={clean} code={clean} /> : <Lobby />}
    </section>
  )
}

// ── Vestíbulo: crear o entrar ──────────────────────────────────────────────
function Lobby() {
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const last = storage.get(LAST_ROOM)
  const typed = normalizeCode(input)

  async function create() {
    setBusy(true)
    setError(null)
    try {
      const r = await api<{ code: string }>('/duo/rooms', { method: 'POST', auth: true, module: 'duo' })
      track('duo.room_created', 'duo')
      go(r.code)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'No se pudo crear la sala.')
    } finally {
      setBusy(false)
    }
  }

  function join(e: FormEvent) {
    e.preventDefault()
    if (typed.length === 6) go(typed)
    else setError('El código tiene 6 letras o números.')
  }

  return (
    <div className="relative z-10 mx-auto w-full max-w-md px-5 pt-6">
      <header className="text-center">
        <p className="eyebrow">Para jugar de a dos</p>
        <h1 className="mt-1 font-qu text-[clamp(1.8rem,7vw,2.4rem)] font-semibold leading-tight">Dúo</h1>
        <p className="mt-1 text-muted">
          Una persona describe una imagen <em>en quechua</em>; la otra la encuentra entre cuatro. Ganan o pierden juntas, y
          se turnan.
        </p>
      </header>

      <div className="lobby-steps" aria-hidden>
        <span>
          <b>1</b>crea una sala
        </span>
        <span>
          <b>2</b>invita con el código
        </span>
        <span>
          <b>3</b>describan y adivinen
        </span>
      </div>

      <div className="mt-6 space-y-3">
        <button className="btn-primary w-full" onClick={() => void create()} disabled={busy}>
          {busy ? 'Creando…' : 'Crear una sala'}
        </button>

        <form onSubmit={join} className="phase-card space-y-3">
          <label htmlFor="duo-code" className="eyebrow block">
            ¿Te pasaron un código?
          </label>
          <div className="flex gap-2">
            <input
              id="duo-code"
              className="field code-field"
              inputMode="text"
              autoCapitalize="characters"
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              maxLength={9}
              placeholder="XV4 FWR"
              value={input}
              onChange={(e) => {
                setInput(e.target.value.toUpperCase())
                setError(null)
              }}
            />
            <button className="btn-soft shrink-0" disabled={typed.length !== 6}>
              Entrar
            </button>
          </div>
        </form>

        {error && (
          <p role="alert" className="text-center text-sm text-danger">
            {error}
          </p>
        )}
        {last && (
          <button className="btn-ghost mx-auto flex" onClick={() => go(last)}>
            Volver a la sala {last}
          </button>
        )}
      </div>
    </div>
  )
}

// ── Sala ───────────────────────────────────────────────────────────────────
const ROLE = { describer: 'describe', guesser: 'adivina' } as const

function Room({ code }: { code: string }) {
  const room = useDuoRoom(code)
  const { state, conn, fatal, pending, error, send } = room
  const [consentOpen, setConsentOpen] = useState(false)
  const [confirmLeave, setConfirmLeave] = useState(false)
  const askedKey = `cv.duo.asked.${code}`

  useEffect(() => storage.set(LAST_ROOM, code), [code])

  // Consentimiento: se pregunta al entrar a la sala (una vez por sala), antes de jugar.
  const [asked, setAsked] = useState(() => storage.get(askedKey) === '1')
  const showConsent = consentOpen || (!!state && state.room.status !== 'closed' && !asked)

  function answerConsent(value: boolean) {
    storage.set(askedKey, '1')
    setAsked(true)
    setConsentOpen(false)
    void room.setConsent(value).then(
      () => {
        if (state && value !== state.you.consent) track('duo.consent', 'duo', { value })
        if (!value && state?.you.consent) toast('Listo: retiramos y borramos tus frases de esta sala.')
      },
      () => toast('No se pudo guardar tu elección. Inténtalo otra vez.', 'error'),
    )
  }

  async function leave() {
    if (!confirmLeave) {
      setConfirmLeave(true)
      window.setTimeout(() => setConfirmLeave(false), 5000)
      return
    }
    try {
      await room.leave()
    } catch {
      /* si ya estaba cerrada, da igual */
    }
    storage.remove(LAST_ROOM)
    go()
  }

  const results = useMemo(() => khipuResults(state, room.history), [state, room.history])

  if (fatal) {
    return (
      <div className="relative z-10 mx-auto w-full max-w-md px-5 pt-10">
        <div className="phase-card text-center" role="alert">
          <p className="font-qu text-2xl font-semibold">No se pudo entrar</p>
          <p className="mt-2 text-muted">{fatal}</p>
          <button
            className="btn-primary mt-5"
            onClick={() => {
              storage.remove(LAST_ROOM)
              go()
            }}
          >
            Volver al inicio de Dúo
          </button>
        </div>
      </div>
    )
  }

  const round = state?.round ?? null
  const me = state?.players.find((p) => p.seat === state.you.seat)
  const partner = state?.players.find((p) => p.seat !== state.you.seat) ?? null
  const closed = state?.room.status === 'closed'
  const roleOf = (mine: boolean) => {
    if (!round || round.phase === 'done') return null
    const iDescribe = round.role === 'describer'
    return ROLE[iDescribe === mine ? 'describer' : 'guesser']
  }
  const chosen =
    round?.result?.chosen_image_id != null && room.options?.round === round.number
      ? (room.options.list.find((o) => o.id === round.result!.chosen_image_id) ?? null)
      : null

  return (
    <div className="relative z-10 mx-auto w-full max-w-md px-5 pt-3">
      <div className="room-bar">
        <span className="conn" data-conn={conn}>
          {conn === 'open' ? `Sala ${code}` : conn === 'connecting' ? 'Conectando…' : 'Reconectando…'}
        </span>
        {!closed && (
          <button className="btn-ghost -mr-3" onClick={() => void leave()}>
            {confirmLeave ? '¿Cerrar para ambos?' : 'Salir'}
          </button>
        )}
      </div>

      {state && (
        <>
          <Cord
            you={{ label: 'Tú', connected: conn === 'open', role: roleOf(true) }}
            partner={partner ? { label: 'Tu pareja', connected: partner.connected, role: roleOf(false) } : null}
            pulse={!!pending}
          />
          <div className="score">
            {results.length > 0 ? (
              <>
                <Khipu results={results} />
                <p className="text-sm">
                  <b className="font-qu text-xl">{state.room.score}</b>
                  <span className="text-muted"> {state.room.score === 1 ? 'acierto' : 'aciertos'} juntas</span>
                </p>
              </>
            ) : (
              <p className="text-sm text-muted">Cada acierto ata un nudo en su khipu.</p>
            )}
          </div>
          {!closed && (
            <div className="mt-2 flex justify-center">
              <button className="chip-btn" aria-pressed={state.you.consent} onClick={() => setConsentOpen(true)}>
                {state.you.consent ? '✓ Compartes tus frases' : 'No compartes tus frases · cambiar'}
              </button>
            </div>
          )}
        </>
      )}

      {partner && !partner.connected && !closed && state?.room.status === 'ready' && (
        <p className="banner" role="status">
          Tu pareja perdió la conexión. Esperamos a que vuelva…
        </p>
      )}

      <div className="mt-4 pb-6">
        {!state ? (
          <div className="space-y-3" aria-busy="true" aria-label="Entrando a la sala">
            <div className="skeleton mx-auto h-16 w-3/4" />
            <div className="skeleton h-48 w-full" />
          </div>
        ) : closed ? (
          <Closed state={state} onNew={() => go()} />
        ) : state.room.status === 'waiting' ? (
          <Invite code={code} />
        ) : !round ? (
          <Ready youDescribe={state.you.seat === 0} busy={pending === 'start_round'} onStart={() => send({ action: 'start_round' })} />
        ) : round.phase === 'describing' && round.role === 'describer' ? (
          <Describe
            key={round.number}
            round={round}
            consent={!!me?.consent}
            busy={pending === 'describe' || pending === 'skip' ? pending : null}
            error={error}
            onDescribe={(text) => send({ action: 'describe', text })}
            onSkip={() => send({ action: 'skip' })}
            onConsent={() => setConsentOpen(true)}
          />
        ) : round.phase === 'describing' ? (
          <WaitDescription />
        ) : round.phase === 'guessing' && round.role === 'guesser' ? (
          <Guess key={round.number} round={round} busy={pending === 'guess'} error={error} onGuess={(id) => send({ action: 'guess', image_id: id })} />
        ) : round.phase === 'guessing' ? (
          <WaitGuess round={round} />
        ) : (
          <Result key={round.number} round={round} chosen={chosen} busy={pending === 'start_round'} onNext={() => send({ action: 'start_round' })} />
        )}
        {error && round?.phase === 'done' && (
          <p role="alert" className="mt-2 text-center text-sm text-danger">
            {error}
          </p>
        )}
      </div>

      <Sheet open={showConsent} onClose={() => (asked ? setConsentOpen(false) : answerConsent(false))} label="Permiso para guardar tus frases">
        <ConsentBody current={state?.you.consent ?? false} firstTime={!asked} onAnswer={answerConsent} />
      </Sheet>
    </div>
  )
}

/** Orden de aciertos/fallos: el registrado en este dispositivo, completado con los totales del servidor. */
function khipuResults(state: DuoState | null, history: Record<number, boolean>): boolean[] {
  const seen = Object.keys(history)
    .map(Number)
    .sort((a, b) => a - b)
    .map((n) => history[n])
  if (!state) return seen
  const { rounds_played: total, score } = state.room
  const wins = seen.filter(Boolean).length
  const missingWins = Math.max(0, score - wins)
  const missingMiss = Math.max(0, total - seen.length - missingWins)
  return [...Array<boolean>(missingWins).fill(true), ...Array<boolean>(missingMiss).fill(false), ...seen]
}

function ConsentBody({ current, firstTime, onAnswer }: { current: boolean; firstTime: boolean; onAnswer: (v: boolean) => void }) {
  return (
    <div className="space-y-4">
      <h2 className="font-qu text-2xl font-semibold">¿Compartes tus descripciones con el corpus?</h2>
      <ul className="consent-list">
        <li>
          <b>Qué se guarda:</b> solo las frases que tú escribes al describir, junto con la imagen. Nada de lo que elige tu
          pareja, ni datos personales.
        </li>
        <li>
          <b>Para qué:</b> la comunidad las revisa y se publican de forma abierta con un seudónimo. Frases reales como estas
          son lo que más le falta al quechua en internet.
        </li>
        <li>
          <b>Puedes cambiar de opinión:</b> si retiras el permiso, se borran las frases que ya diste en esta sala.
        </li>
        <li>Sin permiso juegas exactamente igual.</li>
      </ul>
      <div className="grid gap-2">
        <button className="btn-primary" onClick={() => onAnswer(true)} aria-pressed={!firstTime && current}>
          Sí, compartir mis frases
        </button>
        <button className="btn-soft justify-center" onClick={() => onAnswer(false)} aria-pressed={!firstTime && !current}>
          {current && !firstTime ? 'Retirar permiso y borrar mis frases' : 'Jugar sin compartir'}
        </button>
      </div>
    </div>
  )
}
