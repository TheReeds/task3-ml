# Fase 0 — Informe de viabilidad (quechua, modelos públicos)

Fecha: 2026-09-24 · Lengua: quechua sureño (`quy`) · Hardware: RTX 3050 Laptop (4 GB VRAM)

Mientras el corpus y el modelo del curso no estén disponibles, se evaluaron recursos públicos
como sustitutos detrás del contrato de interfaz (§10.2). Detalle de cada prueba en
`data/processed/viability/*.md`; se reproduce con `uv run python -m pipeline.viability`.

## Fuentes

| Recurso | Uso | Observación |
|---|---|---|
| AmericasNLP 2021 dev (996 pares quy–es) | Entradas del corpus provisional | Texto general, bien curado |
| AmericasNLP 2021 train (125k pares) | Frecuencias y embeddings | Mayoritariamente JW300: dominio religioso, ortografía de 5 vocales |
| AmericasNLP dict (9.643 pares) | Lemas y glosas (`lexemes`) | Ortografía de 3 vocales; 2.584 entradas de una palabra |
| NLLB-200 distilled 600M | Adaptador: traducir / traducir inverso | `quy_Latn` ↔ `spa_Latn` |
| MMS-TTS `quy` | Audio sintético para Radio | Sustituye al audio real del corpus |
| torchaudio MMS_FA | Alineación forzada por palabra | CTC, técnica citada en el doc. (Kürzinger 2020) |
| fastText (gensim) | Adaptador: vectorizar (Radar) | Entrenado sobre el corpus a nivel de lema |

## Resultados por módulo

### Radio — viable

- **Traducción:** chrF++ 31,3 (quy→es) y 22,3 (es→quy) en 200 oraciones; 1,4 GB VRAM.
  Conserva el sentido general pero comete errores léxicos (p. ej. *warmakuna* "niños" → "mujeres").
  → Mostrar la traducción del dataset cuando exista; la del modelo solo como respaldo, marcada
  con `origin = model`. Es además una fuente natural de contribuciones de corrección.
- **Audio + alineación:** 6/6 enunciados con marcas monótonas, cobertura media 83 % del audio,
  pausas en comas respetadas, palabra más corta 140 ms.
  → Viable para resaltado por palabra.
  → Pendiente: los números ("5,539") y signos no alineables se descartan; la ingesta debe
  mapear tokens mostrados ↔ tokens alineados para que los no alineados hereden el tiempo vecino.

### Radar — viable con lematización

- Con formas de superficie, **ningún** conjunto de vectores sirve: los vecinos son flexiones de
  la misma palabra (*wasi* → wasim, wasita, wasipi).
- Tras **normalizar ortografía (5→3 vocales) y reducir flexiones a lema** (`pipeline/quechua.py`),
  aparecen vecindarios semánticos: *yaku* (agua) → qucha (laguna), pukyu (manantial);
  *urqu* (cerro) → wayqu (quebrada); *killa* (mes) → agosto, enero, wata (año); *tayta* ↔ *mama*.
- Casos débiles por sesgo del dominio religioso: *sara* (maíz), *inti* (sol), *puñuy* (dormir).
- **Vocabulario elegible:** 421 lemas con frecuencia ≥ 50 (vs. 218 sin normalizar).

Decisiones para la implementación:
1. Radar opera **solo sobre lemas**: el intento del jugador se normaliza y lematiza antes de buscarlo.
2. La palabra del día excluye palabras funcionales (mana, chay, hinaspa…) mediante lista de exclusión.
3. El espacio de ranking colapsa derivados triviales del diccionario (wasiy, wasicha → wasi).
4. Cuando el otro equipo entregue su modelo, `embed` se sustituye vía adaptador; el pipeline de
   lemas se mantiene.

### Lente / Dúo — no evaluados (fuera de esta fase)

## Riesgos detectados

| Riesgo | Mitigación |
|---|---|
| Audio sintético no representa habla real | Etiquetar entradas `audio_origin = synthetic`; buscar Siminchik / Common Voice `quy` |
| Dominio religioso sesga embeddings y frecuencias | Pesar menos JW300 o ampliar con otras fuentes; el corpus real del curso lo resolverá |
| Lematizador por sufijos es heurístico | Aislado en `pipeline/quechua.py`, reemplazable por el segmentador del equipo del modelo |
| VRAM 4 GB | Los modelos se cargan de a uno en el pipeline; en la API solo NLLB (1,4 GB) |

## Conclusión

Radio y Radar son viables con recursos públicos para quechua. Se procede a la Fase 1 (núcleo:
esquema, ingesta y API de lectura) usando el dev de AmericasNLP con audio MMS-TTS como corpus
provisional. Para aimara, NLLB cubre `ayr_Latn`; falta verificar TTS y diccionario equivalentes.
