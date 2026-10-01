# Corpus Vivo — guía para agentes de frontend

Este directorio es el contexto completo para construir la interfaz (web PWA y/o móvil) de
**Corpus Vivo**. El backend ya existe y está probado; tu trabajo es la experiencia de usuario.

| Archivo | Para quién |
|---|---|
| `README.md` (este) | Todos los agentes: producto, API común, reglas, orden de trabajo |
| `00-base.md` | Agente de base: identidad visual, sistema de diseño, shell, cliente de API, sesión |
| `01-radio.md` | Agente del módulo Radio |
| `02-radar.md` | Agente del módulo Radar |
| `03-lente.md` | Agente del módulo Lente |
| `04-duo.md` | Agente del módulo Dúo |
| `05-taller.md` | Agente del módulo Taller |
| `openapi.json` | Contrato exacto de la API (OpenAPI 3.1, generado del backend) |

## 1. El producto en una página

Los corpus de lenguas indígenas existen, pero solo los puede usar quien sabe programar: son
archivos comprimidos de varios gigabytes. **Corpus Vivo convierte un corpus de quechua en algo
que se escucha, se recorre y se juega desde el navegador**, sin instalar nada ni registrarse. Y
cada uso puede mejorar el corpus: quien escucha un error lo corrige, quien no encuentra una palabra
la aporta, y la comunidad valida esos aportes por consenso.

Cinco módulos sobre el mismo corpus:

| Módulo | Qué es | Qué aporta al corpus |
|---|---|---|
| **Radio** | Reproducción continua: audio + transcripción resaltada palabra a palabra + traducción | Corrección de transcripción y de traducción |
| **Radar** | Juego diario: adivinar la palabra secreta por cercanía de significado | Palabras que faltan, glosas corregidas |
| **Lente** | La cámara reconoce objetos y muestra/pronuncia su nombre en quechua | Palabras para objetos sin nombre, grabaciones de pronunciación |
| **Dúo** | Dos personas: una describe una imagen en quechua, la otra la identifica entre cuatro | Frases espontáneas (el dato más escaso) |
| **Taller** | Bandeja donde la comunidad revisa los aportes: aceptar, rechazar o "no estoy seguro" | Cierra el ciclo: decide qué entra al corpus |

Público: hablantes de quechua, estudiantes que lo aprenden, docentes. Muchos usarán **celulares
modestos con datos móviles** en Puno y el sur andino. Diseña para ellos.

## 2. Principios no negociables

Vienen del documento técnico del proyecto; no son decoraciones.

1. **Cero fricción de entrada.** Nada de registro ni login para usar. Radio debe sonar con su
   transcripción sincronizada **en menos de 3 segundos** desde que se abre la dirección.
2. **Contribuir está a un toque.** El control para corregir o aportar vive dentro de cada módulo,
   junto al dato. Nunca un formulario aparte.
3. **La revisión es participación**, no una tarea administrativa: el Taller es un modo de uso
   legítimo y debe sentirse así.
4. **Privacidad.** En Lente ninguna imagen sale del dispositivo (la clasificación corre en el
   navegador). En Dúo la captura de texto exige **consentimiento explícito, informado y revocable**.
5. **Honestidad con el dato.** Si algo es sintético o automático, dilo: el audio actual es voz
   sintética (`audio_origin: "synthetic"`), algunas traducciones pueden venir de un modelo
   (`origin: "model"`). Muéstralo con discreción, pero muéstralo.
6. **Respeto cultural.** El quechua es una lengua viva, no un adorno. Evita el folclorismo de
   catálogo (patrones "étnicos" genéricos, llamas de caricatura, tipografías "incas"). Si usas
   referencias visuales andinas, que sean específicas, con sentido y bien hechas; en caso de duda,
   menos es más. El español acompaña; el quechua es protagonista.
7. **Accesible y liviano.** Contraste AA, objetivos táctiles ≥ 44 px, funciona con lector de
   pantalla, respeta `prefers-reduced-motion`, carga rápida en 3G. Interfaz en español; el
   contenido en quechua siempre con `lang="qu"`.

## 3. Stack

El documento técnico fija: **React + Vite**, **Tailwind CSS**, **PWA** (Lente la necesita),
**TensorFlow.js** para visión en el cliente, **WebSocket** para Dúo. Si trabajas en móvil nativo,
consúmelo igual: la API es la misma. El agente de base decide librerías adicionales (router,
estado, animación, iconos) y las documenta para los demás.

## 4. Cómo acceder a la API

- **Base URL (desarrollo):** `https://commerce-bras-title-holland.trycloudflare.com`
  Documentación interactiva en `…/docs`, contrato en `…/openapi.json`.
  > **Es un túnel temporal**: la URL cambia si se reinicia y solo responde mientras el equipo
  > que la sirve está encendido. Nunca la escribas en el código: léela de `VITE_API_BASE_URL`.
  > Si no responde, trabaja contra el mock de abajo y avisa al equipo de backend.
  > La base de datos es compartida: lo que envíes (aportes, revisiones, salas) lo ven los demás.
