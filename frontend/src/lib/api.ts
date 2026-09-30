import type { Module } from './types'

export const API_BASE = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '').replace(/\/+$/, '')

// crypto.randomUUID solo existe en contextos seguros; en http://192.168.x (prueba en celular) no.
function uuid(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  const b = crypto.getRandomValues(new Uint8Array(16))
  b[6] = (b[6] & 0x0f) | 0x40
  b[8] = (b[8] & 0x3f) | 0x80
  const h = Array.from(b, (x) => x.toString(16).padStart(2, '0')).join('')
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`
}

export const storage = {
  get(key: string): string | null {
    try {
      return localStorage.getItem(key)
    } catch {
      return null
    }
  },
  set(key: string, value: string) {
    try {
      localStorage.setItem(key, value)
    } catch {
      /* modo privado: la sesión vive solo en memoria */
    }
  },
  remove(key: string) {
    try {
      localStorage.removeItem(key)
    } catch {
      /* idem */
    }
  },
}

export const deviceId: string =
  storage.get('cv.device') ??
  (() => {
    const id = uuid()
    storage.set('cv.device', id)
    return id
  })()

export const sessionId = uuid()

export class ApiError extends Error {
  status: number
  retryAfter: number | null
  constructor(message: string, status: number, retryAfter: number | null = null) {
    super(message)
    this.status = status
    this.retryAfter = retryAfter
  }
}

export function baseHeaders(module?: Module): Record<string, string> {
  const h: Record<string, string> = { 'X-Device-Id': deviceId, 'X-Session-Id': sessionId }
  if (module) h['X-Module'] = module
  return h
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

async function readDetail(res: Response): Promise<string | null> {
  try {
    const body = (await res.json()) as { detail?: unknown }
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) {
      return body.detail.map((d: { msg?: string }) => d.msg ?? '').filter(Boolean).join(' · ') || null
    }
  } catch {
    /* cuerpo no JSON */
  }
  return null
}

// ── Sesión anónima perezosa ────────────────────────────────────────────────
const TOKEN_KEY = 'cv.token'
let tokenPromise: Promise<string> | null = null

export function getToken(): Promise<string> {
  const saved = storage.get(TOKEN_KEY)
  if (saved) return Promise.resolve(saved)
  tokenPromise ??= (async () => {
    try {
      const data = await api<{ token: string }>('/auth/anonymous', { method: 'POST' })
      storage.set(TOKEN_KEY, data.token)
      return data.token
    } finally {
      tokenPromise = null
    }
  })()
  return tokenPromise
}

// ── Cliente ────────────────────────────────────────────────────────────────
type Options = {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH'
  body?: unknown
  module?: Module
  auth?: boolean
  signal?: AbortSignal
}

export async function api<T>(path: string, opts: Options = {}): Promise<T> {
  const method = opts.method ?? 'GET'
  for (let attempt = 0; ; attempt++) {
    const headers = baseHeaders(opts.module)
    if (opts.body !== undefined) headers['Content-Type'] = 'application/json'
    if (opts.auth) headers.Authorization = `Bearer ${await getToken()}`

    let res: Response
    try {
      res = await fetch(API_BASE + path, {
        method,
        headers,
        body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
        signal: opts.signal,
      })
    } catch (err) {
      if (opts.signal?.aborted) throw err
      if (method === 'GET' && attempt < 2) {
        await sleep(700 * (attempt + 1))
        continue
      }
      throw new ApiError('No hay conexión con el servidor. Revisa tu internet e inténtalo otra vez.', 0)
    }

    if (res.ok) return (res.status === 204 ? undefined : await res.json()) as T

    if (res.status === 401 && opts.auth && attempt === 0) {
      storage.remove(TOKEN_KEY)
      continue
    }
    if (res.status === 429) {
      const wait = Number(res.headers.get('Retry-After')) || 5
      if (method === 'GET' && attempt === 0 && wait <= 10) {
        await sleep(wait * 1000)
        continue
      }
      throw new ApiError(`Vas muy rápido. Espera ${wait} s y vuelve a intentarlo.`, 429, wait)
    }
    if (res.status >= 500 && method === 'GET' && attempt === 0) {
      await sleep(800)
      continue
    }
    throw new ApiError((await readDetail(res)) ?? `Error ${res.status}`, res.status)
  }
}

// ── Media ──────────────────────────────────────────────────────────────────
export function mediaUrl(rel: string): string {
  return /^https?:/.test(rel) ? rel : API_BASE + encodeURI(rel)
}

let opusSupport: boolean | null = null
function canPlayOpus(): boolean {
  opusSupport ??= new Audio().canPlayType('audio/ogg; codecs="opus"') !== ''
  return opusSupport
}

/** Elige Ogg/Opus (más liviano) o AAC (iOS antiguo) y devuelve la URL absoluta. */
export function pickAudio(ogg: string | null, m4a: string | null): string | null {
  const rel = canPlayOpus() ? (ogg ?? m4a) : (m4a ?? ogg)
  return rel ? mediaUrl(rel) : null
}
