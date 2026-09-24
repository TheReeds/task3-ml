# 03 — Lente

> Lee `README.md` y el `DESIGN.md` de la base antes de empezar.

## Qué es

Se apunta la cámara a un objeto y **aparece su nombre en quechua sobre el objeto, con su
pronunciación**. Si el corpus no tiene palabra para ese objeto, la interfaz lo convierte en una
invitación: "¿Cómo se dice esto? Enséñanos". También se puede grabar la propia pronunciación.

### Privacidad: requisito, no optimización

**La imagen nunca sale del dispositivo.** La clasificación corre en el navegador con
TensorFlow.js; el servidor solo entrega una tabla etiqueta → palabra. No envíes fotos, frames ni
recortes a ningún servidor, ni siquiera para "mejorar". Dilo claramente en la interfaz: es un
argumento de confianza.

### Modelo de visión

La tabla está construida para **COCO-SSD** (`@tensorflow-models/coco-ssd`, 80 clases de objetos
cotidianos, con cajas: permite anclar la palabra encima del objeto). Usa sus etiquetas tal cual
(`"cup"`, `"dog"`, `"cell phone"`…) como clave. Si propones otro modelo, habla antes con backend:
el conjunto de etiquetas se identifica con `label_set`.

## Endpoints

### Tabla etiqueta → palabra

```http
GET /lente/labels?label_set=coco-ssd
{"label_set": "coco-ssd", "lang": "quy", "mapped": 17, "total": 80,
 "labels": [
  {"label": "backpack", "label_es": "mochila", "lexeme_id": 4412, "lemma": "wayqa", "gloss": "saco",
   "audio_url": "/media/quy/lexemes/wayqa-4412.ogg", "audio_url_m4a": "/media/quy/lexemes/wayqa-4412.m4a",
   "method": "dictionary"},
  {"label": "bird", "label_es": "pájaro", "lexeme_id": 4022, "lemma": "pisqu", "gloss": "Ave",
   "audio_url": "/media/quy/lexemes/pisqu-4022.ogg", "method": "dictionary"},
  {"label": "airplane", "label_es": "avión", "lexeme_id": null, "lemma": null, "gloss": null,
   "audio_url": null, "method": null}
 ]}
```

- Descárgala **una vez** y cachéala (service worker): Lente debe funcionar sin conexión
  (el modelo de TF.js también se cachea). Refresca en segundo plano.
- `lexeme_id: null` = **vacío**: el corpus no tiene palabra para ese objeto. Hoy son 63 de 80.
  Diséñalo como el caso frecuente que es.
- `method`: `dictionary` (del diccionario), `model` (traducción automática validada),
  `community` (aportado y aprobado por la comunidad; ¡celébralo!).
- `?gaps_only=true` devuelve solo los vacíos (útil para una vista "ayúdanos a nombrar").
- Sin cámara: `GET /lexemes?q=<texto>&concrete=true` busca entre las palabras de objetos.
- Detalle de la palabra: `GET /lexemes/{lexeme_id}` (glosa, ejemplos, audio).

## Puntos de contribución

### Nombrar un objeto sin palabra

```http
POST /contributions   Authorization: Bearer …
{"type": "new_lemma", "lemma": "qiru", "gloss": "vaso de madera",
 "origin_module": "lente", "vision_label": "cup"}
```

Sirve tanto para palabras nuevas como para palabras que **ya existen** en el corpus pero no
estaban asociadas al objeto: al aprobarse en el Taller, la etiqueta queda enlazada.
`409` si la etiqueta ya tiene palabra; `422` si la etiqueta no existe.

### Grabar la propia pronunciación

```http
POST /contributions/audio      multipart/form-data, Authorization: Bearer …
  lexeme_id = 4022
  consent   = true              ← obligatorio y explícito; sin él → 422
  file      = <audio>           ← 0,3–6 s, ≤ 2 MB; webm/ogg/wav/m4a (el servidor normaliza)
→ 201 {"type": "audio_recording", "target_id": 4022,
       "payload": {"lemma": "pisqu", "original": "/media/…/pisqu-4022.ogg",
                   "proposed": "/media/quy/contrib/3f2a….ogg", "duration_ms": 1040, "consent": true},
       "status": "pending", …}
```

Envía `X-Module: lente`. Graba con `MediaRecorder` (el WebM de Chrome se acepta aunque no
declare duración; el servidor lo normaliza a Ogg y AAC). Antes de enviar: permitir escuchar y regrabar. El consentimiento debe
ser una acción consciente (no una casilla premarcada) y explicar que la grabación será pública
tras la revisión comunitaria. Errores `422` con mensaje: duración fuera de rango, no es audio,
sin consentimiento.

## Criterios de aceptación

- Ningún byte de imagen sale del dispositivo (verificable en la pestaña Red).
- Detección fluida en gama baja (baja la resolución/frecuencia de inferencia si hace falta);
  indicador claro mientras carga el modelo la primera vez.
- Palabra anclada al objeto (usa la caja de COCO-SSD), con toque para oír y ver detalle.
- Permiso de cámara denegado → alternativa útil (explorar la lista de objetos y sus palabras).
- Funciona sin conexión tras la primera carga.

---

## Prompt para el agente

```
Construye el módulo Lente de Corpus Vivo sobre la base existente (lee docs/frontend/README.md,
este archivo y DESIGN.md). Lente usa la cámara para reconocer objetos (COCO-SSD en TensorFlow.js,
todo en el dispositivo) y superpone su nombre en quechua con su pronunciación.

Tienes libertad creativa total sobre la experiencia de realidad aumentada: cómo aparece la
palabra sobre el objeto, cómo se escucha, cómo se transforma el "no sé cómo se dice" en una
invitación a enseñar. Recuerda que hoy la mayoría de los objetos NO tienen palabra: ese es el
momento central del módulo, no un caso de error. Propón primero la interacción y luego
impleméntala con el sistema de diseño de la base.

No negociable: ninguna imagen sale del dispositivo; consentimiento explícito para grabaciones;
funcionamiento sin conexión tras la primera carga; alternativa sin cámara. Usa solo los
endpoints documentados; lo que falte, a "Pedidos al backend".
```