- **Sin servidor disponible:** levanta un mock desde el contrato:
  `npx @stoplight/prism-cli mock docs/frontend/openapi.json` → `http://127.0.0.1:4010`.
  Los ejemplos de cada módulo son respuestas **reales** capturadas del backend.
- **Media:** audio (`.ogg` Opus) e imágenes (`.jpg`) se sirven bajo `/media/...`; las URLs que
  devuelve la API son **relativas**: antepón la base URL. Pueden contener `ñ`: usa `encodeURI`.
- **WebSocket (Dúo):** misma base con `wss://` en lugar de `https://`.
- **Latencia:** en este entorno cada petición tarda ~1 s (servidor en Perú, base de datos en
  EE. UU.). Diseña estados de carga reales y precarga; no es un error de tu parte.
- **Lengua:** los endpoints aceptan `?lang=quy` (quechua sureño, por defecto). Aimara (`ayr`)
  llegará más adelante con el mismo contrato: no escribas `quy` fijo en la interfaz.
  `GET /languages` lista las lenguas con datos y qué módulos están disponibles en cada una:
  ```json
  [{"code": "quy", "name": "Quechua sureño (chanka)", "endonym": "Runasimi", "iso639_1": "qu",
    "default": true,
    "counts": {"entries": 855, "lexemes": 1187, "vision_labels_mapped": 17, "duo_images": 155, "topics": 8},
    "modules": {"radio": true, "radar": true, "lente": true, "duo": true, "taller": true}}]
  ```
- **Audio en iPhone:** todo audio viene en dos formatos: `audio_url` (Ogg/Opus, más liviano) y
  `audio_url_m4a` (AAC). Elige con `audio.canPlayType('audio/ogg; codecs="opus"')`; las versiones
  antiguas de iOS no reproducen Opus en Ogg. Aplica también en Taller (`original_m4a`, `proposed_m4a`).
- **Límite de peticiones:** si se excede, la API responde `429` con cabecera `Retry-After`
  (segundos). Reintenta después de ese tiempo; nunca en bucle inmediato. Límites por cliente:
  sesiones 10/min, aportes 30/min, revisiones y Radar 60/min, eventos 60/min, general 600/min.

## 4.1 Instrumentación (obligatoria)

La evaluación del proyecto (§12 del documento técnico) mide el uso real. El cliente debe:

1. Generar al primer arranque un **id de dispositivo aleatorio** (p. ej. `crypto.randomUUID()`),
   guardarlo en localStorage y enviarlo en **todas** las peticiones como `X-Device-Id`.
   Un id de sesión nuevo por visita va en `X-Session-Id`. Ninguno contiene datos personales.
2. Indicar el módulo activo con `X-Module: radio|radar|lente|duo|taller` al contribuir (una glosa
   se puede corregir desde Radio o desde Radar y el servidor no puede distinguirlo).
3. En Dúo, pasar el id en el WebSocket: `…/duo/ws/{code}?token=…&device_id=…`.
4. Enviar los eventos que solo el cliente conoce, en lotes (máx. 50, `props` ≤ 2 KB):

```http
POST /events        X-Device-Id: 3f1c…   X-Session-Id: 9a2e…
{"events": [
  {"name": "app.open", "module": "app"},
  {"name": "radio.first_play", "module": "radio", "props": {"ms": 2140}}
]}
→ 202 {"accepted": 2}
```

**Imprescindible:** `radio.first_play` con `props.ms` = milisegundos desde que se abrió la página
hasta que empezó a sonar la primera frase. Es el indicador principal del proyecto ("tiempo hasta
el primer dato útil"). Otros nombres son libres (`^[a-z][a-z0-9_.]{1,63}$`, estilo
`modulo.accion`). El servidor ya registra por su cuenta sesiones, aportes, revisiones, intentos de
Radar y rondas de Dúo: no los dupliques.

`GET /metrics?days=30` devuelve los agregados (útil para un panel del equipo, no para usuarios):
tiempo hasta la primera frase (mediana, p90), dispositivos activos por día, sesiones, retención a 7
días y proporción de dispositivos que aportan.

## 5. Sesión anónima y contribuciones (común a todos los módulos)

Leer no requiere nada. Para **contribuir o revisar** se necesita un token anónimo:

```http
POST /auth/anonymous            → 201
{"contributor_id": "8f171680-…", "token": "RqVHI_39fp…", "reliability": 0.5}
```

Guárdalo (localStorage/IndexedDB) y envíalo como `Authorization: Bearer <token>`. Pídelo de forma
**perezosa**: la primera vez que la persona intenta aportar, no al abrir la app.

**Usar la misma identidad en otro dispositivo** (conserva confiabilidad y aportes; sin correo):

