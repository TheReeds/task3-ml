export type ToastItem = { id: number; text: string; tone: 'ok' | 'error' }

export const toastListeners = new Set<(t: ToastItem) => void>()
let seq = 0

export function toast(text: string, tone: ToastItem['tone'] = 'ok') {
  const t = { id: ++seq, text, tone }
  toastListeners.forEach((l) => l(t))
}
