# 05 — Taller

> Lee `README.md` y el `DESIGN.md` de la base antes de empezar.

## Qué es

El lugar donde la comunidad **decide qué entra al corpus**. Las contribuciones de los otros
módulos llegan aquí y se presentan **de a una**, con su contexto: el audio original, la versión
actual y la propuesta. Quien revisa elige **aceptar**, **rechazar** o **"no estoy seguro"**
(esta última es esencial: sin ella la gente emite juicios que no puede sostener).

Reglas que implementa el backend (no las repliques, pero entiéndelas para comunicarlas bien):
- Ninguna aprobación es unilateral: hacen falta varios juicios, ponderados por la
  **confiabilidad** de cada revisor.
- La confiabilidad se estima con **elementos de control** con respuesta conocida, intercalados
  (el primero y luego uno cada cinco). **No se distinguen de los reales y la API nunca revela
  cuáles son**: no intentes mostrarlo.
- La identidad de quien propuso está oculta; solo se ve su confiabilidad.
- "No estoy seguro" nunca penaliza.

Además: un **panel de impacto** con lo que la comunidad ha logrado y la **exportación abierta**
de todo lo aprobado (devolver a la comunidad lo que produjo).

## Endpoints

### Siguiente ítem

```http
GET /taller/next            Authorization: Bearer …        → 200 | 204 (no hay nada que revisar)
GET /taller/next?type=audio_recording&type=new_lemma      filtrar por tipo (repetible)
{"contribution_id": 190, "type": "transcription_fix", "lang": "quy",
 "original": "mikuytam", "proposed": "mikutyam",
 "context": {"entry_id": 2618, "text": "Yananpiqa ensaladatam mikuytam munani",
             "audio_url": "/media/quy/americasnlp-dev-0062.ogg",
             "audio_url_m4a": "/media/quy/americasnlp-dev-0062.m4a",
             "position": 2, "segment_ms": [2235, 2778],
             "translation": "De vez en cuando me gusta comer ensalada."},
 "proposer_reliability": 0.5}
```

`context` depende de `type`:

| `type` | `original` → `proposed` | `context` |
|---|---|---|
| `transcription_fix` | token actual → token propuesto | `text` (con el token original), `audio_url`, `position`, `segment_ms` (reproduce solo ese tramo), `translation` |
| `translation_fix` | traducción actual → propuesta | `text` en quechua, `audio_url` |
| `gloss_fix` | glosa actual → propuesta | `lemma`, `examples` [{`text`, `translation`}] |
| `new_lemma` | `null` → glosa propuesta | `lemma`, `origin_module` (`radar`/`lente`), `vision_label` (objeto de Lente en español, si aplica), `existing_lemma` (true = solo se enlaza a un objeto) |
| `audio_recording` | URL audio actual → URL grabación | `lemma`, `gloss`, `duration_ms`, `original_m4a`, `proposed_m4a` |
| `new_sentence` (Dúo) | `null` → frase | `image_url`, `concept_es`, `understood` (si el compañero acertó), `origin_module` |

Las URLs de audio de `original`/`proposed` en `audio_recording` son relativas (antepón base URL).

### Emitir juicio

```http
POST /taller/reviews   {"contribution_id": 190, "verdict": "accept" | "reject" | "unsure"}
→ 201 {"contribution_id": 190, "recorded": true, "status": "pending"}
```

`status` pasa a `accepted`/`rejected`/`stale` cuando se alcanza el consenso (en los controles
siempre verás `pending`). Errores: `403` es tuya · `409` ya la juzgaste o ya se resolvió ·
`404` no existe.

### Impacto y exportación

```http
GET /taller/impact?days=30
{"lang": "quy",
 "timeline": [{"day": "2026-09-23", "created": 0, "accepted": 0, "reviews": 0},
              {"day": "2026-09-24", "created": 2, "accepted": 1, "reviews": 3}],
 "contributions": {"pending": 2, "accepted": 0, "rejected": 0, "stale": 0},
 "accepted_by_type": {}, "reviews": 0, "contributors": 2, "reviewers": 1, "fleiss_kappa": null}
```

`timeline` trae un punto por día (zona horaria de Lima), incluidos los días sin actividad: listo
para graficar.

`fleiss_kappa`: grado de acuerdo entre revisores (1 = total, 0 = azar, `null` = aún sin datos).
Tradúcelo a lenguaje humano.

```http
GET /taller/export?format=jsonl|csv     → descarga con Content-Disposition
```

Tu confiabilidad: `GET /auth/me` → `reliability` (0,1–1). Declararse hablante nativo:
`PATCH /auth/me {"is_native_speaker": true}` (solo aumenta el peso si además acierta en los
controles; explícalo para no generar expectativas falsas).

## Criterios de aceptación

- Revisar un ítem en ≤ 2 toques tras escuchar/leer; flujo continuo al siguiente.
- El contexto necesario siempre visible (en transcripción: reproducir el tramo exacto).
- "No estoy seguro" con el mismo peso visual que aceptar/rechazar.
- Estado vacío (204) positivo, no un callejón sin salida.
- Panel de impacto comprensible para una persona no técnica; exportación a un toque.

---

## Prompt para el agente

```
Construye el módulo Taller de Corpus Vivo sobre la base existente (lee docs/frontend/README.md,
este archivo y DESIGN.md). Taller es donde la comunidad revisa, una por una, las correcciones y
aportes que llegan de Radio, Radar, Lente y Dúo, y decide por consenso qué entra al corpus.

Tienes libertad creativa total: queremos que revisar se sienta como participar y cuidar la
lengua, no como una tarea administrativa ni una cola de moderación. Piensa en el ritmo (uno tras
otro, sin fricción), en cómo presentar cada tipo de contribución con justo el contexto necesario,
en cómo mostrar el impacto colectivo de forma que emocione, y en cómo explicar la confiabilidad
sin gamificar de forma tóxica. Propón primero la experiencia y luego impleméntala con el sistema
de diseño de la base.

No negociable: tres opciones con igual jerarquía (aceptar, rechazar, no estoy seguro); nunca
revelar ni intentar inferir cuáles ítems son de control; identidad del proponente oculta;
reproducir el tramo exacto de audio en correcciones de transcripción. Usa solo los endpoints
documentados; lo que falte, a "Pedidos al backend".
```
