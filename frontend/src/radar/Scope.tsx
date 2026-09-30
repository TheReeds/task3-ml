import { useMemo, useState, type CSSProperties } from 'react'
import { angle, heat, radius, type Answer, type Guess } from './model'

type Props = {
  guesses: Guess[]
  vocab: number
  letters: number
  answer: Answer | null
  solved: boolean
  scanning: boolean
  flash: string | null
}

const SWEEP_MS = 4000
const EDGE = 45 // radio útil, en % del lado

/** Reloj común: fase del barrido en el instante en que se monta cada elemento. */
const clock = () => performance.now() % SWEEP_MS

function place(word: string, rank: number, vocab: number) {
  const a = angle(word)
  const r = radius(rank, vocab) * EDGE
  const rad = (a * Math.PI) / 180
  return { a, left: 50 + r * Math.sin(rad), top: 50 - r * Math.cos(rad) }
}

type BlipProps = { word: string; rank: number; vocab: number; label: boolean; ghost?: boolean; heatKey?: string; flash?: boolean }

/** El ping se programa según el reloj común al montarse, para que coincida con el paso del barrido. */
function Blip({ word, rank, vocab, label, ghost, heatKey, flash }: BlipProps) {
  const [mountPhase] = useState(clock)
  const p = place(word, rank, vocab)
  const style = {
    left: `${p.left}%`,
    top: `${p.top}%`,
    '--ping-delay': `${(p.a / 360) * SWEEP_MS - mountPhase}ms`,
    '--sweep': `${SWEEP_MS}ms`,
  } as CSSProperties
  return (
    <span className="blip" data-ghost={ghost || undefined} data-heat={heatKey} data-flash={flash || undefined} style={style} aria-hidden>
      <i />
      {label && <b lang="qu">{word}</b>}
    </span>
  )
}

/**
 * Pantalla de radar: la secreta en el centro, cada intento a una distancia logarítmica según
 * su ranking y en un ángulo fijo por palabra. El barrido "ilumina" cada punto al pasar: el
 * retraso del ping se calcula con el mismo reloj que el barrido.
 */
export function Scope({ guesses, vocab, letters, answer, solved, scanning, flash }: Props) {
  const [phase] = useState(clock)

  const known = useMemo(() => guesses.filter((g) => g.known && g.rank != null && g.lemma), [guesses])
  // La acertada no se dibuja como punto: ocupa el centro.
  const plotted = useMemo(() => known.filter((g) => g.rank! > 1), [known])
  // Etiquetas: el último intento y los mejores, saltando las que chocarían con otra ya puesta.
  const labelled = useMemo(() => {
    const last = plotted.at(-1)
    const order = [...(last ? [last] : []), ...[...plotted].sort((a, b) => a.rank! - b.rank!)]
    const placed: { left: number; top: number }[] = []
    const out = new Set<string>()
    for (const g of order) {
      if (out.size >= 5 || out.has(g.lemma!)) continue
      const p = place(g.lemma!, g.rank!, vocab)
      if (placed.some((q) => Math.abs(q.top - p.top) < 6 && Math.abs(q.left - p.left) < 22)) continue
      placed.push(p)
      out.add(g.lemma!)
    }
    return out
  }, [plotted, vocab])

  const rings = [10, 100].filter((r) => r < vocab)
  return (
    <div className="scope" data-solved={solved || undefined}>
      <svg viewBox="-50 -50 100 100" className="scope-grid" aria-hidden>
        <circle r={EDGE} />
        {rings.map((r) => (
          <g key={r}>
            <circle r={radius(r, vocab) * EDGE} />
            <text y={-radius(r, vocab) * EDGE - 1.2}>top {r}</text>
          </g>
        ))}
        <line x1={-EDGE} x2={EDGE} />
        <line y1={-EDGE} y2={EDGE} />
      </svg>

      <div className="scope-sweep" style={{ animationDelay: `${-phase}ms`, animationDuration: `${SWEEP_MS}ms` }} aria-hidden />
      {scanning && <div className="scope-pulse" aria-hidden />}

      {/* Al revelar, las vecinas son puntos huecos; sus nombres van en la lista de abajo. */}
      {answer?.neighbors.map((n) => (
        <Blip key={`n-${n.lemma}`} word={n.lemma} rank={n.rank} vocab={vocab} label={false} ghost />
      ))}

      {plotted.map((g) => (
        <Blip
          key={g.lemma}
          word={g.lemma!}
          rank={g.rank!}
          vocab={vocab}
          label={labelled.has(g.lemma!)}
          heatKey={heat(g.rank).key}
          flash={flash === g.lemma}
        />
      ))}

      <div className="scope-core" aria-hidden>
        {answer || solved ? (
          <span lang="qu" className="font-qu text-lg font-semibold">
            {answer?.lemma ?? known.find((g) => g.rank === 1)?.lemma}
          </span>
        ) : (
          <span className="flex gap-1">
            {Array.from({ length: letters }, (_, i) => (
              <span key={i} className="slot" />
            ))}
          </span>
        )}
      </div>
    </div>
  )
}
