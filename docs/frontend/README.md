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

- **Base URL:** `{{API_BASE_URL}}` (se completará al desplegar el entorno de desarrollo).
  Documentación interactiva en `{{API_BASE_URL}}/docs`.
- **Sin servidor disponible:** levanta un mock desde el contrato:
  `npx @stoplight/prism-cli mock docs/frontend/openapi.json` → `http://127.0.0.1:4010`.
  Los ejemplos de cada módulo son respuestas **reales** capturadas del backend.
- **Media:** audio (`.ogg` Opus) e imágenes (`.jpg`) se sirven bajo `/media/...`; las URLs que
  devuelve la API son **relativas**: antepón la base URL. Pueden contener `ñ`: usa `encodeURI`.
- **Lengua:** los endpoints aceptan `?lang=quy` (quechua sureño, por defecto). Aimara (`ayr`)
  llegará más adelante con el mismo contrato: no escribas `quy` fijo en la interfaz.

## 5. Sesión anónima y contribuciones (común a todos los módulos)

Leer no requiere nada. Para **contribuir o revisar** se necesita un token anónimo:

```http
POST /auth/anonymous            → 201
{"contributor_id": "8f171680-…", "token": "RqVHI_39fp…", "reliability": 0.5}
```

Guárdalo (localStorage/IndexedDB) y envíalo como `Authorization: Bearer <token>`. Pídelo de forma
**perezosa**: la primera vez que la persona intenta aportar, no al abrir la app. Si se pierde, se
pide otro (no hay recuperación; es anónimo por diseño).

```http
GET  /auth/me                   → {"id": "…", "reliability": 0.5, "is_native_speaker": false}
PATCH /auth/me {"is_native_speaker": true}      autodeclaración (solo pesa con buen desempeño)
```

**Enviar una contribución** — un único endpoint con `type` discriminado:

```http
POST /contributions             Authorization: Bearer …
{"type": "transcription_fix", "entry_id": 2572, "position": 0, "token": "Kutirqani"}
{"type": "translation_fix",   "translation_id": 2566, "text": "…"}
{"type": "gloss_fix",         "lexeme_id": 3809, "gloss": "volver, regresar"}
{"type": "new_lemma", "lemma": "antawa", "gloss": "auto", "origin_module": "radar"}
{"type": "new_lemma", "lemma": "…", "origin_module": "lente", "vision_label": "cup"}
→ 201
{"id": 245, "type": "transcription_fix", "target_type": "entry", "target_id": 2572,
 "payload": {"position": 0, "original": "Kutirqani", "proposed": "Kutirqanix"},
 "status": "pending", "score": null, "created_at": "2026-09-24T18:28:33Z"}
```

Grabaciones de audio (Lente): `POST /contributions/audio` multipart, ver `03-lente.md`.

`GET /contributions/mine` lista las propias con su `status`: `pending` → `accepted` |
`rejected` | `stale` (aceptada, pero alguien corrigió ese dato antes; no se aplicó) |
`withdrawn` (retirada por revocar consentimiento). Es un buen material para mostrar a la persona
el impacto de lo que aporta.

**Errores:** siempre `{"detail": "mensaje en español"}` (o `detail` como lista en errores de
validación 422 de FastAPI). Códigos: `401` falta/invalid token · `404` no existe o ya fue
sustituido · `409` conflicto (duplicado, ya resuelto) · `422` validación · `503` sin datos.
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
- Glosas del diccionario con errores reales (p. ej. *mayu* aparece como "Mayo, el quinto mes" en
  vez de "río"). No los escondas: son justo lo que la comunidad corregirá.
- ~61 % de las palabras de las frases tienen lema (`lexeme_id`); el resto es `null` y no debe
  abrir el panel de palabra (o debe ofrecer aportar).
