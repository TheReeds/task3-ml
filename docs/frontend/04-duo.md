# 04 — Dúo

> Lee `README.md` y el `DESIGN.md` de la base antes de empezar.

## Qué es

Un juego **para dos personas** conectadas por un código de sala. Por turnos, una recibe una
imagen y la **describe en quechua**; la otra ve cuatro imágenes y elige la descrita. **Ganan o
pierden juntas.** Los roles se alternan cada ronda. Un panel de pistas sugiere palabras del
corpus relacionadas con la imagen para quien describe.

Es el módulo más valioso para el corpus: cada ronda produce una frase espontánea con intención
comunicativa real, el dato más escaso en lenguas de pocos recursos. Por eso mismo, **la captura
exige consentimiento explícito, informado y revocable** de quien describe.

El servidor ajusta la dificultad sola (qué tan parecidas son las imágenes distractoras) para
que las parejas acierten ~65 % de las veces: ni trivial ni frustrante.

## Flujo

```
A: POST /duo/rooms → código "XV4FWR"  ──comparte el código──▶  B: POST /duo/rooms/XV4FWR/join
A y B: abren WebSocket /duo/ws/XV4FWR?token=…
Cualquiera: start_round
  descriptor ve imagen + pistas        adivinador espera
  descriptor: describe "Kayqa …"
  descriptor sigue viendo su imagen    adivinador ve la descripción + 4 opciones
                                       adivinador: guess image_id
  ambos ven el resultado (acierto/fallo, imagen correcta y su concepto)
Cualquiera: start_round → roles invertidos
```

## REST

```http
POST /duo/rooms                     (auth)   → 201 {"code": "XV4FWR", "seat": 0}
POST /duo/rooms/{code}/join         (auth)   → {"code": "XV4FWR", "seat": 1}   (reconectar = mismo resultado)
GET  /duo/rooms/{code}              (auth)   → mismo objeto "state" que el WebSocket
PUT  /duo/rooms/{code}/consent      (auth)   {"consent": true|false}
POST /duo/rooms/{code}/leave        (auth)   → {"code": "XV4FWR", "status": "closed"}
```

Errores: `404` sala inexistente · `409` sala llena o cerrada · `403` no participas en la sala.

**Ciclo de vida:** salir cierra la sala **para ambos** (el juego es de a dos; lo capturado se
conserva). Una sala sin actividad durante **2 horas** se cierra sola. Con la sala cerrada
(`room.status: "closed"`) toda acción responde `409 "La sala está cerrada"`: ofrece crear otra.

## WebSocket `/duo/ws/{code}?token=<token anónimo>&device_id=<X-Device-Id>`

Si el token no es de un participante, se cierra con código `4403` (o `4401`/`4404`).

**Cliente → servidor**

```json
{"action": "start_round"}
{"action": "describe", "text": "Kayqa hatun uywa"}
{"action": "guess", "image_id": 386}
{"action": "consent", "value": true}
{"action": "skip"}     el descriptor pasa una imagen que no sabe describir
{"action": "leave"}    cierra la sala para ambos
```

**Pasar (`skip`)**: solo el descriptor y solo antes de describir. La ronda termina sin contar
como fallo, la dificultad no cambia y **la misma persona describe** en la siguiente ronda.

**Servidor → cliente**: tras **cada** cambio (incluida la conexión/desconexión del otro), cada
participante recibe **su** vista completa. Renderiza desde ella; no reconstruyas estado a mano.

```json
{"type": "state",
 "room": {"code": "XV4FWR", "lang": "quy", "status": "ready", "score": 0, "rounds_played": 0},
 "you": {"seat": 0, "consent": false},
 "players": [{"seat": 0, "connected": true, "consent": false},
             {"seat": 1, "connected": true, "consent": false}],
 "round": {"number": 1, "phase": "describing", "role": "describer", "difficulty": 0.4,
   "image": {"id": 386, "url": "/media/duo/mayu-bdc4cec162.jpg",
             "attribution": {"author": "Boletín de la Sociedad Geográfica de Lima",
                             "license": "Public domain",
                             "source": "https://commons.wikimedia.org/wiki/File:…"}},
   "hints": [{"lemma": "mayu", "gloss": "Mayo, el quinto mes"}, {"lemma": "chimpa", "gloss": "al otro lado"},
             {"lemma": "pukyu", "gloss": "Manantial"}, {"lemma": "qucha", "gloss": "Lago"}]}}
```

