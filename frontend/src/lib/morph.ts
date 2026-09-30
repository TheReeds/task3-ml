/** Parte común entre una forma flexionada y su lema: kuti|rqani ← kuti|y. null si casi no comparten. */
export function splitStem(form: string, lemma: string) {
  const f = form.toLocaleLowerCase('es')
  const l = lemma.toLocaleLowerCase('es')
  let i = 0
  while (i < f.length && i < l.length && f[i] === l[i]) i++
  return i >= 2 ? { stem: form.slice(0, i), formRest: form.slice(i), lemmaRest: lemma.slice(i) } : null
}

export function sameWord(a: string, b: string) {
  return a.toLocaleLowerCase('es') === b.toLocaleLowerCase('es')
}
