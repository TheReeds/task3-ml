import { storage } from '../lib/api'

export type Today = {
  puzzle_id: number
  lang: string
  day: string
  letters: number
  vocabulary_size: number
  hints: { top_1: number; top_10: number; top_100: number }
}

export type PuzzleItem = { puzzle_id: number; day: string; letters: number; is_today: boolean }

export type GuessResult = {
  word: string
  known: boolean
  lemma: string | null
  gloss: string | null
  lexeme_id: number | null
  rank: number | null
  percentile: number | null
  similarity: number | null
  solved: boolean
  can_contribute: boolean
  suggestion: ({ lemma: string } & Record<string, unknown>) | null
}

export type Neighbor = { lemma: string; gloss: string | null; rank: number; percentile: number; similarity: number }

export type Answer = {
  puzzle_id: number
  day: string
  lemma: string
  gloss: string | null
  lexeme_id: number
  neighbors: Neighbor[]
}

export type Guess = GuessResult & { n: number }

export type Game = {
  puzzleId: number
  day: string
  letters: number
  guesses: Guess[]
  status: 'playing' | 'solved' | 'gave_up'
  answer: Answer | null
}

// ── Persistencia local por puzzle_id (el servidor no guarda la partida) ─────
const gameKey = (id: number) => `cv.radar.game.${id}`

export function loadGame(p: { puzzle_id: number; day: string; letters: number }): Game {
  try {
    const raw = storage.get(gameKey(p.puzzle_id))
    if (raw) return JSON.parse(raw) as Game
  } catch {
    /* estado corrupto: se empieza de nuevo */
  }
  return { puzzleId: p.puzzle_id, day: p.day, letters: p.letters, guesses: [], status: 'playing', answer: null }
}

export function saveGame(g: Game) {
  storage.set(gameKey(g.puzzleId), JSON.stringify(g))
}

export function peekStatus(id: number): Game['status'] | 'new' {
  try {
    const raw = storage.get(gameKey(id))
    if (!raw) return 'new'
    const g = JSON.parse(raw) as Game
    return g.guesses.length || g.status !== 'playing' ? g.status : 'new'
  } catch {
    return 'new'
  }
}

// ── Racha: días resueltos el mismo día del puzzle ──────────────────────────
const STREAK_KEY = 'cv.radar.solved_days'

function solvedDays(): string[] {
  try {
    return JSON.parse(storage.get(STREAK_KEY) ?? '[]') as string[]
  } catch {
    return []
  }
}

export function markSolved(day: string) {
  const days = new Set(solvedDays())
  days.add(day)
  storage.set(STREAK_KEY, JSON.stringify([...days].sort().slice(-400)))
}

function prevDay(day: string) {
  const d = new Date(`${day}T12:00:00Z`)
  d.setUTCDate(d.getUTCDate() - 1)
  return d.toISOString().slice(0, 10)
}

/** Días seguidos resueltos hasta hoy (si hoy aún no, cuenta hasta ayer). */
export function streak(today: string): number {
  const days = new Set(solvedDays())
  let d = days.has(today) ? today : prevDay(today)
  let n = 0
  while (days.has(d)) {
    n++
    d = prevDay(d)
  }
  return n
}

// ── Cercanía ───────────────────────────────────────────────────────────────
export type Heat = { key: string; label: string; emoji: string; level: number }

/** Escala por ranking. Se comunica con texto, número y posición, no solo con color. */
export function heat(rank: number | null): Heat {
  if (rank == null) return { key: 'unknown', label: 'Desconocida', emoji: '⬜', level: -1 }
  if (rank === 1) return { key: 'found', label: '¡Es esa!', emoji: '🎯', level: 5 }
  if (rank <= 10) return { key: 'burning', label: 'Ardiendo', emoji: '🔥', level: 4 }
  if (rank <= 50) return { key: 'hot', label: 'Muy cerca', emoji: '🟥', level: 3 }
  if (rank <= 150) return { key: 'warm', label: 'Cerca', emoji: '🟧', level: 2 }
  if (rank <= 400) return { key: 'mild', label: 'Tibio', emoji: '🟨', level: 1 }
  return { key: 'cold', label: 'Lejos', emoji: '🟦', level: 0 }
}

/** Hueco central que ocupa la secreta: el puesto 2 cae justo fuera de él. */
const CORE = 0.2

/** 0 = la secreta, 1 = borde. Logarítmica, para que los anillos top 10/top 100 queden parejos. */
export function radius(rank: number, vocab: number) {
  if (rank <= 1) return 0
  return Math.min(1, CORE + (1 - CORE) * (Math.log(rank / 2 + 0.5) / Math.log(vocab / 2 + 0.5)))
}

/** Ángulo fijo por palabra (FNV-1a): la misma palabra cae siempre en el mismo sitio, para todos. */
export function angle(word: string) {
  let h = 0x811c9dc5
  for (const ch of word.toLocaleLowerCase('es')) {
    h ^= ch.codePointAt(0)!
    h = Math.imul(h, 0x01000193)
  }
  return ((h >>> 0) % 3600) / 10
}

const fmtDay = new Intl.DateTimeFormat('es-PE', { day: 'numeric', month: 'short', timeZone: 'UTC' })
export const dayLabel = (day: string) => fmtDay.format(new Date(`${day}T12:00:00Z`))

export function shareText(g: Game) {
  const known = g.guesses.filter((x) => x.known)
  const best = Math.min(...known.map((x) => x.rank ?? Infinity))
  const trail = g.guesses.slice(-12).map((x) => heat(x.rank).emoji).join('')
  const head =
    g.status === 'solved'
      ? `🎯 en ${g.guesses.length} ${g.guesses.length === 1 ? 'intento' : 'intentos'}`
      : g.status === 'gave_up'
        ? `Me rendí tras ${g.guesses.length} intentos (mejor: #${best})`
        : `${g.guesses.length} intentos · mejor: #${Number.isFinite(best) ? best : '—'}`
  return `Radar · Corpus Vivo · ${dayLabel(g.day)}\n${head}\n${trail}\n${location.origin}${location.pathname}#/radar`
}
