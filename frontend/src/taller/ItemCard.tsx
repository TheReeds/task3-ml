import { mediaUrl, pickAudio } from '../lib/api'
import { Icon, Qu } from '../ui/bits'
import type { useClip } from './clip'
import { diff, reliabilityWord, typeLabel, type ReviewItem } from './model'

type Clip = ReturnType<typeof useClip>

function Listen({ clip, id, src, seg, children }: { clip: Clip; id: string; src: string | null; seg?: [number, number] | null; children: string }) {
  const on = clip.playing === id
  return (
    <button className="listen" data-on={on || undefined} onClick={() => (on ? clip.stop() : clip.play(id, src, seg))} disabled={!src}>
      <Icon name={on ? 'pause' : 'speaker'} className="size-4" />
      {children}
    </button>
  )
}

/** Antes → propuesta, con la parte que cambia resaltada (no solo por color: tachado/subrayado). */
function Change({ before, after, qu }: { before: string | null; after: string | null; qu: boolean }) {
  const Text = qu ? Qu : 'span'
  if (before == null) {
    return (
      <div className="change">
        <p className="change-label">Propuesta</p>
        <Text className="change-new">{after}</Text>
      </div>
    )
  }
  const d = diff(before, after ?? '')
  return (
    <div className="change">
      <p className="change-label">Dice ahora</p>
      <Text className="change-old">
        {d.pre}
        {d.a ? <del>{d.a}</del> : <span className="diff-gap" aria-label="aquí se agrega algo" />}
        {d.post}
      </Text>
      <p className="change-label mt-3">Propuesta</p>
      <Text className="change-new">
        {d.pre}
        {d.b ? <ins>{d.b}</ins> : <span className="diff-gap" aria-label="aquí se quitó algo" />}
        {d.post}
      </Text>
    </div>
  )
}

const str = (v: unknown) => (typeof v === 'string' ? v : null)

export function ItemCard({ item, clip }: { item: ReviewItem; clip: Clip }) {
  const c = item.context
  const audioSrc = pickAudio(str(c.audio_url), str(c.audio_url_m4a))

  return (
    <article className="review-card" aria-labelledby={`item-${item.contribution_id}`}>
      <header className="flex flex-wrap items-center gap-2">
        <h2 id={`item-${item.contribution_id}`} className="phase-tag">
          {typeLabel(item.type)}
        </h2>
        {item.proposer_reliability != null && (
          <span className="text-xs text-muted" title="La identidad de quien propuso está oculta">
            Propuso alguien con confiabilidad {reliabilityWord(item.proposer_reliability)}
          </span>
        )}
      </header>

      {item.type === 'transcription_fix' && <Transcription item={item} clip={clip} audioSrc={audioSrc} />}

      {item.type === 'translation_fix' && (
        <>
          <p className="ask">¿La traducción propuesta dice lo mismo que la frase?</p>
          <blockquote className="said">
            <Qu>{str(c.text)}</Qu>
          </blockquote>
          <Listen clip={clip} id="sentence" src={audioSrc}>
            Oír la frase
          </Listen>
          <Change before={item.original} after={item.proposed} qu={false} />
        </>
      )}

      {item.type === 'gloss_fix' && (
        <>
          <p className="ask">
            ¿Qué significa <Qu className="font-semibold">{str(c.lemma)}</Qu>?
          </p>
          <Change before={item.original} after={item.proposed} qu={false} />
          <Examples examples={c.examples} />
        </>
      )}

      {item.type === 'new_lemma' && (
        <>
          <p className="ask">
            {c.existing_lemma ? '¿Esta palabra nombra este objeto?' : '¿Esta palabra existe y significa eso?'}
          </p>
          <p className="big-word">
            <Qu>{str(c.lemma)}</Qu>
          </p>
          {str(c.vision_label) && (
            <p className="text-muted">
              Para el objeto que la cámara reconoció como «{str(c.vision_label)}»
            </p>
          )}
          {item.proposed && <Change before={null} after={item.proposed} qu={false} />}
          {str(c.origin_module) && <p className="text-xs text-muted">Llegó desde {c.origin_module === 'lente' ? 'Lente' : 'Radar'}</p>}
        </>
      )}

      {item.type === 'audio_recording' && (
        <>
          <p className="ask">
            ¿La grabación nueva pronuncia bien <Qu className="font-semibold">{str(c.lemma)}</Qu>
            {str(c.gloss) && <span className="text-muted"> («{str(c.gloss)}»)</span>}?
          </p>
          <div className="grid grid-cols-2 gap-2">
            <Listen clip={clip} id="orig" src={pickAudio(item.original, str(c.original_m4a))}>
              Actual (sintética)
            </Listen>
            <Listen clip={clip} id="prop" src={pickAudio(item.proposed, str(c.proposed_m4a))}>
              Grabación nueva
            </Listen>
          </div>
        </>
      )}

      {item.type === 'new_sentence' && (
        <>
          <p className="ask">¿La frase es quechua natural y describe la imagen?</p>
          {str(c.image_url) && (
            <figure className="photo">
              <img src={mediaUrl(str(c.image_url)!)} alt={str(c.concept_es) ?? ''} />
              {str(c.concept_es) && <figcaption className="photo-badge">{str(c.concept_es)}</figcaption>}
            </figure>
          )}
          <blockquote className="said said-big">
            <Qu>{item.proposed}</Qu>
          </blockquote>
          {typeof c.understood === 'boolean' && (
            <p className="text-sm text-muted">
              {c.understood ? 'Su pareja de juego la entendió y eligió bien la imagen.' : 'Su pareja de juego no acertó con esta descripción.'}
            </p>
          )}
        </>
      )}
    </article>
  )
}

function Transcription({ item, clip, audioSrc }: { item: ReviewItem; clip: Clip; audioSrc: string | null }) {
  const c = item.context
  const seg = Array.isArray(c.segment_ms) ? (c.segment_ms as [number, number]) : null
  const pos = typeof c.position === 'number' ? c.position : -1
  const words = (str(c.text) ?? '').split(' ')
  return (
    <>
      <p className="ask">Escucha la palabra marcada. ¿Se escribe como propone la corrección?</p>
      <blockquote className="said">
        <Qu>
          {words.map((w, i) => (
            <span key={i}>
              {i > 0 && ' '}
              {i === pos ? <mark className="said-mark">{w}</mark> : w}
            </span>
          ))}
        </Qu>
      </blockquote>
      <div className="flex flex-wrap gap-2">
        <Listen clip={clip} id="segment" src={audioSrc} seg={seg}>
          Oír solo la palabra
        </Listen>
        <Listen clip={clip} id="sentence" src={audioSrc}>
          Oír la frase
        </Listen>
      </div>
      <Change before={item.original} after={item.proposed} qu />
      {str(c.translation) && <p className="text-sm text-muted">«{str(c.translation)}»</p>}
    </>
  )
}

function Examples({ examples }: { examples: unknown }) {
  const list = Array.isArray(examples) ? (examples as { text: string; translation: string | null }[]) : []
  if (!list.length) return <p className="text-sm text-muted">No hay frases de ejemplo en el corpus para esta palabra.</p>
  return (
    <div>
      <p className="eyebrow mb-2">Cómo se usa en el corpus</p>
      <ul className="space-y-2">
        {list.slice(0, 3).map((x, i) => (
          <li key={i} className="example">
            <span>
              <Qu className="block">{x.text}</Qu>
              {x.translation && <span className="block text-sm text-muted">{x.translation}</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
