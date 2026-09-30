import { useEffect, useRef, type ReactNode } from 'react'

type Props = {
  open: boolean
  onClose: () => void
  label: string
  children: ReactNode
}

/** Hoja inferior sobre <dialog> nativo: foco atrapado, Esc y capa superior gratis. */
export function Sheet({ open, onClose, label, children }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const openRef = useRef(open)

  useEffect(() => {
    openRef.current = open
    const d = ref.current
    if (!d) return
    if (open && !d.open) d.showModal()
    if (!open && d.open) d.close()
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-label={label}
      className="sheet"
      // Solo avisa cierres de la persona (Esc, fondo); no los que hace el padre al cambiar `open`.
      onClose={() => openRef.current && onClose()}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="sheet-body">
        <div className="mx-auto mb-3 h-1.5 w-10 rounded-full bg-line" aria-hidden />
        {open && children}
      </div>
    </dialog>
  )
}
