# 01 — Radio

> Lee `README.md` y el `DESIGN.md` de la base antes de empezar.

## Qué es

La puerta de entrada de Corpus Vivo. **Al abrir la app ya está sonando**: una frase en quechua
con su transcripción, donde la palabra que se pronuncia se resalta en el momento exacto, y la
traducción al español debajo. Al terminar, encadena la siguiente según la **emisora** elegida
(aleatoria, por dificultad; más adelante por tema o hablante). Se puede pausar y **tocar una
palabra** para ver su lema, glosa, frecuencia y ejemplos, y desde ahí señalar un error.

Es la respuesta directa al problema del proyecto: pasar de "descargar gigas y programar" a
"abrir un enlace y escuchar". La métrica estrella es **tiempo hasta la primera frase escuchada**.

> Nota de navegador: el autoplay con sonido suele bloquearse hasta el primer gesto. Diseña ese
> primer toque como parte de la experiencia (no como un error), y deja todo precargado detrás.

## Endpoints

### Emisoras

```http
GET /radio/stations
[
 {"id": "aleatoria",  "name": "Aleatoria",  "description": "Todo el corpus en orden aleatorio", "entries": 855},
 {"id": "facil",      "name": "Fácil",      "description": "Frases cortas con vocabulario frecuente", "entries": 285},
 {"id": "intermedia", "name": "Intermedia", "description": "Dificultad media", "entries": 285},
 {"id": "dificil",    "name": "Difícil",    "description": "Frases largas con vocabulario poco frecuente", "entries": 285},
 {"id": "hablante:mms-tts-quy", "name": "Hablante: mms-tts-quy", "description": "…", "entries": 855}
]
```

La lista es dinámica: aparecerán `dominio:<x>` y `hablante:<x>` cuando el corpus real traiga
esos metadatos. No la escribas fija.

### Siguiente frase

```http
GET /radio/stations/{station_id}/next?after={id_de_la_que_acaba_de_sonar}
```

```json
{
  "id": 2572, "lang": "quy",
  "text": "Kutirqani hinaspam tiyarqani umalliqniy ruray niwaptin",
  "audio_url": "/media/quy/americasnlp-dev-0007.ogg",
  "audio_origin": "synthetic", "duration_ms": 5584,
  "domain": null, "speaker": "mms-tts-quy", "difficulty": 0.26,
  "source": "americasnlp-2021-dev", "supersedes_id": null,
  "translation": {"id": 2566, "lang": "spa", "origin": "dataset",
                  "text": "Regresé y me senté porque mi jefe me dijo que lo hiciera."},
  "tokens": [
    {"position": 0, "token": "Kutirqani", "start_ms": 442,  "end_ms": 1125, "aligned": true, "lexeme_id": 3809},
    {"position": 1, "token": "hinaspam",  "start_ms": 1868, "end_ms": 2430, "aligned": true, "lexeme_id": 3622},
    {"position": 2, "token": "tiyarqani", "start_ms": 2531, "end_ms": 3113, "aligned": true, "lexeme_id": 4278},
    {"position": 3, "token": "umalliqniy","start_ms": 3616, "end_ms": 4238, "aligned": true, "lexeme_id": 4311}
  ]
}
```

- **Resaltado:** con el tiempo actual del audio `t`, la palabra activa es el token con
  `start_ms ≤ t < end_ms`. Entre palabras hay silencios (pausas en comas): decide qué se ve.
- `aligned: false` → el token (números, signos) no se alineó y heredó el hueco entre vecinos.
- `lexeme_id: null` → la palabra no tiene lema conocido: no abre el panel (o invita a aportar).
- `translation` puede ser `null`; `origin` puede ser `dataset`, `model` o `community`.
- Emisora aleatoria: nunca repite la que acaba de sonar. Emisoras ordenadas: al final vuelven
  al principio.
- **Precarga**: pide la siguiente (y su audio) mientras suena la actual; así el encadenado es
  instantáneo.

### Panel de palabra

