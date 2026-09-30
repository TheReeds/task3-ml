export type Module = 'app' | 'radio' | 'radar' | 'lente' | 'duo' | 'taller'

export type Token = {
  position: number
  token: string
  start_ms: number
  end_ms: number
  aligned: boolean
  lexeme_id: number | null
}

export type Origin = 'dataset' | 'model' | 'community' | 'synthetic' | (string & {})

export type Translation = { id: number; lang: string; text: string; origin: Origin }

export type Entry = {
  id: number
  lang: string
  text: string
  audio_url: string
  audio_url_m4a: string | null
  audio_origin: Origin
  duration_ms: number
  domain: string | null
  speaker: string | null
  difficulty: number | null
  source: string | null
  supersedes_id: number | null
  translation: Translation | null
  tokens: Token[]
}

export type Station = { id: string; name: string; description: string; entries: number }

export type LexemeExample = { entry_id: number; text: string; translation: string | null }

export type Lexeme = {
  id: number
  lang: string
  lemma: string
  gloss: string | null
  frequency: number
  is_function_word: boolean
  is_concrete: boolean
  audio_url: string | null
  audio_url_m4a: string | null
  audio_origin: Origin
  examples?: LexemeExample[]
}

export type Language = {
  code: string
  name: string
  endonym: string
  iso639_1: string | null
  default: boolean
  modules: Record<string, boolean>
}

export type Contribution = {
  id: number
  type: string
  status: 'pending' | 'accepted' | 'rejected' | 'stale' | 'withdrawn'
}
