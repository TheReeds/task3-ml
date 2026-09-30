import { lazy, Suspense, useEffect, useState } from 'react'
import { RadioPage } from './radio/RadioPage'
import { Toaster } from './ui/Toaster'

// Cada módulo en su propio fragmento: Radio (la puerta de entrada) va en el inicial.
const RadarPage = lazy(() => import('./radar/RadarPage'))
const DuoPage = lazy(() => import('./duo/DuoPage'))
const TallerPage = lazy(() => import('./taller/TallerPage'))

const MODULES = [
  { id: 'radio', name: 'Radio', glyph: '◉' },
  { id: 'radar', name: 'Radar', glyph: '◎' },
  { id: 'lente', name: 'Lente', glyph: '◐' },
  { id: 'duo', name: 'Dúo', glyph: '◑' },
  { id: 'taller', name: 'Taller', glyph: '◇' },
] as const

type ModuleId = (typeof MODULES)[number]['id']

/** `#/duo/XV4FWR` → { id: 'duo', param: 'XV4FWR' } */
function routeFromHash(): { id: ModuleId; param: string | null } {
  const [id, param] = location.hash.replace(/^#\/?/, '').split('/')
  return MODULES.some((m) => m.id === id) ? { id: id as ModuleId, param: param || null } : { id: 'radio', param: null }
}

export default function App() {
  const [{ id: route, param }, setRoute] = useState(routeFromHash)

  useEffect(() => {
    const on = () => setRoute(routeFromHash())
    addEventListener('hashchange', on)
    return () => removeEventListener('hashchange', on)
  }, [])

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="flex items-center gap-2 px-5 pt-[max(env(safe-area-inset-top),0.75rem)]">
        <a href="#/radio" className="font-qu text-lg font-semibold tracking-tight">
          Corpus <span className="text-tint">Vivo</span>
        </a>
        <span lang="qu" className="ml-auto rounded-full border border-line px-3 py-1 text-sm text-muted">
          Runasimi
        </span>
      </header>

      <main className="flex-1 pb-24">
        {/* La radio sigue sonando aunque se visite otro módulo. */}
        <div hidden={route !== 'radio'}>
          <RadioPage />
        </div>
        {route === 'radar' && (
          <Suspense fallback={null}>
            <RadarPage />
          </Suspense>
        )}
        {route === 'duo' && (
          <Suspense fallback={null}>
            <DuoPage code={param} />
          </Suspense>
        )}
        {route === 'taller' && (
          <Suspense fallback={null}>
            <TallerPage />
          </Suspense>
        )}
        {route === 'lente' && (
          <div className="mx-auto max-w-md px-6 py-24 text-center">
            <p className="font-qu text-3xl font-semibold">{MODULES.find((m) => m.id === route)?.name}</p>
            <p className="mt-2 text-muted">Este módulo está en construcción.</p>
          </div>
        )}
      </main>

      <nav aria-label="Módulos" className="tabbar">
        {MODULES.map((m) => (
          <a key={m.id} href={`#/${m.id}`} aria-current={route === m.id ? 'page' : undefined} className="tab">
            <span aria-hidden className="text-lg leading-none">
              {m.glyph}
            </span>
            <span className="text-xs">{m.name}</span>
          </a>
        ))}
      </nav>
      <Toaster />
    </div>
  )
}
