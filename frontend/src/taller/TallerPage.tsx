import { useEffect, useState, type KeyboardEvent } from 'react'
import { api, storage } from '../lib/api'
import { Sheet } from '../ui/Sheet'
import { toast } from '../ui/toast'
import { Impact } from './Impact'
import { Mine } from './Mine'
import { reliabilityWord } from './model'
import { Review } from './Review'

type Tab = 'review' | 'impact' | 'mine'
const TABS: { id: Tab; label: string }[] = [
  { id: 'review', label: 'Revisar' },
  { id: 'impact', label: 'Impacto' },
  { id: 'mine', label: 'Tus aportes' },
]

type Me = { id: string; reliability: number; is_native_speaker: boolean }
const pct = new Intl.NumberFormat('es-PE', { maximumFractionDigits: 2, minimumFractionDigits: 2 })

export default function TallerPage() {
  const [tab, setTab] = useState<Tab>('review')
  const [me, setMe] = useState<Me | null>(null)
  const [aboutOpen, setAboutOpen] = useState(false)
  const [intro, setIntro] = useState(() => storage.get('cv.taller.intro') !== '1')

  useEffect(() => {
    // Revisar necesita sesión anónima de todos modos; la confiabilidad sale de /auth/me.
    api<Me>('/auth/me', { auth: true }).then(setMe, () => {})
  }, [])

  function onTabKey(e: KeyboardEvent) {
    const i = TABS.findIndex((t) => t.id === tab)
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!d) return
    const next = TABS[(i + d + TABS.length) % TABS.length]
    setTab(next.id)
    document.getElementById(`tab-${next.id}`)?.focus()
  }

  async function setNative(v: boolean) {
    try {
      setMe(await api<Me>('/auth/me', { method: 'PATCH', body: { is_native_speaker: v }, auth: true, module: 'taller' }))
    } catch {
      toast('No se pudo guardar. Inténtalo otra vez.', 'error')
    }
  }

  return (
    <section className="taller" aria-label="Taller">
      <div className="glow" aria-hidden />
      <div className="relative z-10 mx-auto w-full max-w-md px-5 pt-4">
        <header className="text-center">
          <p className="eyebrow">Revisión comunitaria</p>
          <h1 className="mt-1 font-qu text-[clamp(1.8rem,7vw,2.4rem)] font-semibold leading-tight">Taller</h1>
          <p className="mt-1 text-muted">Aquí se decide, entre muchas personas, qué entra al corpus.</p>
          {me && (
            <button className="chip-btn mt-3" onClick={() => setAboutOpen(true)}>
              Tu confiabilidad: {reliabilityWord(me.reliability)} ({pct.format(me.reliability)})
            </button>
          )}
        </header>

        {intro && tab === 'review' && (
          <div className="intro-card mt-4">
            <p className="font-bold">Cómo funciona</p>
            <ul className="consent-list mt-2 text-sm">
              <li>Verás los aportes de uno en uno, con lo necesario para juzgarlos.</li>
              <li>Ninguna persona decide sola: hacen falta varios juicios coincidentes.</li>
              <li>
                Si dudas, elige <b>No estoy seguro</b>: nunca te resta, y es mejor que adivinar.
              </li>
            </ul>
            <button
              className="btn-soft mt-3"
              onClick={() => {
                storage.set('cv.taller.intro', '1')
                setIntro(false)
              }}
            >
              Entendido
            </button>
          </div>
        )}

        <div className="tabs mt-4" role="tablist" aria-label="Secciones del Taller" onKeyDown={onTabKey}>
          {TABS.map((t) => (
            <button
              key={t.id}
              id={`tab-${t.id}`}
              role="tab"
              aria-selected={tab === t.id}
              aria-controls={`panel-${t.id}`}
              tabIndex={tab === t.id ? 0 : -1}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div id={`panel-${tab}`} role="tabpanel" aria-labelledby={`tab-${tab}`} className="mt-4 pb-6">
          {tab === 'review' && <Review onGoImpact={() => setTab('impact')} />}
          {tab === 'impact' && <Impact onReview={() => setTab('review')} />}
          {tab === 'mine' && <Mine />}
        </div>
      </div>

      <Sheet open={aboutOpen} onClose={() => setAboutOpen(false)} label="Qué es la confiabilidad">
        {me && (
          <div className="space-y-4">
            <h2 className="font-qu text-2xl font-semibold">Tu confiabilidad</h2>
            <p>
              Es cuánto pesa tu juicio al decidir. Empieza en 0,50 y se ajusta sola, con algunos aportes cuya respuesta ya se
              conoce, mezclados entre los demás. No se pueden distinguir, y está bien: basta con juzgar cada uno con cuidado.
            </p>
            <ul className="consent-list text-sm">
              <li>
                <b>No estoy seguro</b> nunca la baja.
              </li>
              <li>No es un ranking ni se muestra a nadie: solo sirve para que las decisiones sean más fiables.</li>
              <li>Tu identidad no se ve. Tampoco ves quién propuso cada aporte, solo su confiabilidad.</li>
            </ul>
            <label className="flex items-start gap-3 rounded-2xl border border-line p-4">
              <input
                type="checkbox"
                className="mt-1 size-5 accent-[var(--tint)]"
                checked={me.is_native_speaker}
                onChange={(e) => void setNative(e.target.checked)}
              />
              <span>
                <span className="font-bold">Hablo quechua como lengua materna</span>
                <span className="mt-1 block text-sm text-muted">
                  Solo aumenta el peso de tus juicios si además aciertas en los aportes de respuesta conocida. Declararlo no
                  basta por sí solo.
                </span>
              </span>
            </label>
          </div>
        )}
      </Sheet>
    </section>
  )
}