Vista del adivinador al pasar a `guessing` (las opciones **no** revelan su concepto):

```json
"round": {"number": 1, "phase": "guessing", "role": "guesser", "difficulty": 0.4,
  "description": "Kayqa sumaq",
  "options": [{"id": 386, "url": "/media/duo/mayu-bdc4cec162.jpg", "attribution": {…}},
              {"id": 363, "url": "/media/duo/ñan-f6be502d9f.jpg", "attribution": {…}}, …]}
```

Al terminar (`done`), ambos reciben:

```json
"round": {"number": 1, "phase": "done", "role": "describer", "description": "Kayqa sumaq",
  "result": {"success": true, "chosen_image_id": 386,
             "target": {"id": 386, "url": "…", "attribution": {…},
                        "concept_lemma": "mayu", "concept_es": "río"}}}
```

`result` incluye `"skipped": true|false`; si se pasó, `success` es `null`.
`rounds_played` no cuenta las rondas pasadas.

`round: null` = aún no empezó ninguna ronda. `room.status`: `waiting` (falta la otra persona) ·
`ready` · `closed`. `players[].connected` permite mostrar "tu compañero se desconectó".

Errores de acción (no cierran la conexión):

```json
{"type": "error", "status": 409, "detail": "No hay una imagen esperando descripción"}
{"type": "error", "status": 403, "detail": "En esta ronda te toca adivinar"}
{"type": "error", "status": 422, "detail": "Describe la imagen en la lengua, sin nombrarla en español"}
```

Descripción: 1–280 caracteres; nombrar el concepto en español se rechaza.

## Consentimiento y atribución

- Pide el consentimiento **al entrar a la sala**, explicando qué se guarda (solo las
  descripciones de quien consiente, para revisión comunitaria y publicación abierta con
  seudónimo) y que puede revocarse en cualquier momento. Sin consentimiento se juega igual.
- Revocar (`consent: false`) retira y borra los textos ya capturados de esa persona en la sala.
- Las imágenes son de Wikimedia Commons con licencias libres: **muestra autor y licencia** con
  enlace a `source` (puede ser discreto, p. ej. un botón "ⓘ" sobre la imagen). Es obligatorio.

## Notas

- Las glosas de las pistas pueden tener errores del diccionario (mira *mayu*); están ahí para
  ayudar, no como verdad.
- Reconexión: si se cae el socket, reabre con el mismo token; `join` es idempotente.
- Un solo servidor: si en el futuro hay varios, el backend cambiará el transporte, no el
  protocolo.

## Criterios de aceptación

- Entrar a una sala compartiendo un enlace o un código de 6 caracteres fácil de dictar.
- Estados claros: esperando compañero, tu turno de describir, esperando descripción, elige,
  resultado. Nunca una pantalla sin saber qué hacer.
- Funciona con conexiones inestables (reconexión automática, estados de "reconectando").
- Consentimiento explícito, visible y revocable desde la sala.

---

## Prompt para el agente

```
Construye el módulo Dúo de Corpus Vivo sobre la base existente (lee docs/frontend/README.md,
este archivo y DESIGN.md). Dúo es un juego cooperativo para dos personas en tiempo real: una
describe en quechua una imagen, la otra la elige entre cuatro; ganan o pierden juntas y se
turnan.

Tienes libertad creativa total sobre la experiencia social: cómo se invita a alguien, cómo se
siente jugar "juntos" aunque estén lejos, cómo se vive la espera del otro, cómo se celebra el
acierto compartido, cómo se usa el panel de pistas sin que se convierta en trampa. Queremos que
dé ganas de jugar con un amigo o en clase. Propón primero la experiencia y luego impleméntala
con el sistema de diseño de la base.

No negociable: consentimiento explícito, informado y revocable antes de capturar descripciones;
atribución visible de las imágenes (autor, licencia, enlace); renderizar siempre desde el
mensaje "state" del servidor; reconexión robusta. Usa solo los endpoints y mensajes
documentados; lo que falte, a "Pedidos al backend".
```
