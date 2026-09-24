# 02 — Radar

> Lee `README.md` y el `DESIGN.md` de la base antes de empezar.

## Qué es

Un **juego diario**: hay una palabra secreta en quechua, la misma para todas las personas ese
día. Se proponen palabras y el sistema responde **qué tan cerca de significado** están de la
secreta, como percentil: "más cerca que el 94 % del vocabulario". Sin saberlo, quien juega
explora cómo el modelo entiende el quechua. Si propone una palabra que el corpus no tiene, no
es un error: **se le invita a aportarla**.

Detalles que ya resuelve el backend:
- Las formas flexionadas cuentan como su raíz: *wasikunapi* ("en las casas") → *wasi*; un verbo
  conjugado como *maskaspa* → *maskay*. Mostrar esa reducción enseña morfología.
- La palabra secreta cambia a medianoche de Lima (`America/Lima`).
- El estado de la partida (intentos) **no se guarda en el servidor**: guárdalo en el cliente por
  `puzzle_id`.

## Endpoints

### Puzzle del día

```http
GET /radar/today
{"puzzle_id": 2, "lang": "quy", "day": "2026-09-24", "letters": 5, "vocabulary_size": 794,
 "hints": {"top_1": 0.5957, "top_10": 0.5208, "top_100": 0.4255}}
```

`hints` = similitud de la palabra más cercana, de la 10.ª y de la 100.ª: sirve para calibrar
("tu mejor intento está a la altura de la 10.ª más cercana"). `503` si aún no hay vocabulario.

### Intento

```http
POST /radar/guess   {"word": "wasikunapi"}            (opcional: "puzzle_id", "lang")
{"word": "wasikunapi", "known": true, "lemma": "wasi", "gloss": "casa", "lexeme_id": 4383,
 "rank": 234, "percentile": 70.6, "similarity": 0.3652, "solved": false,
 "can_contribute": false, "suggestion": null}
```

Palabra desconocida:

```json
{"word": "antawa", "known": false, "lemma": null, "gloss": null, "lexeme_id": null,
 "rank": null, "percentile": null, "similarity": null, "solved": false,
 "can_contribute": true,
 "suggestion": {"type": "new_lemma", "lang": "quy", "lemma": "antawa", "origin_module": "radar"}}
```

`suggestion` es el cuerpo **listo** para `POST /contributions` (agrega `gloss` si la persona la
escribe). Más de una palabra → `422 {"detail": "Propón una sola palabra"}`.

`solved: true` cuando `rank == 1`. `percentile` 100 = la secreta.

### Rendirse / respuesta

```http
GET /radar/puzzles/{puzzle_id}/answer              → 403 si es el de hoy
GET /radar/puzzles/{puzzle_id}/answer?give_up=true
{"puzzle_id": 2, "day": "2026-09-24", "lemma": "samay", "gloss": "Aliento", "lexeme_id": 4185,
 "neighbors": [
   {"lemma": "kamay",   "gloss": "Crear",   "rank": 2, "percentile": 99.9, "similarity": 0.5957},
   {"lemma": "samariy", "gloss": "Reposar", "rank": 3, "percentile": 99.7, "similarity": 0.5938},
   {"lemma": "asnu",    "gloss": "burro",   "rank": 4, "percentile": 99.6, "similarity": 0.5667}
 ]}
```

Al revelar: sus 10 vecinos más cercanos y su pronunciación (`GET /lexemes/{lexeme_id}` trae
`audio_url`). Puzzles pasados pueden jugarse enviando `puzzle_id` en `/radar/guess`.

## Puntos de contribución

| Situación | Acción |
|---|---|
| Palabra no encontrada | `POST /contributions` con `suggestion` (+ `gloss` opcional) |
| Glosa que no corresponde (en un intento o al revelar) | `{"type": "gloss_fix", "lexeme_id": …, "gloss": "…"}` |

## Honestidad sobre la calidad

Los vectores actuales vienen de un corpus pequeño y mayormente religioso: algunos días los
vecinos son muy buenos (*pichqa* "cinco" → otros números) y otros ruidosos. Algunas glosas del
diccionario son erróneas. La interfaz no debe prometer precisión que no hay; los errores visibles
son oportunidades de contribución.

## Criterios de aceptación

- Un intento se responde en < 300 ms percibidos (optimista: muestra el intento de inmediato).
- Historial ordenable por cercanía y por orden de intento; la reducción a raíz visible.
- Partida persistente al recargar (localStorage por `puzzle_id`); racha diaria local.
- Compartir resultado sin revelar la palabra (texto/emoji, estilo Wordle).

---

## Prompt para el agente

```
Construye el módulo Radar de Corpus Vivo sobre la base existente (lee docs/frontend/README.md,
este archivo y DESIGN.md). Radar es un juego diario de adivinanza por cercanía de significado:
cada intento revela qué tan cerca está de la palabra secreta en quechua.

Tienes libertad creativa total: la metáfora visual del "radar" (o cualquier otra mejor), cómo se
representa la cercanía, cómo se siente acercarse, cómo se celebra acertar, cómo se comparte.
Queremos un juego al que den ganas de volver cada día y que, de paso, enseñe vocabulario y
morfología (muestra cómo "wasikunapi" se reduce a "wasi"). Propón primero la mecánica visual y
luego impleméntala con el sistema de diseño de la base.

Obligatorio: una sola palabra por intento, estado de la partida persistido en el cliente por
puzzle_id, rendirse con revelación de vecinos y pronunciación, y convertir "palabra desconocida"
en una invitación a aportarla (usa `suggestion` tal cual). Accesible: la cercanía no puede
comunicarse solo con color. Usa solo los endpoints documentados; lo que falte, a
"Pedidos al backend".
```
