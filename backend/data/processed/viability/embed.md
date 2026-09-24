# Representaciones vectoriales para Radar

## A) fastText wiki.qu (preentrenado)

Vocabulario: 23,073 · cobertura de las 5.000 palabras más frecuentes del corpus: 20%

- **wasi** → wasim, wasin, wasita, wasiqa, wasipi, wasipim, wasiman, wasinmi
- **yaku** → yakum, yakuqa, yakuta, yakupi, yakutam, yakuwan, yakuman, yakupas
- **mikuy** → mikuyta, mikuq, yaykuy, rikuy, mañakuy, miskita, puñuy, rurayta
- **runa** → runan, runakuna, runaman, runam, runankuna, runakunaman, runapa, runataq
- **allqu** → alli, allpa, oveja, allpaqa, kichka, allpam, allpaman, allpapi, kichki
- **inti** → intita, intipa, intiqa, ruraymi, kutimuspa, wayta, achkiyta, inc
- **tayta** → taytan, taytanqa, taytanpa, taytacha, churin, churinkuna, churinmi, payta
- **mama** → llaqtapi, llaqtapipas, llaqtapim, llaqtam, llaqtapa, llaqtapas, llaqtanpi, llaqtanmi
- **urqu** → nina, diablo, aguja, m, hurqusqa, viuda, wiksa, ur, uray
- **sara** → sarah, wara, qara, lepra, sandra, para, wira, sasa
- **killa** → killakama, killapim, killapi, killaqa, killakunapim, cebadilla, kikillan, killamanta
- **puñuy** → puñuq, punkuta, rurananpaq, wiksa, purun, llullu, mikuy, purinanpaq

## B) FastText entrenado sobre AmericasNLP train+dev (19 s)

Vocabulario: 32,744

- **wasi** → wasim, wasiqa, wasiy, wasipa, wasita, wasa, wasin, wasipi
- **yaku** → yakuta, yakum, yakupa, yakuyoq, raku, yakupi, yakuqa, yakuman
- **mikuy** → mikumuy, mikuykachiy, mikuyllapi, mikuyqa, mikuq, mikuypa, mikuypas, mikunan
- **runa** → runapura, runtu, runaña, runam, runalla, runan, runakuna, runata
- **allqu** → mallqo, allen, alliq, al, alfred, alex, gallo, alhaja, allpayoq
- **inti** → intipi, intipa, intiqa, intita, centimetro, luz, ñiti, bob
- **tayta** → taytayta, taytata, taytay, mamayta, pitayta, mama, taytapa, taytayoq
- **mama** → mamam, mamay, mamapa, mamata, mamaqa, mamakuna, mamanku, mamáy
- **urqu** → turquía, hurqurqa, horqorurqa, eufrates, hungría, n, madagascar, lluqsiramurqa, d
- **sara** → sarah, saram, rahab, abel, isaac, abrahan, saraqa, rebeca
- **killa** → killapi, killakama, killam, killan, killata, killapuni, killaña, killaqa
- **puñuy** → puñuq, puñuyqa, puñuywan, puñuspa, puñusqa, puñuyta, pierdekuy, qariwan

## C) FastText a nivel de lema, ortografía normalizada (16 s)

Espacio de búsqueda: 785 lemas del diccionario con frecuencia ≥ 5

- **wasi** (Casa) → wasiy (Mi casa), wasin (Su casa), wasicha (pequeña casa), wasiyuq (Dueño de una casa), waska (Rectángulo), wasiypim (En mi casa), wasinpim (En su casa), qasi (Quieto)
- **yaku** (Agua) → aqu (Arena), urku (Frente), yakulla (manta ceremonial), raku (Grueso), qucha (Laguna), uku (Profundo), pukyu (Manantial), urqu (Cerro)
- **mikuy** (Comer) → rantikuy (Vender), rakikuy (Separarse), aypuy (agasajar), tuma (Abertura), tusuy (Bailar), tumasa (Nombre propio de una mujer), rantiq (Comprador), quykuy (Regalar)
- **runa** (Hombre) → runakuna (Gente), runamasi (Prójimo), runtu (Huevo), rutuy (Trasquilar), kachiyuq (salado), atiysapa (rico), wakchayay (Volverse pobre), arwi (adobe)
- **allqu** (Perro) → mallqu (Pichón), allqucha (Perrito), malliy (Probar), aqu (Arena), ñutqu (Seso), talliy (Echar), rapra (Ala), ñuñu (Seno)
- **inti** (Sol) → siqay (Subir), puquy (Madurar), pukyu (Manantial), yarqay (Hambruna), iniru (enero), waqra (Cuerno), llantuy (Ensombrecer), tullu (Hueso)
- **tayta** (Papá) → taytay (Señor), mama (Mamá), taytakuna (Padres), taytallay (Oh, Dios mío), mamakuna (Madres), taytacha (Dios), mamallay (Caramba), wayta (Flor)
- **mama** (Mamá) → mamakuna (Madres), tayta (Papá), mamallay (Caramba), uyway (Criar a los hijos), taytay (Señor), taytakuna (Padres), turi (Hermano), taytacha (Dios)
- **urqu** (Cerro) → aqu (Arena), muqu (Morro), qucha (Laguna), chimpa (Frente), pukyu (Manantial), puka (rojo), wayqu (Quebrada), ñutqu (Seso)
- **sara** (Maíz) → ilina (Elena), paray (Llover), willka (Bisnieto), para (Lluvia), sullu (Feto), abusay (abusar), hirida (Herir), araña (araña)
- **killa** (Mes) → agustu (Agosto), abril (abril), iniru (enero), dumingu (Domingo), wata (Año), abugadu (abogado), illaq (caminante), kiru (Diente)
- **puñuy** (Dormir) → qari (Varón), purikuy (Pasear), sinkakuy (Emborracharse), wiksayuq (Embarazada), wiksa (Barriga), tragu (Trago), ñuñu (Seno), wayanakuy (golondrina)