```http
GET /lexemes/{lexeme_id}?examples=2
{
  "id": 3809, "lang": "quy", "lemma": "kutiy", "gloss": "regresar", "frequency": 1721,
  "is_function_word": false, "is_concrete": false,
  "audio_url": "/media/quy/lexemes/kutiy-3809.ogg", "audio_origin": "synthetic",
  "examples": [
    {"entry_id": 2572, "text": "Kutirqani hinaspam tiyarqani umalliqniy ruray niwaptin",
     "translation": "Regresé y me senté porque mi jefe me dijo que lo hiciera."},
    {"entry_id": 2629, "text": "Sapa kutin Cooperativa de Crétitonniyta watuni",
     "translation": "Visito mi cooperativa de crédito con frecuencia."}
  ]
}
```

Observa: el token era *Kutirqani* y el lema es *kutiy*. Mostrar esa relación (forma → raíz) es
pedagógicamente valioso en una lengua aglutinante. El id devuelto puede diferir del pedido si la
glosa fue corregida (versión vigente).

### Otros

- `GET /entries/{id}` — misma forma que `next`.
- `GET /entries/{id}/history` — cadena de versiones (más reciente primero) para mostrar
  "corregido por la comunidad".

## Puntos de contribución

| Qué señala la persona | Cuerpo de `POST /contributions` |
|---|---|
| Palabra mal transcrita | `{"type": "transcription_fix", "entry_id": 2572, "position": 0, "token": "Kutirqanim"}` |
| Traducción mejorable | `{"type": "translation_fix", "translation_id": 2566, "text": "…"}` |
| Glosa incorrecta (desde el panel) | `{"type": "gloss_fix", "lexeme_id": 3809, "gloss": "volver, regresar"}` |

Errores útiles: `422` "La corrección es idéntica al token actual"; `404` si la frase ya fue
sustituida por otra versión (recárgala). Enviar dos veces lo mismo devuelve la misma contribución.

## Criterios de aceptación

- < 3 s desde abrir la URL hasta escuchar la primera frase con resaltado (tras el primer toque
  si el navegador exige gesto), en celular de gama baja con 4G.
- El resaltado nunca se atrasa perceptiblemente respecto del audio.
- Encadenado sin silencio incómodo entre frases.
- Corregir una palabra: ≤ 3 toques desde que se escucha el error.
- Funciona con pantalla bloqueada / en segundo plano si la plataforma lo permite (Media Session).

## Ideas (no obligatorias)

Modo lectura sin sonido; velocidad de reproducción; repetir frase; "mostrar/ocultar traducción"
para practicar; visualización del avance de la emisora; tocar una palabra y oír solo ese segmento
(tienes `start_ms`/`end_ms`).

---

## Prompt para el agente

```
Construye el módulo Radio de Corpus Vivo sobre la base existente (lee docs/frontend/README.md,
este archivo y DESIGN.md). Radio es la primera impresión de la app: al abrirla, el quechua
suena y la palabra pronunciada se ilumina en su momento exacto, con la traducción debajo.

Tienes libertad creativa total sobre la experiencia: cómo se ve y se siente el resaltado, cómo
se elige una emisora, cómo se revela el significado de una palabra, cómo transmitir que es una
"radio" viva y no una lista de audios. Busca algo memorable y original, que invite a quedarse
escuchando, y que siga el sistema de diseño de la base. Propón primero la idea de interacción
(boceto o descripción) y luego impleméntala.

Obligatorio: criterio de < 3 s, precarga de la siguiente frase, resaltado sincronizado con
start_ms/end_ms, panel de palabra con lema/glosa/audio/ejemplos, y corrección a un toque usando
el patrón "aportar/corregir" de la base. Respeta accesibilidad (el resaltado no puede depender
solo del color; respeta prefers-reduced-motion) y marca con discreción el audio sintético.
Usa únicamente los endpoints documentados; si necesitas algo que la API no da, anótalo en una
sección "Pedidos al backend" en lugar de inventarlo.
```
