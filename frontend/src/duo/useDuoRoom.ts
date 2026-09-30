import { useCallback, useEffect, useRef, useState } from 'react'
import { API_BASE, api, ApiError, deviceId, getToken, storage } from '../lib/api'

export type Attribution = { author: string | null; license: string | null; source: string | null }
export type DuoImage = { id: number; url: string; attribution: Attribution }
export type Target = DuoImage & { concept_lemma: string; concept_es: string }
export type Hint = { lemma: string; gloss: string | null }

export type RoundView = {
  number: number
  phase: 'describing' | 'guessing' | 'done'
  role: 'describer' | 'guesser'
  difficulty: number
  image?: DuoImage
  hints?: Hint[]
  description?: string | null
  options?: DuoImage[]
  result?: { success: boolean | null; skipped: boolean; chosen_image_id: number | null; target: Target }
}

export type DuoState = {
  type: 'state'
  room: { code: string; lang: string; status: 'waiting' | 'ready' | 'closed'; score: number; rounds_played: number }
  you: { seat: number; consent: boolean }
  players: { seat: number; connected: boolean; consent: boolean }[]
  round: RoundView | null
}

export type Conn = 'connecting' | 'open' | 'reconnecting'

type Action =
  | { action: 'start_round' }
  | { action: 'describe'; text: string }
  | { action: 'guess'; image_id: number }
  | { action: 'consent'; value: boolean }
  | { action: 'skip' }

const WS_BASE = (API_BASE || location.origin).replace(/^http/, 'ws')

/** Normaliza lo que la persona escribe o dicta: "xv4-fwr" → "XV4FWR". */
export const normalizeCode = (raw: string) => raw.toUpperCase().replace(/[^A-Z0-9]/g, '')

const historyKey = (code: string) => `cv.duo.rounds.${code}`

/**
 * Conexión a una sala. La interfaz se dibuja siempre desde el último `state` del servidor;
 * aquí solo se guarda aparte lo que el servidor deja de enviar (las opciones al terminar la
 * ronda, para mostrar qué se eligió) y el orden de aciertos para el khipu.
 */
export function useDuoRoom(code: string) {
  const [state, setState] = useState<DuoState | null>(null)
  const [conn, setConn] = useState<Conn>('connecting')
  const [error, setError] = useState<string | null>(null)
  const [fatal, setFatal] = useState<string | null>(null)
  const [pending, setPending] = useState<Action['action'] | null>(null)
  const [options, setOptions] = useState<{ round: number; list: DuoImage[] } | null>(null)
  const [history, setHistory] = useState<Record<number, boolean>>(() => {
    try {
      return JSON.parse(storage.get(historyKey(code)) ?? '{}') as Record<number, boolean>
    } catch {
      return {}
    }
  })
  const ws = useRef<WebSocket | null>(null)

  useEffect(() => {
    let stopped = false
    let attempt = 0
    let timer = 0

    const retry = () => {
      if (stopped) return
      attempt++
      setConn('reconnecting')
      timer = window.setTimeout(connect, Math.min(15000, 800 * 2 ** (attempt - 1)))
    }

    async function connect() {
      window.clearTimeout(timer)
      if (stopped || ws.current) return
      setConn(attempt ? 'reconnecting' : 'connecting')
      let token: string
      try {
        token = await getToken()
        // join es idempotente: sirve tanto para entrar como para reconectar
        await api(`/duo/rooms/${code}/join`, { method: 'POST', auth: true, module: 'duo' })
      } catch (err) {
        if (err instanceof ApiError && [403, 404, 409].includes(err.status)) {
          stopped = true
          setFatal(
            err.status === 404
              ? 'No encontramos esa sala. Revisa el código.'
              : err.status === 409 && /llena/i.test(err.message)
                ? 'Esa sala ya tiene a sus dos personas.'
                : err.message,
          )
        } else retry()
        return
      }
      if (stopped) return

      const sock = new WebSocket(
        `${WS_BASE}/duo/ws/${code}?token=${encodeURIComponent(token)}&device_id=${encodeURIComponent(deviceId)}`,
      )
      ws.current = sock
      sock.onopen = () => {
        attempt = 0
        setConn('open')
      }
      sock.onmessage = (ev) => {
        const msg = JSON.parse(ev.data as string) as DuoState | { type: 'error'; status: number; detail: string }
        setPending(null)
        if (msg.type === 'error') return setError(msg.detail)
        setError(null)
        setState(msg)
        const r = msg.round
        if (r?.phase === 'guessing' && r.options) setOptions({ round: r.number, list: r.options })
        if (r?.phase === 'done' && r.result && !r.result.skipped && r.result.success != null) {
          const success = r.result.success
          setHistory((h) => {
            if (h[r.number] === success) return h
            const next = { ...h, [r.number]: success }
            storage.set(historyKey(code), JSON.stringify(next))
            return next
          })
        }
        if (msg.room.status === 'closed') {
          stopped = true
          sock.close(1000)
        }
      }
      sock.onclose = (ev) => {
        if (ws.current === sock) ws.current = null
        setPending(null)
        if (stopped) return
        if (ev.code === 4401) storage.remove('cv.token') // token no reconocido: se pedirá otro
        if (ev.code === 4403 || ev.code === 4404) {
          stopped = true
          setFatal(ev.reason || 'No participas en esta sala.')
          return
        }
        retry()
      }
    }

    // Volver a la pestaña o recuperar la red: reconectar ya, sin esperar el temporizador.
    const wake = () => {
      if (!stopped && !ws.current && document.visibilityState === 'visible') {
        attempt = Math.max(attempt, 1)
        void connect()
      }
    }
    // Sin red, el socket puede quedar "medio abierto" (el servidor ya nos dio por caídos y el
    // navegador no se entera): se cierra ya para mostrar "reconectando" y no perder acciones.
    const drop = () => ws.current?.close(4000, 'offline')
    void connect()
    addEventListener('offline', drop)
    addEventListener('online', wake)
    document.addEventListener('visibilitychange', wake)
    return () => {
      stopped = true
      window.clearTimeout(timer)
      removeEventListener('offline', drop)
      removeEventListener('online', wake)
      document.removeEventListener('visibilitychange', wake)
      ws.current?.close(1000)
      ws.current = null
    }
  }, [code])

  const send = useCallback((msg: Action) => {
    const sock = ws.current
    if (sock?.readyState !== WebSocket.OPEN) {
      setError('Sin conexión por un momento; reintentando…')
      return false
    }
    setError(null)
    setPending(msg.action)
    sock.send(JSON.stringify(msg))
    return true
  }, [])

  /** Revocar/dar permiso funciona aunque el socket esté caído (REST). */
  const setConsent = useCallback(
    async (value: boolean) => {
      if (send({ action: 'consent', value })) return
      await api(`/duo/rooms/${code}/consent`, { method: 'PUT', body: { consent: value }, auth: true, module: 'duo' })
    },
    [code, send],
  )

  const leave = useCallback(async () => {
    await api(`/duo/rooms/${code}/leave`, { method: 'POST', auth: true, module: 'duo' })
  }, [code])

  return { state, conn, error, fatal, pending, options, history, send, setConsent, leave, clearError: () => setError(null) }
}
