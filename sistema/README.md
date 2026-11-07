# Sistema de estudio de partituras (COBLA PRO MUSIC)

Convierte las particellas en PDF de una pieza en:
- **App de estudio** (HTML, para Chrome en el PC): partitura original con cursor, 5 fases progresivas, micro que corrige notas y tiempo, bucles y progreso.
- **PDF anotado** de mi voz: con quién voy en cada parte, entradas, pasajes difíciles y una guía por secciones.
- **MusicXML + MIDI** de la pieza completa (para abrir en MuseScore).

## Estructura de la carpeta de trabajo
```
piece.json          configuración de la pieza (ver piece.example.json)
parts/*.pdf         una particella PDF por instrumento (nombres sencillos, sin espacios)
scripts/*.py        el sistema (y scripts/template.html, la app)
```
Salida en `out/`.

## Requisitos
`pip install --break-system-packages homr music21 verovio reportlab pypdf pillow numpy` · `poppler-utils` (pdftoppm, pdfinfo, pdftotext) · Java no hace falta.

## Uso
```
python3 scripts/run.py          # todo
python3 scripts/run.py assemble # un paso: render, omr, assemble, build, export, boxes, analyze, annotate, app
```
`omr` tarda ~30 s por página (homr). Los resultados se cachean en `omr/`.

## Cómo funciona
1. **render**: páginas a PNG 300 dpi (`img/`) + JPG de mi voz para la app (`app/`).
2. **omr**: homr lee cada página → MusicXML por página.
3. **assemble** (`assemble.py` + `layout.py`): une páginas por instrumento. Los silencios multicompás los lee homr mal, así que se corrigen con el texto del PDF: números de compás al inicio de cada sistema y números de los multicompases (la fuente musical va desplazada: el glifo '/' = 0, '0' = 1…). Un DP (`solve`) encaja cada sistema para que sume exactamente los compases que toca. Las alturas de compás (3/8, 3/4…) se deducen del contenido.
4. **build / export**: `out/score.json` (notas por voz) + MusicXML y MIDI. `overrides` en piece.json corrige compases concretos a mano.
5. **boxes** (`barlines.py`): detecta las barras de compás en el PDF de mi voz → caja de cada compás (para el cursor de la app y las anotaciones).
6. **analyze**: compara mi voz con las demás compás a compás: mismo ritmo, unísono/terceras/sextas, entradas tras silencios (y a quién escuchar), solos, pasajes difíciles.
7. **annotate**: dibuja todo encima del PDF original de mi voz + guía final.
8. **app**: inyecta datos e imágenes en `template.html` → un único HTML.

## Revisar siempre
- Que `assemble` termine con **todas las voces con el mismo nº de compases** (= `total_measures`) y mirar los LOG `forced fix` / `pad kept`.
- Comparar visualmente mi voz (renderizar `out/<me>.musicxml` con verovio) con el PDF original, página a página. Corregir con `overrides`.
- Que `boxes` no avise de sistemas sin cuadrar.
- Percusión: homr no la lee bien (pentagrama de 1 línea) → no incluirla en `parts` (la app tiene metrónomo).

## piece.json
- `me`: id de mi voz. `total_measures`: último compás de la pieza (mirarlo en el PDF).
- `parts[].role`: `yo`, `companeros` (con quien más cuadro; fase 4), `base` (bajo/pulso; fase 3), `melodia`.
- `parts[].timbre`: `flauta`, `lengueta`, `fagot`, `metal`, `cuerda`, `voz`, `bajo`.
- `sections`: inicio de cada sección (letras de ensayo), nombre y tempo orientativo (`bpm` de la parte, `beat` en negras: 1.5 = negra con puntillo en 3/8 o 6/8, 1 = negra).
- `overrides`: `"voz:compás": [[midi|null, "duración en negras"], ...]`.
