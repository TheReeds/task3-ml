import { toast } from '../ui/toast'

export function roomLink(code: string) {
  return `${location.origin}${location.pathname}#/duo/${code}`
}

export async function shareRoom(code: string) {
  const url = roomLink(code)
  const text = `¡Juguemos Dúo en quechua! Entra con el código ${code}`
  try {
    if (navigator.share) await navigator.share({ title: 'Corpus Vivo · Dúo', text, url })
    else {
      await navigator.clipboard.writeText(`${text}: ${url}`)
      toast('Enlace copiado. Pásaselo a tu pareja de juego.')
    }
  } catch {
    /* compartir cancelado */
  }
}
