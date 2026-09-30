# Corpus Vivo — frontend

React + Vite + TypeScript + Tailwind v4. Contexto y contrato: `../docs/frontend/`.

```sh
pnpm install
pnpm dev          # http://localhost:5173 — usa VITE_API_BASE_URL de .env.development (API local :7860)
pnpm build && pnpm lint
```

Para usar el túnel (o probar desde un celular en la red local, donde `127.0.0.1` no sirve), crea
`.env.development.local` con `VITE_API_BASE_URL=<url del túnel>`.

## Estructura

| Ruta | Qué hay |
|---|---|
| `src/lib/api.ts` | Cliente: base URL, `X-Device-Id`/`X-Session-Id`/`X-Module`, token anónimo perezoso con reintento ante 401, `429` con `Retry-After`, reintento de red en GET, `mediaUrl`, `pickAudio` (Opus/AAC) |
| `src/lib/events.ts` | Cola de eventos → `POST /events` en lotes; `fetch keepalive` al ocultarse la página |
| `src/contribute/` | `CorrectForm`: patrón aportar/corregir compartido (transcripción, traducción, glosa, palabra nueva) |
| `src/lib/morph.ts` | Forma → raíz (`splitStem`) |
| `src/ui/` | `Sheet` (hoja inferior sobre `<dialog>`), `toast`, `Qu` (texto en quechua), `Provenance`, `Icon` |
| `src/radio/` | Módulo Radio (abajo) |

Tokens de diseño en `src/index.css`: tinta cálida de noche / papel de día; tipografías Fraunces
(quechua, protagonista) y Atkinson Hyperlegible (interfaz). El acento `--tint` cambia por familia
de emisora: grana de cochinilla (Todo), maíz (Nivel), crisocola (Temas).

## Radio

- **Encendido:** al abrir se piden en paralelo las emisoras y la primera frase (con su audio
  descargado a un blob). Si el navegador permite autoplay, suena sola; si no, el botón "respira"
  y el primer toque *enciende la radio* (el fondo se expande, las palabras se iluminan).
  `radio.first_play` envía `ms` (desde la navegación) y `gesture_ms` (cuándo se tocó).
- **Resaltado:** bucle `requestAnimationFrame` sobre `audio.currentTime`. Estados de palabra:
  futura (atenuada), activa (color + subrayado que se llena al ritmo de la palabra + leve
  elevación), dicha (plena, subrayado tenue). En los silencios queda "dicha" la última.
- **Encadenado:** mientras suena una frase se descarga la siguiente (JSON + audio en blob);
  entre frases hay un respiro de 650 ms con animación de entrada palabra a palabra.
- **Dial:** banda de sintonía con "frecuencias" decorativas agrupadas por familia (prefijo del id).
  Al cambiar de emisora: aguja buscando, estática visual y un leve ruido (Web Audio).
- **Visualizador:** espectro real con `AnalyserNode` (el blob evita problemas de CORS). En iOS no se
  usa Web Audio (silenciaría el audio con la pantalla bloqueada) y la onda se aproxima.
- **Panel de palabra:** tocar pausa; muestra forma → raíz (*kuti*rqani ← *kuti*y), glosa,
  frecuencia, audio del lema, oír solo ese tramo de la frase y ejemplos que se pueden escuchar.
  Al cerrar, retoma donde iba.
- **Corregir (≤ 3 toques):** palabra → "Está mal escrita" → Enviar. También glosa y traducción.
  `404` recarga la versión vigente de la frase sin cortar el audio.
- Media Session (pantalla bloqueada / auriculares), velocidad 0,75×, bucle, traducción oculta
  para practicar, `prefers-reduced-motion` (sin desplazamientos; el resaltado se mantiene).

## Radar

Fragmento aparte (`React.lazy`), acento crisocola.

- **Pantalla de radar:** la secreta en el centro (sus letras como guiones); cada intento es un
  punto a distancia logarítmica según su puesto (anillos top 10 / top 100) y en un ángulo fijo
  por palabra (hash FNV-1a: la misma palabra cae en el mismo sitio para todos). Un barrido gira
  y hace "ping" a cada punto al pasar (los retrasos se calculan con el mismo reloj que el barrido).
- **Optimista:** el intento aparece al instante y el radar pulsa mientras llega la respuesta (~1 s).
- **Cercanía nunca solo por color:** etiqueta (Lejos · Tibio · Cerca · Muy cerca · Ardiendo), puesto,
  percentil en texto, barra y posición.
- **Morfología:** *wasi*kunapi → wasi en la tarjeta y el historial; si una forma nueva se reduce a
  una raíz ya probada, se avisa y no cuenta como intento.
- **Palabra desconocida:** invitación a aportarla con `suggestion` tal cual (+ glosa opcional).
- Historial ordenable (cercanía / orden), corrección de glosa en cada fila y al revelar.
- Rendirse (confirmación de dos toques) → vecinas en el radar como puntos huecos + lista, y
  pronunciación. Al acertar se piden las vecinas con `give_up=true` (el servidor no lo registra).
- Archivo de 7 días con estado (· en curso, ✓ resuelto, ⚑ rendido); partida por `puzzle_id` en
  localStorage; racha = días resueltos el mismo día; compartir con emojis sin revelar la palabra.
- Autocompletar (`/lexemes?q=`) no se usa a propósito: le quitaría gracia al juego.

## Dúo

Fragmento aparte, acento maíz. Rutas `#/duo` (vestíbulo) y `#/duo/CÓDIGO` (entrar por enlace).

- **Invitar:** código de 6 caracteres en dos grupos para dictar (`XV4 · FWR`), enlace para
  compartir (`navigator.share` o portapapeles) y QR dibujado con `currentColor` (para clase).
