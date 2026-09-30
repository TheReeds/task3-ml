import { API_BASE, baseHeaders } from './api'
import type { Module } from './types'

type Event = { name: string; module: Module; props?: Record<string, unknown> }

const queue: Event[] = []
let timer: number | undefined

function flush(keepalive = false) {
  window.clearTimeout(timer)
  timer = undefined
  while (queue.length) {
    const events = queue.splice(0, 50)
    fetch(`${API_BASE}/events`, {
      method: 'POST',
      headers: { ...baseHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ events }),
      keepalive,
    }).catch(() => {
      /* la instrumentación nunca debe romper la experiencia */
    })
  }
}

/** Encola un evento; se envía en lote a los 5 s, al llegar a 20, o al ocultarse la página. */
export function track(name: string, module: Module, props?: Record<string, unknown>) {
  queue.push(props ? { name, module, props } : { name, module })
  if (queue.length >= 20) flush()
  else timer ??= window.setTimeout(flush, 5000)
}

document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') flush(true)
})
