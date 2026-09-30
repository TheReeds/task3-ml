import { useEffect, useState } from 'react'
import { toastListeners as listeners, type ToastItem as Toast } from './toast'

export function Toaster() {
  const [items, setItems] = useState<Toast[]>([])

  useEffect(() => {
    const add = (t: Toast) => {
      setItems((xs) => [...xs.slice(-2), t])
      window.setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== t.id)), 4200)
    }
    listeners.add(add)
    return () => void listeners.delete(add)
  }, [])

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-24 z-50 flex flex-col items-center gap-2 px-4"
    >
      {items.map((t) => (
        <p key={t.id} className="toast" data-tone={t.tone}>
          {t.text}
        </p>
      ))}
    </div>
  )
}
