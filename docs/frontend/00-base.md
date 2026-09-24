# 00 — Base: identidad, sistema de diseño y shell

> Lee primero `README.md`. Este agente trabaja **antes** que los de módulo: lo que construyas
> aquí es el suelo sobre el que ellos crean.

## Entregables

1. **Identidad visual** de Corpus Vivo: paleta (claro y oscuro), tipografía (con buen soporte
   de `ñ`, apóstrofos y diacríticos; legible a tamaños pequeños), iconografía, tono de voz de los
   textos de interfaz, tratamiento del movimiento.
2. **Sistema de diseño** como código: tokens (CSS variables / Tailwind theme) y componentes base.
   Mínimo: botón, chip, tarjeta, hoja inferior (bottom sheet), toast, diálogo, estado vacío,
   estado de error, skeleton de carga, barra de progreso de audio.
3. **Shell de la app**: navegación entre los cinco módulos (en móvil, pensada para una mano),
   manejo de rutas, instalación como PWA (manifest, service worker, íconos), modo sin conexión
   digno (al menos: mensaje claro y reintento).
4. **Cliente de API tipado** generado o escrito desde `openapi.json`, con base URL configurable
   (`VITE_API_BASE_URL`), resolución de URLs relativas de `/media`, manejo uniforme de errores
   `{"detail": …}`, y reintento en fallos de red.
5. **Sesión anónima**: obtención perezosa del token (`POST /auth/anonymous`) la primera vez que
   hace falta, persistencia, cabecera `Authorization` automática, recuperación ante `401`
   (pedir uno nuevo y reintentar una vez).
6. **Componentes transversales** que todos los módulos usarán:
   - **Reproductor de audio** (`.ogg` Opus) con estado reproduciendo/pausado/cargando y
     evento de tiempo actual (Radio lo usa para el resaltado; Lente/Radar/Taller para lemas).
     Ojo: Safari iOS antiguo no reproduce Opus en `.ogg`; decide y documenta el fallback.
   - **"Aportar / corregir"**: patrón de un toque que abre una hoja con el dato actual y un campo
     para la propuesta, confirma con feedback claro ("Tu aporte pasará por revisión comunitaria")
     y maneja 401/404/409/422.
   - **Etiqueta de procedencia**: marca discreta para `synthetic` / `model` / `community`.
   - **Texto en quechua**: componente que aplica `lang="qu"` y el estilo tipográfico acordado.
7. **`DESIGN.md`** en el repositorio del frontend: decisiones, tokens, componentes con ejemplos
   de uso, y reglas para los agentes de módulo.

## Endpoints que usa la base

`POST /auth/anonymous`, `GET /auth/me`, `PATCH /auth/me`, `GET /contributions/mine`,
`GET /health`. Ejemplos y errores en `README.md` §5.

Una pantalla de **"Mis aportes"** (lista de `/contributions/mine` con su estado y qué significa
cada uno) es parte de la base: conecta a la persona con el efecto de lo que hace.

## Criterios de aceptación

- Lighthouse móvil: Performance ≥ 90, Accessibility ≥ 95, PWA instalable.
- Primer render útil < 1,5 s en "Slow 4G" emulado; bundle inicial pequeño (divide por módulo).
- Todo componente usable con teclado y lector de pantalla; foco visible.
- Tema claro y oscuro coherentes.

---

## Prompt para el agente

```
Eres responsable de la identidad visual y la base técnica de Corpus Vivo, una PWA que hace
escuchable, explorable y jugable un corpus de quechua, y que permite a su comunidad corregirlo.
Lee docs/frontend/README.md y este archivo; el contrato de la API está en openapi.json.

Tienes libertad creativa real. No queremos una plantilla de dashboard ni un "estilo SaaS"
genérico, ni tampoco un folclorismo de postal. Buscamos una identidad propia, contemporánea y
con carácter, que trate al quechua como lengua viva y protagonista. Antes de escribir código,
propón dos o tres direcciones visuales distintas (paleta, tipografía, una pantalla de ejemplo,
el porqué de cada una), elige una justificándola y documéntala en DESIGN.md.

Restricciones: los principios del README (§2) son obligatorios, en especial rendimiento en
celulares modestos, accesibilidad AA, cero registro para usar, y contribuir a un toque. Stack:
React + Vite + Tailwind, PWA. Construye tokens, componentes base, el shell con navegación entre
Radio, Radar, Lente, Dúo y Taller, el cliente de API tipado, la sesión anónima perezosa, el
reproductor de audio compartido y el patrón "aportar/corregir". Deja cada módulo como una ruta
con una pantalla placeholder bien hecha, para que otros agentes los construyan en paralelo.

Cuando termines, DESIGN.md debe permitir que otro agente construya un módulo nuevo sin
preguntarte nada y que el resultado se sienta parte de la misma app.
```
