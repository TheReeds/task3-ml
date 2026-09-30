import { api, ApiError, pickAudio } from '../lib/api'
import { track } from '../lib/events'
import type { Entry, Station } from '../lib/types'

export type Phase =
  | 'boot' // cargando la primera frase
  | 'gate' // lista, esperando el primer toque (autoplay bloqueado)
  | 'playing'
  | 'paused'
  | 'between' // respiro entre frases / cargando la siguiente
  | 'tuning' // cambiando de emisora
  | 'error'

type Loaded = { entry: Entry; url: string }

export type RadioUi = {
  setStations: (s: Station[]) => void
  setStationId: (id: string) => void
  setCurrent: (e: Entry) => void
  setPhase: (p: Phase) => void
  setError: (msg: string | null) => void
  setHeard: (n: number) => void
  setAnalyser: (a: AnalyserNode | null) => void
}

/** Pausa entre frases: da tiempo a la animación de salida y a respirar. */
const GAP_MS = 650
export const DEFAULT_STATION = 'aleatoria'

// En iOS, pasar el audio por Web Audio lo silencia con la pantalla bloqueada.
const IS_IOS =
  /iPad|iPhone|iPod/.test(navigator.userAgent) ||
  (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)

/** Descarga el audio completo a un blob: el encadenado es instantáneo y el analizador no depende de CORS. */
async function loadAudio(entry: Entry): Promise<Loaded> {
  const src = pickAudio(entry.audio_url, entry.audio_url_m4a)
  if (!src) throw new ApiError('Esta frase no tiene audio.', 404)
  try {
    const res = await fetch(src)
    if (!res.ok) throw new Error(String(res.status))
    return { entry, url: URL.createObjectURL(await res.blob()) }
  } catch {
    return { entry, url: src } // que el navegador lo transmita directamente
  }
}

async function fetchNext(station: string, after: number | null): Promise<Loaded> {
  const qs = after != null ? `?after=${after}` : ''
  const entry = await api<Entry>(`/radio/stations/${encodeURIComponent(station)}/next${qs}`)
  return loadAudio(entry)
}

function release(l: Loaded | null) {
  if (l?.url.startsWith('blob:')) URL.revokeObjectURL(l.url)
}