```http
POST /auth/link-code     (dispositivo A, con token)  → 201 {"code": "K7QM2XPA", "expires_at": "…"}
POST /auth/link  {"code": "k7qm-2xpa"}   (dispositivo B, sin token)
→ {"contributor_id": "<el mismo de A>", "token": "<token nuevo para B>", "reliability": 0.62}
```

El código dura 10 minutos, sirve una sola vez y admite minúsculas, espacios y guiones.
Error `400` si es inválido, vencido o ya usado. Si se pierde el token sin haber vinculado otro
dispositivo, no hay recuperación: es anónimo por diseño.

```http
GET  /auth/me                   → {"id": "…", "reliability": 0.5, "is_native_speaker": false}
PATCH /auth/me {"is_native_speaker": true}      autodeclaración (solo pesa con buen desempeño)
```

**Enviar una contribución** — un único endpoint con `type` discriminado:

```http
POST /contributions             Authorization: Bearer …
{"type": "transcription_fix", "entry_id": 2572, "position": 0, "token": "Kutirqanim"}
{"type": "translation_fix",   "translation_id": 2566, "text": "…"}
{"type": "gloss_fix",         "lexeme_id": 3809, "gloss": "volver, regresar"}
{"type": "new_lemma", "lemma": "antawa", "gloss": "auto", "origin_module": "radar"}
{"type": "new_lemma", "lemma": "…", "origin_module": "lente", "vision_label": "cup"}
→ 201
{"id": 245, "type": "transcription_fix", "target_type": "entry", "target_id": 2572,
 "payload": {"position": 0, "original": "Kutirqani", "proposed": "Kutirqanim"},
 "status": "pending", "score": null, "created_at": "2026-09-24T18:28:33Z"}
```

Grabaciones de audio (Lente): `POST /contributions/audio` multipart, ver `03-lente.md`.

`GET /contributions/mine` lista las propias con su `status`: `pending` → `accepted` |
`rejected` | `stale` (aceptada, pero alguien corrigió ese dato antes; no se aplicó) |
`withdrawn` (retirada por revocar consentimiento). Es un buen material para mostrar a la persona
el impacto de lo que aporta.

**Buscar en el vocabulario** (autocompletar, diccionario, Lente sin cámara):

```http
GET /lexemes?q=wasikunapi          → [{"lemma": "wasi", "gloss": "casa", "audio_url": …, "audio_url_m4a": …}]
GET /lexemes?q=perro               → [{"lemma": "allqu", "gloss": "perro", …}, {"lemma": "allquy", "gloss": "Mi perro", …}]
GET /lexemes?q=yak&limit=5         → yaku (agua), yakunayay (sed), …
GET /lexemes?q=gato&concrete=true  → solo lemas asociados a objetos de Lente
```

Acepta quechua (lema, prefijo o forma flexionada) o español (glosa, sin importar tildes).

**Errores:** siempre `{"detail": "mensaje en español"}` (o `detail` como lista en errores de
validación 422 de FastAPI). Códigos: `400` código de vinculación inválido · `401` falta o no
es válido el token · `404` no existe o ya fue sustituido · `409` conflicto (duplicado, ya
resuelto, sala cerrada) · `422` validación · `429` demasiadas solicitudes · `503` sin datos.
Los mensajes son aptos para mostrarse, pero puedes reescribirlos.

**Versionado:** el corpus nunca se sobrescribe. Una corrección aprobada crea una versión nueva
(`supersedes_id` apunta a la anterior). Los ids que tengas pueden quedar "viejos": los endpoints
de lectura resuelven a la versión vigente; los de contribución responden `404` si el destino ya
fue sustituido → recarga el dato.

## 6. Orden de trabajo sugerido

1. **Agente de base** (`00-base.md`): identidad visual, sistema de diseño, shell y navegación,
   cliente de API tipado, sesión anónima, reproductor de audio compartido, componente
   "aportar/corregir". Publica un `DESIGN.md` con decisiones y componentes.
2. **Agentes de módulo en paralelo** (`01`–`05`), cada uno sobre la base. Libertad creativa total
   en la experiencia de su módulo, coherencia con el sistema de diseño.
3. Revisión cruzada: recorrer la app completa en un celular real de gama baja.

## 7. Estado del contenido (para no sorprenderse)

- 855 frases de quechua con traducción; **audio sintético** (TTS) mientras llega el corpus real.
- Los temas de Radio salen de un agrupamiento automático y son aproximados: algunos son
  temáticos ("Dinero y donaciones") y otros reúnen frases por estilo ("Charlas informales").
- Glosas del diccionario con errores reales (p. ej. *mayu* aparece como "Mayo, el quinto mes" en
  vez de "río"). No los escondas: son justo lo que la comunidad corregirá.
- ~61 % de las palabras de las frases tienen lema (`lexeme_id`); el resto es `null` y no debe
  abrir el panel de palabra (o debe ofrecer aportar).
