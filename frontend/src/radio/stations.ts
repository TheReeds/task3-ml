import type { Station } from '../lib/types'

export type Family = 'todo' | 'nivel' | 'tema' | 'voz' | 'otra'

const LEVELS = ['facil', 'intermedia', 'dificil']

export const FAMILY_LABEL: Record<Family, string> = {
  todo: 'Todo',
  nivel: 'Nivel',
  tema: 'Temas',
  voz: 'Voces',
  otra: 'Otras',
}

/** La familia sale del prefijo del id (README: la lista es dinámica). */
export function familyOf(id: string): Family {
  if (id === 'aleatoria') return 'todo'
  if (LEVELS.includes(id) || id.startsWith('nivel:')) return 'nivel'
  if (id.startsWith('dominio:')) return 'tema'
  if (id.startsWith('hablante:')) return 'voz'
  return 'otra'
}

const ORDER: Family[] = ['todo', 'nivel', 'tema', 'voz', 'otra']

export type DialStation = Station & { family: Family; freq: string }

/** Ordena por familia y asigna a cada emisora una "frecuencia" en el dial. */
export function toDial(stations: Station[]): DialStation[] {
  return [...stations]
    .map((s, i) => ({ s, i, f: familyOf(s.id) }))
    .sort((a, b) => ORDER.indexOf(a.f) - ORDER.indexOf(b.f) || a.i - b.i)
    .map(({ s, f }, i) => ({ ...s, family: f, freq: (88.1 + i * 1.6).toFixed(1) }))
}
