# Traducción — NLLB-200 distilled 600M (fp16, GPU)

Muestra: 200 oraciones del dev de AmericasNLP 2021.

| Dirección | chrF++ | Tiempo | 
|---|---|---|
| quy → es | 31.3 | 7.0 s |
| es → quy | 22.3 | 18.7 s |

VRAM pico: 1.39 GB

Referencia: el baseline oficial de AmericasNLP 2021 para es→quy rondaba chrF ~30.

## Ejemplos

- **quy:** IRT nisqapi artistakunaqa manam imatapas warmakunawan rurankuchu, chaypiqa llaqtapi machukunawanmi llamkanku
  - ref es: Los artistas del IRT no hacen nada con niños y, en su lugar, se centran en los adultos de la comunidad.
  - NLLB es: Los artistas del IRT no tienen nada que ver con las mujeres, sino con las mujeres de la ciudad

- **quy:** Kikinkupa yachayninpi munayninkum, kay huñupa yanapayninwan kan, yachasqaqa llapan llaqtata yanaparinqa
  - ref es: En su propio interés ilustrado, cuentan con el apoyo de esta incipiente organización, sabiendo que beneficiaría a la ciudad en su conjunto.
  - NLLB es: Si su voluntad es voluntaria y se hace posible con la ayuda de este grupo, la comunidad será beneficiada

- **quy:** Kay atracción botánica 3,3 acres sayayniyuqmi ancha allin sumaq jardinkunawan sumaq qawakun, sachakunamanta informaciónwan huk sacha sachawan munay llinpisqa kan
  - ref es: Esta impresionante y hermosa atracción botánica de 3,3 acres de extensión combina lo mejor de las ideas de jardinería, información de plantas y un diseño paisajístico inspirador.
  - NLLB es: Esta atracción botánica de 3,3 acres tiene un jardín de gran belleza, información sobre los árboles y un jardín de gran belleza

- **quy:** 5,539 Derecho yachakuqkunam aswan allin huñuta hatarichinku.
  - ref es: Los 5 539 alumnos de la escuela de derecho forman un grupo distinguido.
  - NLLB es: Los 5,539 estudiantes de derecho han creado una sociedad mejor.

- **quy:** Yachayninku tukuruptinqa sinchi, chirim rikurirunku
  - ref es: Se vuelven endurecidos y fríos una vez que completan el entrenamiento.
  - NLLB es: Cuando se les hace falta, se vuelven más duros y más duros