export function createRadio(audio: HTMLAudioElement, ui: RadioUi) {
  const s = {
    gen: 0, // cada cambio de rumbo (emisora, salto) invalida las cargas en vuelo
    station: DEFAULT_STATION,
    current: null as Loaded | null,
    next: null as null | { station: string; after: number; promise: Promise<Loaded> },
    gap: 0,
    pausedInGap: false,
    loading: false,
    unlocked: false,
    gestureAt: null as number | null,
    rate: 1,
    repeat: false,
    heard: 0,
    segmentEnd: null as number | null,
    inspect: null as null | { resume: 'play' | 'advance' | null; t: number },
    ctx: null as AudioContext | null,
    noise: null as AudioBufferSourceNode | null,
    raf: 0,
    firstPlaySent: sessionStorageFlag(),
  }

  function sessionStorageFlag() {
    try {
      return sessionStorage.getItem('cv.first_play') === '1'
    } catch {
      return false
    }
  }

  // ── Carga y encadenado ──────────────────────────────────────────────────
  function prefetch(station: string, after: number) {
    const promise = fetchNext(station, after)
    promise.catch(() => {
      if (s.next?.promise === promise) s.next = null
    })
    s.next = { station, after, promise }
  }

  function take(station: string, after: number | null): Promise<Loaded> {
    const n = s.next
    if (n && n.station === station && n.after === after) {
      s.next = null
      return n.promise
    }
    return fetchNext(station, after)
  }

  async function start(l: Loaded, gen: number) {
    if (gen !== s.gen) return release(l)
    const old = s.current
    s.current = l
    s.loading = true
    ui.setError(null)
    ui.setCurrent(l.entry)
    audio.src = l.url
    audio.defaultPlaybackRate = s.rate
    audio.playbackRate = s.rate
    if (old && old.url !== l.url) release(old)
    setMetadata(l.entry)
    prefetch(s.station, l.entry.id)
    try {
      await audio.play()
    } catch {
      s.loading = false
      if (gen === s.gen) ui.setPhase(s.unlocked ? 'paused' : 'gate')
    }
  }

  function fail(err: unknown) {
    s.loading = false
    ui.setError(err instanceof ApiError ? err.message : 'No se pudo cargar la siguiente frase.')
    ui.setPhase('error')
  }

  function clearGap() {
    window.clearTimeout(s.gap)
    s.gap = 0
  }

  async function advance() {
    const gen = ++s.gen
    clearGap()
    s.pausedInGap = false
    ui.setPhase('between')
    try {
      await start(await take(s.station, s.current?.entry.id ?? null), gen)
    } catch (err) {
      if (gen === s.gen) fail(err)
    }
  }

  // ── Eventos del elemento de audio ────────────────────────────────────────
  const on: Record<string, () => void> = {
    playing() {
      s.loading = false
      s.unlocked = true
      ui.setPhase('playing')
      if (!s.firstPlaySent) {
        s.firstPlaySent = true
        try {
          sessionStorage.setItem('cv.first_play', '1')
        } catch {
          /* sin almacenamiento */
        }
        track('radio.first_play', 'radio', {
          ms: Math.round(performance.now()),
          gesture_ms: s.gestureAt != null ? Math.round(s.gestureAt) : null,
          station: s.station,
        })
      }
    },
    pause() {
      if (audio.ended || s.loading) return
      ui.setPhase('paused')
    },
    ended() {
      if (s.segmentEnd != null) {
        s.segmentEnd = null
        ui.setPhase('paused')
        return
      }
      s.heard += 1
      ui.setHeard(s.heard)
      ui.setPhase('between')
      s.gap = window.setTimeout(() => {
        s.gap = 0
        if (s.repeat) {
          audio.currentTime = 0
          void audio.play()
        } else void advance()
      }, GAP_MS)
    },
    error() {
      if (!audio.src) return
      fail(new ApiError('El audio de esta frase no se pudo reproducir.', 0))
    },
  }

  // Corta la reproducción al final del segmento de una palabra.
  function tick() {
    if (s.segmentEnd != null && !audio.paused && audio.currentTime * 1000 >= s.segmentEnd) {
      s.segmentEnd = null
      audio.pause()
    }
    s.raf = requestAnimationFrame(tick)
  }

  // ── Web Audio: analizador para la visualización y estática al sintonizar ──
  function ensureGraph() {
    if (s.ctx) {
      if (s.ctx.state === 'suspended') void s.ctx.resume()
      return
    }
    if (IS_IOS) return
    try {
      const ctx = new AudioContext()
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 128
      analyser.smoothingTimeConstant = 0.78
      ctx.createMediaElementSource(audio).connect(analyser)
      analyser.connect(ctx.destination)
      s.ctx = ctx
      ui.setAnalyser(analyser)
    } catch {
      /* sin visualización real: se simula con los tiempos de las palabras */
    }
  }

  function staticOn() {
    const ctx = s.ctx
    if (!ctx || s.noise || matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const buf = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate)
    const data = buf.getChannelData(0)
    for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1
    const src = ctx.createBufferSource()
    src.buffer = buf
    src.loop = true
    const band = ctx.createBiquadFilter()
    band.type = 'bandpass'
    band.frequency.value = 2200
    band.Q.value = 0.7
    const gain = ctx.createGain()
    gain.gain.setValueAtTime(0, ctx.currentTime)
    gain.gain.linearRampToValueAtTime(0.05, ctx.currentTime + 0.08)
    src.connect(band).connect(gain).connect(ctx.destination)
    src.start()
    s.noise = src
  }

  function staticOff() {
    try {
      s.noise?.stop()
    } catch {
      /* ya detenido */
    }
    s.noise = null
  }

  // ── Media Session: controles en pantalla bloqueada / auriculares ──────────
  function setMetadata(entry: Entry) {
    if (!('mediaSession' in navigator)) return
    navigator.mediaSession.metadata = new MediaMetadata({
      title: entry.text,
      artist: entry.translation?.text ?? 'Runasimi',
      album: 'Corpus Vivo · Radio',
      artwork: [{ src: '/favicon.svg', sizes: 'any', type: 'image/svg+xml' }],
    })
  }

  function bindMediaSession() {
    if (!('mediaSession' in navigator)) return
    const ms = navigator.mediaSession
    ms.setActionHandler('play', () => api_.toggle())
    ms.setActionHandler('pause', () => api_.toggle())
    ms.setActionHandler('nexttrack', () => void advance())
    ms.setActionHandler('previoustrack', () => api_.replay())
  }

  // ── API pública ──────────────────────────────────────────────────────────
  const api_ = {
    async boot() {
      Object.entries(on).forEach(([ev, fn]) => audio.addEventListener(ev, fn))
      s.raf = requestAnimationFrame(tick)
      bindMediaSession()
      const gen = ++s.gen
      ui.setPhase('boot')
      api<Station[]>('/radio/stations').then(ui.setStations, () => {
        /* el dial muestra solo la emisora actual */
      })
      try {
        // Se intenta sonar sin gesto; si el navegador lo bloquea, queda en 'gate'.
        await start(await fetchNext(s.station, null), gen)
      } catch (err) {
        if (gen === s.gen) fail(err)
      }
    },

    dispose() {
      s.gen++
      clearGap()
      cancelAnimationFrame(s.raf)
      Object.entries(on).forEach(([ev, fn]) => audio.removeEventListener(ev, fn))
      audio.pause()
    },

    /** Primer toque: desbloquea el audio y enciende la radio. */
    unlock() {
      s.gestureAt ??= performance.now()
      ensureGraph()
      if (s.current) void audio.play().catch(() => ui.setPhase('paused'))
    },

    toggle() {
      s.gestureAt ??= performance.now()
      ensureGraph()
      if (!audio.paused) return audio.pause()
      if (s.gap) {
        clearGap()
        s.pausedInGap = true
        return ui.setPhase('paused')
      }
      if (s.pausedInGap || audio.ended) return void advance()
      if (s.current) void audio.play().catch(() => ui.setPhase('paused'))
    },

    skip() {
      ensureGraph()
      void advance()
    },

    replay() {
      ensureGraph()
      clearGap()
      s.pausedInGap = false
      audio.currentTime = 0
      void audio.play()
    },

    async tune(id: string) {
      if (id === s.station && s.current) return
      ensureGraph()
      const gen = ++s.gen
      clearGap()
      s.loading = true
      audio.pause()
      s.station = id
      s.next = null
      ui.setStationId(id)
      ui.setPhase('tuning')
      staticOn()
      track('radio.station_change', 'radio', { station: id })
      try {
        const l = await fetchNext(id, null)
        if (gen === s.gen) staticOff()
        await start(l, gen)
      } catch (err) {
        if (gen === s.gen) {
          staticOff()
          fail(err)
        }
      }
    },

    /** Reproduce una frase concreta (p. ej. un ejemplo del panel) y sigue con la emisora. */
    async playEntry(id: number) {
      ensureGraph()
      const gen = ++s.gen
      clearGap()
      s.inspect = null
      ui.setPhase('between')
      try {
        const l = await loadAudio(await api<Entry>(`/entries/${id}`))
        await start(l, gen)
      } catch (err) {
        if (gen === s.gen) fail(err)
      }
    },

    /** Suena solo el tramo de una palabra. */
    segment(startMs: number, endMs: number) {
      ensureGraph()
      clearGap()
      s.segmentEnd = endMs + 40
      audio.currentTime = Math.max(0, startMs - 60) / 1000
      void audio.play()
    },

    /** Al abrir el panel de palabra: pausa y recuerda cómo seguir. */
    inspect() {
      if (s.inspect) return
      const resume = !audio.paused ? 'play' : s.gap ? 'advance' : null
      clearGap()
      s.inspect = { resume, t: audio.currentTime }
      audio.pause()
    },

    endInspect() {
      const i = s.inspect
      s.inspect = null
      s.segmentEnd = null
      if (!i) return
      if (i.resume === 'advance') return void advance()
      audio.currentTime = i.t
      if (i.resume === 'play') void audio.play()
      else if (!audio.paused) audio.pause()
    },

    /** Tras un 404 al corregir: la frase fue sustituida; trae la versión vigente sin cortar el audio. */
    async refreshCurrent() {
      const cur = s.current
      if (!cur) return
      const entry = await api<Entry>(`/entries/${cur.entry.id}`)
      if (s.current === cur) {
        s.current = { ...cur, entry }
        ui.setCurrent(entry)
      }
    },

    retry() {
      if (s.current) void advance()
      else void api_.tune(s.station)
    },

    setRate(r: number) {
      s.rate = r
      audio.defaultPlaybackRate = r
      audio.playbackRate = r
    },

    setRepeat(on: boolean) {
      s.repeat = on
    },
  }
  return api_
}

export type Radio = ReturnType<typeof createRadio>
