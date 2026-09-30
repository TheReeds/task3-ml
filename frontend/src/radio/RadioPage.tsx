import { useEffect, useMemo, useState } from 'react'
import { track } from '../lib/events'
import type { Entry, Station, Token } from '../lib/types'
import { Icon, Provenance } from '../ui/bits'
import { Sheet } from '../ui/Sheet'
import { createRadio, DEFAULT_STATION, type Phase } from './controller'
import { CorrectForm, type Correction } from '../contribute/CorrectForm'
import { Dial } from './Dial'
import { Phrase } from './Phrase'
import { familyOf, toDial } from './stations'
import { Visualizer } from './Visualizer'
import { WordPanel } from './WordPanel'

const ON_AIR: Phase[] = ['playing', 'between', 'tuning']

export function RadioPage() {
  const [audio] = useState(() => {
    const a = new Audio()
    a.preload = 'auto'
    return a
  })
  const [stations, setStations] = useState<Station[] | null>(null)
  const [stationId, setStationId] = useState(DEFAULT_STATION)
  const [current, setCurrent] = useState<Entry | null>(null)
  const [phase, setPhase] = useState<Phase>('boot')
  const [error, setError] = useState<string | null>(null)
  const [heard, setHeard] = useState(0)
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null)
  const [everOn, setEverOn] = useState(false)
  const [radio] = useState(() =>
    createRadio(audio, {
      setStations,
      setStationId,
      setCurrent,
      setPhase: (p) => {
        setPhase(p)
        if (p === 'playing') setEverOn(true)
      },
      setError,
      setHeard,
      setAnalyser,
    }),
  )

  const [slow, setSlow] = useState(false)
  const [repeat, setRepeat] = useState(false)
  const [hideTr, setHideTr] = useState(false)
  const [peekId, setPeekId] = useState<number | null>(null)
  const [word, setWord] = useState<Token | null>(null)
  const [correction, setCorrection] = useState<Correction | null>(null)

  useEffect(() => {
    void radio.boot()
    return () => radio.dispose()
  }, [radio])

  useEffect(() => {
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = phase === 'playing' ? 'playing' : 'paused'
  }, [phase])

  const dial = useMemo(() => {
    const list = stations ?? [{ id: stationId, name: 'Aleatoria', description: '', entries: 0 }]
    return toDial(list.some((s) => s.id === stationId) ? list : [...list, { id: stationId, name: stationId, description: '', entries: 0 }])
  }, [stations, stationId])
  const station = dial.find((s) => s.id === stationId)

  const onAir = ON_AIR.includes(phase)
  const gate = phase === 'gate' || (phase === 'boot' && !everOn)

  function openWord(t: Token) {
    radio.inspect()
    setWord(t)
    track('radio.word_open', 'radio', { lexeme: t.lexeme_id != null })
  }

  function closeSheets() {
    setWord(null)
    setCorrection(null)
    radio.endInspect()
  }

  function startCorrection(c: Correction) {
    radio.inspect()
    setWord(null)
    setCorrection(c)
  }

  const tr = current?.translation
  const peek = peekId != null && peekId === current?.id

  return (
    <section
      className="radio"
      data-family={familyOf(stationId)}
      data-power={everOn ? 'on' : 'off'}
      aria-label="Radio"
    >
      <div className="glow" aria-hidden />

      <header className="relative z-10 px-5 pt-4 text-center">
        <p className="onair" data-on={onAir || undefined}>
          <span className="onair-dot" aria-hidden />
          {phase === 'tuning' ? 'Sintonizando…' : onAir ? 'Al aire' : gate ? 'Lista para sonar' : 'En pausa'}
        </p>
        <h1 className="mt-1 font-qu text-[clamp(1.6rem,6vw,2.2rem)] font-semibold leading-tight">
          {station?.name ?? 'Radio'}
          <span className="ml-2 align-middle font-sans text-sm font-normal tabular-nums text-muted">
            {station?.freq} <abbr title="frecuencia de la emisora, solo decorativa">FM</abbr>
          </span>
        </h1>
        {station?.description && <p className="mx-auto mt-0.5 max-w-sm text-sm text-muted">{station.description}</p>}
      </header>

      <Dial stations={dial} current={stationId} tuning={phase === 'tuning'} onTune={(id) => void radio.tune(id)} />

      <div className="stage" aria-live="off">
        {phase === 'tuning' && <div className="static" aria-hidden />}
        {current ? (
          <div key={current.id} className="stage-in">
            <Phrase entry={current} audio={audio} onWord={openWord} />

            <div className="translation mt-5" data-hidden={(hideTr && !peek) || undefined}>
              {tr ? (
                <p lang="es" className="text-lg leading-relaxed">
                  {tr.text}
                </p>
              ) : (
                <p className="text-muted">Esta frase aún no tiene traducción.</p>
              )}
              {hideTr && !peek && tr && (
                <button className="translation-peek" onClick={() => setPeekId(current.id)}>
                  <Icon name="eye" className="size-4" /> Ver traducción
                </button>
              )}
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <Provenance origin={current.audio_origin} />
              <Provenance origin={tr?.origin} />
              {current.supersedes_id != null && <Provenance origin="community" />}
              {tr && (
                <button
                  className="btn-ghost ml-auto"
                  onClick={() => startCorrection({ kind: 'translation', entry: current })}
                >
                  <Icon name="pencil" className="size-4" /> Mejorar traducción
                </button>
              )}
            </div>
          </div>
        ) : phase === 'error' ? null : (
          <div className="space-y-3" aria-busy="true" aria-label="Cargando la primera frase">
            <div className="skeleton h-10 w-11/12" />
            <div className="skeleton h-10 w-8/12" />
            <div className="skeleton mt-6 h-5 w-10/12" />
          </div>
        )}

        {phase === 'error' && (
          <div role="alert" className="mt-4 rounded-2xl border border-line p-4 text-center">
            <p>{error ?? 'Se cortó la señal.'}</p>
            <button className="btn-soft mt-3" onClick={() => radio.retry()}>
              Volver a intentar
            </button>
          </div>
        )}
      </div>

      <div className="controls">
        <button className="btn-icon" aria-label="Escuchar otra vez" onClick={() => radio.replay()} disabled={!current}>
          <Icon name="replay" />
        </button>

        <div className="play-wrap">
          <Visualizer analyser={analyser} audio={audio} />
          {gate && <span className="gate-ring" aria-hidden />}
          <button
            className="play"
            data-state={gate ? 'gate' : onAir ? 'on' : 'off'}
            aria-label={gate ? 'Encender la radio' : onAir ? 'Pausar' : 'Escuchar'}
            aria-busy={phase === 'boot' || undefined}
            onClick={() => (gate ? radio.unlock() : radio.toggle())}
          >
            <Icon name={onAir && !gate ? 'pause' : 'play'} className="size-9" />
          </button>
        </div>

        <button className="btn-icon" aria-label="Siguiente frase" onClick={() => radio.skip()} disabled={!current}>
          <Icon name="next" />
        </button>
      </div>

      <p className="gate-hint" data-show={gate || undefined} aria-hidden={!gate}>
        {phase === 'boot' ? 'Preparando la primera frase…' : <>Toca para escuchar · <span lang="qu">Uyariy</span></>}
      </p>

      <div className="toolbar">
        <button
          className="chip-btn"
          aria-pressed={slow}
          onClick={() => {
            radio.setRate(slow ? 1 : 0.75)
            setSlow(!slow)
          }}
        >
          <span className="tabular-nums">{slow ? '0,75×' : '1×'}</span>
          <span className="sr-only">velocidad</span>
        </button>
        <button className="chip-btn" aria-pressed={!hideTr} onClick={() => setHideTr(!hideTr)}>
          <Icon name={hideTr ? 'eye-off' : 'eye'} className="size-4" />
          Traducción
        </button>
        <button
          className="chip-btn"
          aria-pressed={repeat}
          onClick={() => {
            radio.setRepeat(!repeat)
            setRepeat(!repeat)
          }}
        >
          <Icon name="repeat" className="size-4" /> Bucle
        </button>
        {heard > 0 && (
          <span className="basis-full text-center text-sm text-muted tabular-nums" aria-live="polite">
            {heard} {heard === 1 ? 'frase escuchada' : 'frases escuchadas'}
          </span>
        )}
      </div>

      <Sheet open={!!word && !!current} onClose={closeSheets} label="Significado de la palabra">
        {word && current && (
          <WordPanel
            entry={current}
            token={word}
            onSegment={() => radio.segment(word.start_ms, word.end_ms)}
            onCorrect={startCorrection}
            onPlayEntry={(id) => {
              setWord(null)
              void radio.playEntry(id)
            }}
          />
        )}
      </Sheet>

      <Sheet open={!!correction} onClose={closeSheets} label="Corregir">
        {correction && (
          <CorrectForm correction={correction} module="radio" onDone={closeSheets} onStale={() => void radio.refreshCurrent()} />
        )}
      </Sheet>
    </section>
  )
}
