import { useEffect, useState } from 'react'
import { api, ApiError, pickAudio } from '../lib/api'
import type { Correction } from '../contribute/CorrectForm'
import { sameWord, splitStem } from '../lib/morph'
import type { Entry, Lexeme, Token } from '../lib/types'
import { Icon, Provenance, Qu } from '../ui/bits'

type Props = {
  entry: Entry
  token: Token
  onSegment: () => void
  onCorrect: (c: Correction) => void
  onPlayEntry: (id: number) => void
}

const nf = new Intl.NumberFormat('es-PE')

function playLemma(lx: Lexeme) {
  const src = pickAudio(lx.audio_url, lx.audio_url_m4a)
  if (src) void new Audio(src).play().catch(() => {})
}

export function WordPanel({ entry, token, onSegment, onCorrect, onPlayEntry }: Props) {
  const [lexeme, setLexeme] = useState<Lexeme | null>(null)
  const [error, setError] = useState<string | null>(null)
  const id = token.lexeme_id

  useEffect(() => {
    if (id == null) return
    const ctrl = new AbortController()
    api<Lexeme>(`/lexemes/${id}?examples=3`, { signal: ctrl.signal }).then(setLexeme, (e: unknown) => {
      if (!ctrl.signal.aborted) setError(e instanceof ApiError ? e.message : 'No se pudo cargar la palabra.')
    })
    return () => ctrl.abort()
  }, [id])

  const split = lexeme ? splitStem(token.token, lexeme.lemma) : null
  const sameAsLemma = !!lexeme && sameWord(token.token, lexeme.lemma)
  const examples = lexeme?.examples?.filter((x) => x.entry_id !== entry.id).slice(0, 2) ?? []

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Qu className="text-4xl font-semibold tracking-tight">{token.token}</Qu>
        <button className="btn-icon ml-auto" onClick={onSegment} aria-label={`Oír «${token.token}» en la frase`}>
          <Icon name="speaker" />
        </button>
      </div>

      {id == null ? (
        <p className="text-muted">
          Todavía no sabemos de qué raíz viene esta palabra. Si está mal escrita, puedes corregirla.
        </p>
      ) : error ? (
        <p className="text-muted">{error}</p>
      ) : !lexeme ? (
        <div className="space-y-3" aria-busy="true" aria-label="Cargando significado">
          <div className="skeleton h-12 w-2/3" />
          <div className="skeleton h-5 w-1/2" />
        </div>
      ) : (
        <>
          <div className="morph">
            {!sameAsLemma && (
              <>
                <span className="morph-label">forma</span>
                <Qu className="text-xl">
                  {split ? (
                    <>
                      <b className="morph-stem">{split.stem}</b>
                      {split.formRest}
                    </>
                  ) : (
                    token.token
                  )}
                </Qu>
                <span className="morph-arrow" aria-label="viene de">
                  ←
                </span>
              </>
            )}
            <span className="morph-label">{sameAsLemma ? 'es la raíz' : 'raíz'}</span>
            <Qu className="text-xl">
              {split && !sameAsLemma ? (
                <>
                  <b className="morph-stem">{split.stem}</b>
                  {split.lemmaRest}
                </>
              ) : (
                lexeme.lemma
              )}
            </Qu>
            {lexeme.audio_url && (
              <button className="btn-icon -my-3 ml-auto" onClick={() => playLemma(lexeme)} aria-label={`Oír «${lexeme.lemma}»`}>
                <Icon name="speaker" className="size-4" />
              </button>
            )}
          </div>

          <div>
            <p className="font-qu text-2xl leading-snug">{lexeme.gloss ?? <span className="text-muted">sin glosa</span>}</p>
            <p className="mt-1 text-sm text-muted">
              Aparece {nf.format(lexeme.frequency)} {lexeme.frequency === 1 ? 'vez' : 'veces'} en el corpus
              {lexeme.is_function_word && ' · palabra gramatical'}
            </p>
          </div>

          {examples.length > 0 && (
            <div>
              <h3 className="eyebrow mb-2">También suena en</h3>
              <ul className="space-y-2">
                {examples.map((x) => (
                  <li key={x.entry_id}>
                    <button className="example" onClick={() => onPlayEntry(x.entry_id)}>
                      <Icon name="play" className="size-4 shrink-0 text-tint" />
                      <span>
                        <Qu className="block">{x.text}</Qu>
                        {x.translation && <span className="block text-sm text-muted">{x.translation}</span>}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      <div className="flex flex-wrap gap-2 border-t border-line pt-4">
        <button className="btn-soft" onClick={() => onCorrect({ kind: 'transcription', entry, token })}>
          <Icon name="pencil" className="size-4" /> Está mal escrita
        </button>
        {lexeme && (
          <button className="btn-soft" onClick={() => onCorrect({ kind: 'gloss', lexeme })}>
            <Icon name="pencil" className="size-4" /> El significado no es ese
          </button>
        )}
        {lexeme && <Provenance origin={lexeme.audio_origin} />}
      </div>
    </div>
  )
}
