import { storage } from '../lib/api'

export type ContribType =
  | 'transcription_fix'
  | 'translation_fix'
  | 'gloss_fix'
  | 'new_lemma'
  | 'audio_recording'
  | 'new_sentence'

export const TYPES: { id: ContribType; label: string; short: string; from: string }[] = [
  { id: 'transcription_fix', label: 'Corrección de escritura', short: 'Escritura', from: 'Radio' },
  { id: 'translation_fix', label: 'Traducción propuesta', short: 'Traducción', from: 'Radio' },
  { id: 'gloss_fix', label: 'Significado propuesto', short: 'Significado', from: 'Radio o Radar' },
  { id: 'new_lemma', label: 'Palabra nueva', short: 'Palabras nuevas', from: 'Radar o Lente' },
  { id: 'audio_recording', label: 'Pronunciación grabada', short: 'Pronunciación', from: 'Lente' },
  { id: 'new_sentence', label: 'Frase de Dúo', short: 'Frases de Dúo', from: 'Dúo' },
]
export const typeLabel = (t: string) => TYPES.find((x) => x.id === t)?.label ?? t

export type ReviewItem = {
  contribution_id: number
  type: ContribType
  lang: string
  original: string | null
  proposed: string | null
  context: Record<string, unknown>
  proposer_reliability: number | null
}

export type Verdict = 'accept' | 'reject' | 'unsure'
export type ReviewResult = { contribution_id: number; recorded: boolean; status: 'pending' | 'accepted' | 'rejected' | 'stale' }

export type Impact = {
  lang: string
  timeline: { day: string; created: number; accepted: number; reviews: number }[]
  contributions: { pending: number; accepted: number; rejected: number; stale: number }
  accepted_by_type: Record<string, number>
  reviews: number
  contributors: number
  reviewers: number
  fleiss_kappa: number | null
}

export type Mine = {
  id: number
  type: string
  payload: Record<string, unknown>
  status: 'pending' | 'accepted' | 'rejected' | 'stale' | 'withdrawn'
  created_at: string
}

// ── Diferencia resaltada: por palabras en textos, por letras en palabras sueltas ──
export type Diff = { pre: string; a: string; b: string; post: string }

export function diff(before: string, after: string): Diff {
  const words = /\s/.test(before) || /\s/.test(after)
  const A = words ? before.split(/(\s+)/) : [...before]
  const B = words ? after.split(/(\s+)/) : [...after]
  let i = 0
  while (i < A.length && i < B.length && A[i] === B[i]) i++
  let j = 0
  while (j < A.length - i && j < B.length - i && A[A.length - 1 - j] === B[B.length - 1 - j]) j++
  return {
    pre: A.slice(0, i).join(''),
    a: A.slice(i, A.length - j).join(''),
    b: B.slice(i, B.length - j).join(''),
    post: A.slice(A.length - j).join(''),
  }
}

// ── Lenguaje humano ────────────────────────────────────────────────────────
export function reliabilityWord(r: number) {
  return r < 0.4 ? 'baja' : r < 0.65 ? 'media' : 'alta'
}

/** Fleiss κ en palabras (Landis y Koch, simplificado). */
export function agreement(k: number | null): { label: string; detail: string; level: number } {
  if (k == null) return { label: 'Aún sin medir', detail: 'Hacen falta más revisiones de los mismos aportes para saber cuánto coinciden.', level: 0 }
  if (k < 0.2) return { label: 'Poco acuerdo', detail: 'Quienes revisan suelen opinar distinto. Vale la pena usar más "No estoy seguro".', level: 1 }
  if (k < 0.4) return { label: 'Acuerdo débil', detail: 'Coinciden algo más de lo que se esperaría por azar.', level: 2 }
  if (k < 0.6) return { label: 'Acuerdo moderado', detail: 'Coinciden bastante: las decisiones empiezan a ser sólidas.', level: 3 }
  if (k < 0.8) return { label: 'Buen acuerdo', detail: 'La comunidad coincide en la mayoría de los casos.', level: 4 }
  return { label: 'Acuerdo casi total', detail: 'Quienes revisan coinciden casi siempre.', level: 5 }
}

export const STATUS: Record<Mine['status'], { label: string; detail: string }> = {
  pending: { label: 'En revisión', detail: 'Esperando que la comunidad opine.' },
  accepted: { label: 'Aceptado', detail: 'Ya es parte del corpus. ¡Gracias!' },
  rejected: { label: 'No aceptado', detail: 'La comunidad decidió no incluirlo.' },
  stale: { label: 'Aceptado, sin aplicar', detail: 'Alguien corrigió ese dato antes; tu versión quedó registrada.' },
  withdrawn: { label: 'Retirado', detail: 'Retiraste el permiso para guardarlo.' },
}

// ── Preferencias y tramo del día (solo en este dispositivo) ────────────────
const today = () => new Date().toLocaleDateString('en-CA')

export function loadStrand(): Verdict[] {
  try {
    const s = JSON.parse(storage.get('cv.taller.strand') ?? 'null') as { day: string; v: Verdict[] } | null
    return s?.day === today() ? s.v : []
  } catch {
    return []
  }
}
export function saveStrand(v: Verdict[]) {
  storage.set('cv.taller.strand', JSON.stringify({ day: today(), v }))
}

export function loadFilters(): ContribType[] {
  try {
    return JSON.parse(storage.get('cv.taller.types') ?? '[]') as ContribType[]
  } catch {
    return []
  }
}
export const saveFilters = (t: ContribType[]) => storage.set('cv.taller.types', JSON.stringify(t))