- **Juntas aunque lejos:** las dos personas unidas por una cuerda; sólida con un pulso cuando
  ambas están conectadas, punteada si alguien se cae. Debajo, el **khipu** de la sesión: cada
  acierto ata un nudo, cada fallo deja una cuerda suelta.
- **Estados claros:** esperando pareja → listas → describes / esperas la descripción → eliges /
  tu pareja elige → resultado (con "Elegiste" si fallaste). Todo se dibuja desde el último
  `state` del servidor; solo se guardan aparte las opciones de la ronda (el `result` no las trae)
  y el orden de aciertos para el khipu.
- **Pistas sin trampa:** plegadas en "¿Te falta una palabra?" (la primera es la palabra misma).
- **Consentimiento:** hoja al entrar (una vez por sala) con qué se guarda, para qué y cómo
  revocarlo; siempre visible en la sala; revocar avisa que se borran las frases dadas. Si el
  socket está caído, se envía por REST.
- **Reconexión:** `join` idempotente + WebSocket; reintento con espera creciente (hasta 15 s),
  inmediato al volver la red o la pestaña; el evento `offline` cierra el socket para no quedar
  "medio abierto". `4403`/`4404` y `409` al entrar muestran un error con salida.
- Salir pide dos toques ("¿Cerrar para ambos?"). Sala cerrada → resumen y "Crear otra sala".

Probado con dos navegadores reales jugando juntos: crear/entrar por enlace, ronda acertada y
fallada, pasar (la misma persona vuelve a describir), corte de red y vuelta, revocar, cerrar.

## Taller

Fragmento aparte, acento añil (validado con el script de `dataviz`: `#3d4a9e` claro, `#7c8ae8`
oscuro). Pestañas **Revisar · Impacto · Tus aportes**.

- **Revisar de a una**, con el contexto justo por tipo: tramo exacto de audio en escritura (se
  detiene solo al final de la palabra), frase + audio en traducción, ejemplos en significado,
  imagen en frases de Dúo, audio actual vs. grabación en pronunciación. La diferencia se resalta
  por letras o por palabras (tachado/subrayado, no solo color; una barra marca dónde se quitó o
  agregó algo).
- **Tres botones idénticos** (Rechazar · No estoy seguro · Aceptar), fijos abajo, con atajos
  `R`/`N`/`A`. La tarjeta sale y entra la siguiente. Nunca se muestra ni se infiere qué ítems son
  de control; la identidad de quien propuso no aparece (solo "confiabilidad baja/media/alta").
- **Retroalimentación honesta:** "Anotado, faltan opiniones" / "No suma ni resta" / "¡Con tu
  voto se aceptó!" (cuando `status` cambia). **Tu tramo de hoy**: un hilo por revisión, todos del
  mismo color (importa cuidar, no el veredicto).
- Filtros por tipo (se recuerdan). Estado vacío (`204`) positivo con salidas a Radio/Impacto.
- **Confiabilidad** explicada en una hoja, sin ranking; autodeclaración de hablante nativo con
  la advertencia de que solo pesa si además se acierta.
- **Impacto:** cifra principal (aportes aceptados), tarjetas, acuerdo entre revisores (Fleiss κ
  en palabras), tres gráficos de columnas de una serie (tooltip por barra, valor en el pico, tabla
  equivalente), aceptados por tipo, exportación CSV/JSONL a un toque.
- **Tus aportes:** `/contributions/mine` con cada estado explicado.

Probado en navegador con los juicios **interceptados** (nunca se envió un juicio real a la base
compartida); los tipos sin datos reales y el impacto con datos se probaron con respuestas simuladas.

## Pedidos al backend

- `GET /health` no respondió en 20 s en la API local (`:7860`); el resto de endpoints sí.
- La primera petición a veces tarda hasta ~7 s (base de datos remota): afecta el objetivo de < 3 s.
  Un `GET /radio/boot` que devuelva emisoras + primera frase en una sola llamada ayudaría.
- En emisoras ordenadas no hay posición/total de la frase, así que no se puede dibujar el avance
  dentro de la emisora.
- Radar: tras acertar hoy, las vecinas solo se obtienen con `give_up=true`. Un
  `GET /radar/puzzles/{id}/answer?solved_with=<palabra>` (o aceptar la respuesta correcta) sería
  más limpio si algún día se registran las rendiciones.
- Radar: `/radar/puzzles` no incluye `vocabulary_size`; se usa el de hoy para los días anteriores.
- Dúo: no hay `ping`/latido. El túnel de Cloudflare corta sockets inactivos (~100 s) y en redes
  móviles un socket puede quedar medio abierto sin que el navegador lo sepa. Pedido: aceptar
  `{"action": "ping"}` → `{"type": "pong"}` (o pings de protocolo desde el servidor).
- Dúo: en `done`, `result` trae solo `chosen_image_id`; incluir la imagen elegida evitaría
  guardar las opciones en el cliente para mostrar "Elegiste".
- Dúo: no hay historial de rondas en `state`; el khipu reconstruye el orden en el dispositivo
  (tras recargar en otro equipo solo se conocen los totales).
- Taller: `/taller/impact` devuelve todo en cero aunque hay ítems pendientes servidos por
  `/taller/next` (probablemente porque hoy solo hay elementos de control, que no cuentan). Si es
  así, está bien; si no, revisar.
- Taller: la cabecera `X-License-Note` de la exportación no se puede leer desde el navegador
  (falta `Access-Control-Expose-Headers`); la nota de licencia se muestra como texto fijo.
- Taller: no hay forma de "pasar" un ítem sin juzgarlo; `/taller/next` devuelve el mismo hasta
  emitir un juicio. "No estoy seguro" cumple ese papel, pero conviene confirmarlo como diseño.
