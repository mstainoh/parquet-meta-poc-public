# Extraction notes

Log of the extraction PDF → `csv/raw/`, written per extraction batch while extracting, kept as written (mixed
Spanish/English). It describes `csv/raw/` at extraction time. Page convention: PDF page = printed page + 16.

Superseded by later steps (see `DATASET.md`, `csv/modified/_edits.csv` and `data_processed/inspect/`):
- W-16 "not corrected": its easting was corrected in `csv/modified/` from Appendix 2 Table 4.
- Table 10.4 range "coincides with the text": it does not (DDH-13A-D and DDH-10B are shallower), see the inspect finding.
- 10.6 `collar_id` was dropped in `csv/modified/` (replaced by `borehole_id`); 10.7 `dd_borehole_id` was renamed
  `piezometer_name`.
- The CRS (EPSG:22183) is an assumption: no extracted table declares it.

---

## Status grupo tablas 10.1, 10.2, 10.4, 11.1, 11.2

Metodo: pdfplumber extract_words con coordenadas (separacion por columnas x) + verificacion visual contra PNG de cada pagina.
Offset confirmado: pag_pdf = pag_impresa + 16 (163/147, 164/148, 167/151, 195/179, 198/182).

| Tabla | Archivo | Filas | Pendientes |
|---|---|---|---|
| 10.1 (RC, PDF 163) | t10_1.csv | 24 | 0 |
| 10.2 (PDF 164) | t10_2.csv | 7 | 0 |
| 10.4 (DDH, PDF 167) | t10_4.csv | 29 | 0 |
| 11.1 (PDF 195) | t11_1.csv | 8 | 0 |
| 11.2 (PDF 198) | t11_2.csv | 7 | 0 |

No hay archivos pendientes_*.csv (ninguna fila dudosa). Ninguna tabla cruza paginas (11.2 empieza y termina en PDF 198).

## Convenciones numericas
- 10.1: metros, punto decimal, enteros salvo PE-07 (78.9 / 170.1). Sin separador de miles en las filas.
- 10.4: metros con 2 decimales, punto decimal (ej. 272.45).
- 10.2: conteos de muestras enteros; la coma del origen es separador de miles (1,614 -> 1614; sin ambiguedad porque son conteos de muestras y los totales cuadran).
- from_m: "-" en origen = vacio (no se asume 0). length_m viene del origen, no se calculo.
- 11.1/11.2: texto. En 11.1 el guion largo (en dash, U+2013) de "1 - 2 hours" se conserva tal cual (pdftotext lo rompia).

## Controles de coherencia
- 10.1: 24 pozos (PE-01..PE-22 + PE-14A + PE-17A) = "Total Boreholes: 24" OK. Suma length_m = 4176.1 vs pie "4,176 m": diferencia 0.1, atribuible al redondeo del pie (PE-07 = 170.1). length_m = to_m - from_m (from vacio=0) en las 24 filas, sin inconsistencias. Maximo 371 (PE-10), minimo 28 (PE-01): coincide con el texto.
- 10.4: 29 pozos = "Total Boreholes: 29" OK. Suma length_m = 5713.45 vs pie "5,714 m": diferencia 0.55, atribuible a redondeo del pie (el origen redondea a entero). length_m = to_m - from_m en las 29 filas. Rango 79 (DDH-2: 78.90) a 449.5 (DDH-7) coincide con el texto.
- 10.2: 1487 + 127 = 1614 OK; 1614 + 260 + 263 + 253 = 2390 OK. 1,487 coincide con el texto ("1,487 brine samples" RC).
- 11.1 / 11.2: sin totales; verificadas visualmente contra imagen.

## Rarezas del origen
- 10.1: pdftotext desordena la tabla (valores huerfanos al final); en el PDF la fila esta correcta. Solo PE-07 (from 78.9) y PE-14A (from 144) tienen from_m declarado; el resto es "-".
- 10.1: el texto del informe dice "PE-01 through PE-22, plus two twin holes" = PE-14A y PE-17A (coincide con las filas).
- 10.4: "DDH9A" sin guion en origen -> normalizado a DDH-9A (nota en la fila). DDH-6A aparece antes que DDH-6 en la tabla. Solo DDH-7 (from 371) y DDH-11 (from 165) tienen from_m declarado.
- 10.4: pozos DDH-13A..D con 20.50 m identicos (cuatro filas iguales; verificado visualmente, es el valor del origen).
- 10.2: el texto del informe dice "Table 10.3" para la tabla siguiente (no asignada).
- 11.2: es una tabla analisis -> norma ASTM; la fila RBRC no es ASTM ("Developed by D.B. Stephens (see Section 11.9.2)").

---

## Status: tablas 10.3 y 10.5 (informe NI 43-101 Cauchari)

Extraccion con pdfplumber (palabras + coordenadas), verificada contra imagen de las paginas PDF 165, 166 y 168.
NOTA: la salida de `pdftotext -layout` de p165/p166/p168 esta DESALINEADA (la columna SO4/Li y las ultimas columnas
aparecen una fila corrida respecto de la fila real). No usar `_text/p165.txt`, `p166.txt` ni `p168.txt` para estas
tablas. La reconstruccion por coordenadas es la correcta (confirmada: SO4/Li = SO4/Li_mg_l recalculado coincide con la fila).

## Archivos
- `t10_3.csv` (45 filas), `t10_5.csv` (14 filas)
- `pendientes_10_3.csv` (6 filas), `pendientes_10_5.csv` (3 filas)

## Tabla 10.3 (pag impresa 149-150, PDF 165-166)
- Filas extraidas: 45 intervalos, 14 pozos (PE-04, 06, 07, 09, 10, 13, 14, 15, 17, 18, 19, 20, 21, 22). Esperado 14 / 45: OK.
  - Por pozo: PE-04:3, PE-06:2, PE-07:5, PE-09:3, PE-10:2, PE-13:2, PE-14:3, PE-15:4, PE-17:6, PE-18:1, PE-19:4, PE-20:4, PE-21:3, PE-22:3.
  - p165: 25 filas; p166: 20 filas (`pag_pdf` / `pag_impresa` 165/149 y 166/150 segun donde esta cada fila).
- Columnas: tabla, pag_impresa, pag_pdf, well_id, from_m, to_m, length_m, b_mg_l, k_mg_l, li_mg_l, mg_mg_l, so4_mg_l,
  mg_li_orig, k_li, so4_li, mg_li_recalc, nota.
- Convencion numerica (10.3): coma = separador de MILES en B, K, Li, Mg, SO4 (p.ej. 5,987 = 5987; rangos 174-27284 mg/L,
  coherentes con mg/L). Punto = DECIMAL en K/Li y SO4/Li (3 decimales, p.ej. 8.652 y 29.621; magnitudes ~7-13 y ~19-44,
  confirmado recalculando K/Li y SO4/Li desde las concentraciones). Mg/Li es entero redondeado en origen.
- `mg_li_orig`: texto tal cual (entero). `mg_li_recalc` = round(mg_mg_l / li_mg_l, 2), calculado, sin tocar el original.
  `k_li` y `so4_li` se dejan con los 3 decimales del origen.
- PE-17: la tabla cruza pagina. En p165 la fila 78-84 lleva la etiqueta PE-17; en p166 las 5 primeras filas (87-91 ...
  171-174) NO tienen etiqueta de pozo y se asignaron a PE-17 por continuacion (la siguiente etiqueta es PE-18 en la
  fila 140-260). Marcadas en `nota` y en pendientes (inferencia razonable, verificada en imagen, pero no esta escrita en el origen).
- Las etiquetas de pozo estan centradas verticalmente en cada grupo (no alineadas a la primera fila): la asignacion de
  pozo se hizo por grupos contados en la imagen y se verifico programaticamente que cada etiqueta cae dentro del rango
  de filas de su grupo.
- PE-10 intervalo 60-152: Mg=174, Mg/Li=0 marcado como atipico en `nota`, valores tal cual. Observacion: el Mg/Li=0 es
  consistente con Mg=174 (174/396 = 0.44); lo atipico es el Mg (vecino 152-234: 1,144), no una mala lectura del Mg/Li.

### Controles de coherencia (10.3)
- 45/45 filas con from < to. Intervalos crecientes dentro de cada pozo: OK.
- length_m == to-from en la mayoria; **length_m != to-from en 6 filas**, todas con length_m MENOR que to-from, tal cual
  en origen (probablemente largo efectivo muestreado; no se tocaron): PE-04 83-187 (89 vs 104), PE-07 78-108 (20 vs 30),
  PE-07 145-205 (54 vs 60), PE-07 207-248 (38 vs 41), PE-20 60-127 (64 vs 67), PE-20 129-150 (19 vs 21). (ver `nota`.)
  Ninguna con length > to-from.
- Mg/Li: |mg_li_orig - mg_li_recalc| max 0.49 (<=0.5 en las 45 filas = consistente con redondeo a entero). OK.
- K/Li: |K/Li recalculado - original| max 0.0005 (45/45 OK).
- SO4/Li: |recalculado - original| max 0.035 (~0.1%), en 38 de 45 filas > 0.002. Probable origen: promedio de ratios por
  muestra vs ratio de promedios, o redondeo previo. No es error de lectura (la direccion y magnitud son las de la fila).
  Se conserva el valor del origen.

## Tabla 10.5 (pag impresa 152, PDF 168)
- Filas extraidas: 14 intervalos, 6 pozos (DDH-01:4, DDH-04:1, DDH-06:3, DDH-08:2, DDH-12:3, DDH-13:1).
  El enunciado no fijaba un esperado de filas; los 6 pozos coinciden con la lista asignada.
- Columnas: tabla, pag_impresa, pag_pdf, well_id, from_m, to_m, length_m, b_mg_l, k_mg_l, li_mg_l, mg_mg_l, so4_mg_l,
  mg_li_orig, mg_li_recalc, nota. (No trae K/Li ni SO4/Li, por eso no hay `k_li`/`so4_li`.)
- Convencion numerica (10.5), por columna, segun magnitud:
  - K, Mg, SO4: el punto es separador de MILES cuando el texto es `d{1,3}.ddd` (4.847 = 4847; 1.147 = 1147; 9.039 = 9039;
    23.038 = 23038). Un valor sin punto y de 3 digitos (Mg 927) se toma como esta (927).
  - B, Li, length: enteros sin separador.
  - Mg/Li: DECIMAL con 2 decimales (2.20, 3.46). Se guarda tal cual en `mg_li_orig` (conserva "2.20").
- Rangos tras normalizar: B 610-872, K 3735-6698, Li 408-732, Mg 927-1921, SO4 9039-23038 mg/L (misma escala que 10.3).
- Etiquetas de pozo: aqui van en la PRIMERA fila de cada grupo. DDH-06 tiene 3 filas (100-115, 118-136, 140-190); DDH-08
  empieza en 20-75. Verificado con imagen y con consistencia Mg/Li.

### Controles de coherencia (10.5)
- 14/14 con from < to. Mg/Li: |orig - recalc| max 0.007 (todas coinciden a 2 decimales salvo DDH-01 15-55: orig 2.20 vs
  recalc 2.19 y DDH-08 20-75: orig 3.46 vs recalc 3.45, diferencias de redondeo de 0.01 por el redondeo de las concentraciones). Esto confirma tambien la lectura de los miles en Mg y Li.
- length_m vs to-from: **2 filas con length_m MAYOR que to-from (incoherente en origen)**: DDH-01 70-105 (40 vs 35) y
  DDH-06 140-190 (51 vs 50). 3 filas con length_m menor que to-from: DDH-08 20-75 (50 vs 55), DDH-12 170-185 (10 vs 15),
  DDH-12 225-285 (25 vs 60). Todas leidas bien en imagen; se dejan tal cual con `nota`.

## Pendientes (ver `pendientes_*.csv`)
- 10.3: PE-10 60-152 (atipico), 5 filas PE-17 de p166 (pozo por continuacion), (ninguna fila con length > to-from).
- 10.5: DDH-01 70-105 y DDH-06 140-190 (length > to-from), DDH-12 65-70 (Mg 927 sin separador de miles; no ambiguo por magnitud).

## Rarezas del origen
- Etiquetas de pozo centradas (10.3) vs. en primera fila (10.5).
- Tabla 10.3 cruza p165->p166 dentro del grupo PE-17 sin repetir la etiqueta.
- length_m no siempre = to-from (posible largo muestreado); en 10.5 hay dos casos con length > to-from.
- SO4/Li (10.3) ligeramente distinto del cociente SO4/Li de las columnas redondeadas.
- La tabla 10.3 abarca p149-150 impresas y es horizontal (landscape, pagina rotada: 792x612); 10.5 es vertical.

---

## Status - extraccion Tablas 10.6 y 10.7 (NI 43-101, LAC Jan-8-2025)

Fuente: PDF paginas 170-171 (impresas 154-155) para 10.6; PDF 174-176 (impresas 158-160) para 10.7.
Metodo: `pdfplumber.extract_tables()` (las tablas tienen reglas dibujadas, la extraccion sale limpia; el `pdftotext -layout` de 170-171 sale desordenado y NO se uso). Verificacion visual de las 5 paginas contra imagen (110 dpi): sin discrepancias.
Archivos: `t10_6.csv`, `t10_7.csv`, `pendientes_t10_6.csv`, `pendientes_t10_7.csv` (ambos pendientes: solo cabecera, 0 filas).

## Tabla 10.6 - Borehole drilling summary (piezometros 2017-2019)
- Filas extraidas: **49** (pag_pdf 170: 29; pag_pdf 171: 20). Pendientes: **0**.
- Una fila por piezometro tal como viene. Columnas: `tabla, pag_impresa, pag_pdf, dd_borehole_id, piezometer_name, collar_id, screen_diameter_in, platform_raw, contractor, total_depth_m, screen_top_mbtw, screen_base_mbtw, x_coordinate_m, y_coordinate_m, nota`.
- Convencion numerica: punto decimal, sin separador de miles. Profundidades en m, screen top/base en mbtw (metros bajo el tope del pozo), X/Y en m (Gauss-Krüger faja 3, POSGAR 94, EPSG:22183 asumido; la tabla no declara el CRS en las paginas extraidas). `screen_diameter_in` = numero en pulgadas (se quitan las comillas `"`). Enteros se escriben sin decimales (`200`, no `200.00`); no se pierde informacion (la fuente trae `.00` solo como formato).
- `platform_raw`: texto crudo de la columna "Plataform" (typo del origen): `1`, `3 13 14`, `8 15`, `11 12`, `17 20`, `CN-10`, `PE-09`, etc.
- `collar_id` (regla): si `piezometer_name` cumple `^(SL|ML|DL)-(\d+)\s?(B?)$` -> numero con 3 digitos + `B` opcional (`ML-001`, `SL-001`, `DL-001` -> `001`; `DL-08` -> `008`; `SL-13` -> `013`; `DL-003 B` -> `003B`; `SL-004B` y `DL-004 B` -> `004B`). Vacia para `Cemented`/`Abandoned` (7 filas DD18D) y para `DD19D-001` / `DD19D-PE09`. Es regla SOLO por nombre; no se uso coordenada ni borehole. 16 collares, 15 con >1 piezometro, 1 singleton (`003B`, solo `DL-003 B`). Al leer con pandas usar `dtype={'collar_id': str}` (si no pierde los ceros).
- Filas con `collar_id` vacio: 9 (7 `Cemented`/`Abandoned` DD18D-001..007, `DD19D-001`, `DD19D-PE09`).
- Casos conocidos tratados:
  - DD19D-PE09: venia partida en dos lineas ("DD19D-" / "PE09"); reconstruida como `DD19D-PE09`. El diametro lo devuelve pdfplumber con glifo roto (`2?`); en la imagen es `2"` -> 2. Anotado en `nota`.
  - Plataformas multiples ("3 13 14", "8 15", "11 12", "17 20"): texto crudo conservado en `platform_raw`.
  - Filas DD18D-001..007: la columna "Piezometer Name" trae el estado (`Cemented` x6, `Abandoned` x1) y screen top/base tambien dicen `Cemented`/`Abandoned`. Se conserva el texto en `piezometer_name`, screen top/base quedan vacios y `nota` lo explica.
  - DD19D-001: diametro `-`, screen top/base `-` -> vacios (nota). El piezometer name es el mismo borehole ID.
  - `DL-006`: diametro `2.5` sin comillas en origen (se asume pulgadas, anotado). `SL-004B`: `2.5 "` con espacio (anotado).
- Rarezas del origen (no corregidas):
  - Nombres con numeracion inconsistente: `DL-08`, `DL-09`, `DL-10`, `SL-13`, `DL-003 B` (con espacio) vs `SL-004B`. En 10.7 aparecen como `DL-008`, `DL-009`, `DL-010`, `DL-003B`, `DL-004B`.
  - Tipo de borehole vs prefijo: todos los `DL-*` son borehole `..D-` y todos los `ML/SL` son `..S-` (chequeo: 0 excepciones). `RC17D-003` para `DL-003 B` (sin "B" en el borehole ID).
  - Dentro de un collar, `SL` y `ML` comparten exactamente X/Y (14 de 15 grupos); `DL` esta desplazado entre 8.6 y 69.3 m (mayor: collar 005, DL-005 vs ML-005 = 69 m; el resto 8-26 m). **Collar 014 es la excepcion**: `ML-014` (3426381, 7387647) esta a ~21 m de `SL-014` y `DL-014` (ambos 3426361, 7387640); posible error de origen, no corregido.
  - `SL-014`: total depth 26.7, screen top 2.9, screen base 26.7 (pozo muy somero respecto del resto de los SL, 50 m); base == total depth.
  - Coordenadas de `DD19D-001` (3424376, 7378282) coinciden con `ML-001/SL-001` (3424377, 7378282) a 1 m.
  - Diametro heterogeneo: ML-008 2.5", DL-08 2", DL-002 2", DL-012 3" (no es error evidente; solo lo reporto).
- Controles de coherencia (todos sobre las 49 filas):
  - X en [3.0e6, 3.9e6] y Y en [7.0e6, 7.6e6]: **49/49 OK; ninguna fila con X/Y invertidas**.
  - screen_top < screen_base (donde ambos numericos): 0 violaciones.
  - screen_base <= total_depth y screen_top <= total_depth: 0 violaciones.
  - Nombres de piezometro duplicados (excluyendo `Cemented`): 0.
  - Conteo por pagina coincide con la imagen (29 + 20).

## Tabla 10.7 - Brine concentrations averaged across depth intervals
- Filas extraidas: **63** (pag_pdf 174: 24; 175: 24; 176: 15). Pendientes: **0**. 18 piezometros/boreholes distintos.
- Columnas: `tabla, pag_impresa, pag_pdf, dd_borehole_id, interval_raw, from_m, to_m, length_m, li_mg_l, k_mg_l, mg_mg_l, h3bo3_mg_l, so4_mg_l, mg_li_orig, mg_li_recalc, nota`.
- `dd_borehole_id` es el nombre de la primera columna **tal como la titula la fuente ("DD Borehole ID")**; en la practica contiene el nombre de piezometro (DL-001, ML-001, ...) mas dos boreholes (`DD19D-001`, `DD19D-PE09`), por eso el cruce con 10.6 es contra `piezometer_name`.
- Typo de origen en la cabecera: **"Lenth (m)"** -> columna `length_m`. La cabecera "From - To (m)" se parsea de `interval_raw` (`0-100`) a `from_m`/`to_m`.
- Convencion numerica: punto decimal; concentraciones en mg/L tal como vienen (sin redondeos; p. ej. `545.05`, `1458.05` conservados). `mg_li_orig` = tal cual el origen (1 decimal). `mg_li_recalc` = Mg/Li con 2 decimales.
- Controles:
  - `from_m < to_m`: 63/63 OK.
  - `length_m == to_m - from_m`: 63/63 OK.
  - `mg_li_orig` vs `mg_mg_l/li_mg_l` redondeado a 1 decimal: **63/63 coinciden** (maxima diferencia orig vs recalc a 2 decimales = 0.05, todo redondeo).
  - Continuidad de intervalos por piezometro: contiguos salvo `DD19D-PE09` (286-301 y 325-340, son tramos puntuales de 15 m, no un hueco de error).
- Rarezas del origen:
  - `DL-001` 300-400 y 400-450 tienen **el mismo Mg (1230.1)** con Li/K/otros distintos: posible copia, no corregida.
  - `DL-001` incluye una fila con borehole `DD19D-001` (450-632, 182 m): continua la serie de DL-001 (0-450) hasta 632 m bajo otro nombre (borehole DD19D-001, cuyas coordenadas en 10.6 casi coinciden con DL-001/ML-001).
  - Los intervalos de `DL-010` parten en 0-19 / 19-250 (no multiples de 50/100).
  - Los ML-001/002 solo tienen 3 intervalos de 50 m (0-150). Solo ML-001 y ML-002 de la serie ML/SL tienen datos.
- Cruce con 10.6 (por nombre de piezometro):
  - Nombre exacto: 5 de los 18 de 10.7 **no existen** tal cual en 10.6: `DL-003B`, `DL-004B`, `DL-008`, `DL-009`, `DL-010` (10.6 los escribe `DL-003 B`, `DL-004 B`, `DL-08`, `DL-09`, `DL-10`). Anotado en `nota` de esas filas.
  - Normalizando (prefijo + numero con ceros a 3 digitos + sufijo B, sin espacios): **0** de 10.7 sin correspondencia en 10.6 (13 de los 18 ya coincidian; los 5 anteriores solo difieren en formato).
  - Al reves: de los 49 de 10.6 (44 nombres distintos, contando `Cemented` y `Abandoned` como 2 "nombres"), **26 nombres normalizados no aparecen en 10.7**: todos los `SL-*` (SL-001, 002, 004, 004B, 006, 007, 009, 010, 013, 014), `ML-003..014` (12), `DL-003`, `DL-004`, y los valores `Cemented`/`Abandoned` (no son piezometros). Es decir, 10.7 cubre 14 DL (todos salvo `DL-003` y `DL-004` sin B; si cubre `DL-003B`/`DL-004B`), `ML-001`/`ML-002` y los dos boreholes DD19D (18 en total); en comparacion exacta son 31 nombres distintos de 10.6 que no estan en 10.7 (incluye los 2 textos de estado).
  - `DD19D-001` y `DD19D-PE09` existen en ambas tablas.

## Notas generales
- Typos de cabecera de origen conservados semanticamente: "Plataform" (platform), "Lenth" (length).

---

## Status grupo tablas 10.8, 10.9

Metodo: pdfplumber `extract_words` con coordenadas (columnas por rango x; filas por bandas de intervalos de perforacion) + `extract_tables` como contraste + verificacion visual contra PNG de cada pagina (PDF 178-182 y 185). Offset confirmado: pag_pdf = pag_impresa + 16 (178/162 ... 182/166, 185/169).

| Tabla | Archivo | Filas | Pendientes |
|---|---|---|---|
| 10.8 (pozos de produccion, PDF 178-182) | t10_8.csv | 38 pozos | 10 filas en `pendientes_t10_8.csv` (todas SI incluidas en el CSV, tal cual origen; ver abajo) |
| 10.8 (intervalos de perforacion, derivado) | t10_8_intervals.csv | 111 intervalos | 0 |
| 10.9 (PDF 185) | t10_9.csv | 8 | 1 fila en `pendientes_t10_9.csv` (incluida en el CSV) |

`t10_8_intervals.csv` es un archivo auxiliar: una fila por intervalo de la columna "Drilling Diameter" (diametro de broca como decimal, from_m, to_m), parseado del mismo texto crudo. No se alinea con casing/screen (esas celdas a veces cubren varios intervalos).

Conteo por pagina (T10.8): PDF 178 / imp. 162 = 10 pozos (23 intervalos); PDF 179 / imp. 163 = 7 pozos nuevos + la continuacion de WR-10 (23 intervalos); PDF 180 / imp. 164 = 7; PDF 181 / imp. 165 = 7; PDF 182 / imp. 166 = 7. Total 38, nombres unicos (38 distintos). PDF 183 / imp. 167 NO contiene filas: es la Figura 10.4 (ubicacion de pozos de bombeo).
Cortes de pagina: solo uno, WR-10 (ultima fila de PDF 178). Sus intervalos 2 y 3 (18" 23-190 m; 13 1/2" 190-355 m), los largos de casing/screen de esos intervalos y el material de tuberia ciega (Carbon Steel) quedan en las primeras lineas sin nombre de PDF 179. Se unieron en UNA sola fila (pag_pdf=178, nota con la continuacion). Las demas filas terminan completas dentro de su pagina (las dos paginas 180 y 181 terminan con una fila vacia de relleno en el origen; no se extrajo nada de ahi). Sin filas perdidas ni duplicadas.

## Estructura de t10_8.csv (una fila por pozo)
Columnas: tabla, pag_impresa, pag_pdf, pumping_well, year, total_depth_m, x_raw, y_raw, easting, northing, drilling_method, drilling_diameter_inches, total_length_casing_inserted_m, total_length_screen_casing_inserted_m, solid_casing, screen_casing, nota.
- Las tres columnas de celdas multilinea (`drilling_diameter_inches`, `total_length_casing_inserted_m`, `total_length_screen_casing_inserted_m`) quedan como TEXTO CRUDO con las lineas separadas por ` | `. Cuando las celdas casing/screen estan alineadas a los intervalos de perforacion (pozos con 3-4 intervalos), cada ranura ` | ` corresponde al intervalo del mismo numero; una celda vacia en origen = ranura vacia (p.ej. el primer intervalo no tiene largo de screen: ` | 10" (99.0 m) | 6" (187.0 m)`). En PB-03A, PB-04, PB-06A, W18-05 y W-04A el origen tiene UNA celda combinada para 2 intervalos: se guarda un solo valor, sin alinear (nota lo dice).
- Texto con unidades (p.ej. `8" (122.9 m)`): NO se normalizo a numero, para no inventar la alineacion; los valores numericos estan en el texto crudo. Si se necesita numerico, parsear con el patron `D" (L m)`.
- solid_casing / screen_casing: texto tal cual ("Carbon Steel" etc.).
- Para WR-10 el `solid_casing` ("Carbon Steel") viene de la continuacion en PDF 179 y `screen_casing` ("Stainless Steel") de PDF 178.

## Convenciones numericas
- 10.8: sin separador de miles ni coma en ningun valor. total_depth_m y metros con punto decimal (386.6, 434.1, 338.6, 571.2); year entero. Coordenadas enteras en metros.
- 10.8 coordenadas: encabezado del origen X, Y. `x_raw`, `y_raw` = columnas tal cual (X primero, Y segundo). `easting`/`northing` decididos SOLO por magnitud (valor ~3.4e6 = easting, ~7.4e6 = northing), con nota cuando se intercambia.
- 10.9: el origen usa COMA decimal ("41,07", "493,7", "706,8", "72,11", "700,23", "652,83"): normalizado a punto. La coma solo aparece con 1-2 decimales detras (nunca 3 digitos), asi que no es separador de miles; sin ambiguedades. Coordenadas enteras sin separador. Enteros del origen se dejan enteros.
- 10.9: diametro del filtro, el origen escribe `2''` y `8'', 12''` (dos apostrofes); se normaliza a `2"` y `8", 12"` en `screen_diameter_inches` (texto).
- Faltantes en origen = vacio (piezometer_name en 6 de 8 filas de 10.9; celdas de screen vacias en 10.8).

## Orientacion X/Y
- 10.8: **TODAS las 38 filas estan invertidas** (X = norte ~7.37-7.40e6, Y = este ~3.42-3.43e6; incluso W-16 con Y=3227420). Ninguna tiene orientacion normal. En todas la nota dice "x/y invertidos en origen". Es decir, no es un error por fila: la cabecera de la tabla esta mal (X e Y rotulados al reves) para toda la tabla.
- 10.9: **0 de 8 invertidas**: X ~3.42e6 (este), Y ~7.36e6 (norte), orientacion correcta. easting=x_raw, northing=y_raw, sin nota.

## Validacion cruzada de coordenadas
Contra Apendice 1 Tabla 1 (PDF 442; la tabla ocupa PDF 442-443, solo pozos de exploracion; NO esta en PDF 441, que es texto de calificaciones) y Tabla 15.3 (PDF 283; la parte de PDF 282 tiene las coordenadas desalineadas de los nombres y solo se uso de pista).
- Apendice 1 T1, por nombre (easting/northing de T10.8 ya normalizados):
  - Coinciden exacto (dE=0, dN=0): W17-06, W18-05, W18-06, W11-06, W18-23 (y sus profundidades 455, 270, 460, 434, 484).
  - Coinciden con diferencia sub-metrica por decimales del Apendice (que da 2 decimales): PB-03A (dE -0.69, dN -0.18), PB-04 (-0.53, -0.24), PB-06A (0.00, -1.48).
  - **NO coincide: W-04A** (T10.8: 3423300 / 7379360; Apendice 1 "W04-A": 3422492 / 7379474; dE=+808 m, dN=-114 m). Misma profundidad 478 m. Pendiente: no se sabe cual es el correcto.
  - **Profundidades de PB-03A / PB-04 / PB-06A desfasadas**: T10.8 da 204 / 201 / 305; Apendice 1 da PB-01=204, PB-03A=201, PB-04=305, PB-06A=194. Los ultimos intervalos de perforacion de T10.8 (205 / 305 / 194) concuerdan con el Apendice, no con su propia columna de profundidad: probable desfase de una fila en la columna Total Depth de T10.8 (PB-01 no esta en T10.8). Valores extraidos tal cual; anotado y a pendientes.
- Tabla 15.3 (PDF 283), por cercania (nombres distintos): WR-28 ~ PE-11 (dE +5 m, dN 0); W10-04 ~ DDH-04A (dE +1, dN 0); W-8 ~ PE-15 (dE 0, dN 0). Son coincidencias de coordenada (mismo sitio con otro nombre), no hay coincidencia de nombre. Otro candidato (PB-03A ~ PF-3B a 41 m) se descarto como casual.
- W-16 (T10.8, y_raw=3227420 -> easting fuera de rango): el Apendice 2 Tabla 4 (PDF 446, tabla con columnas desalineadas por pdftotext) lista W-16 con este 3427420, consistente con un typo (3227420 -> 3427420). NO se corrigio; queda 3227420 en y_raw/easting con nota y pendiente.
- Tabla 10.9: ninguna de sus 8 perforaciones DD19D coincide con coordenadas de 15.3 ni del Apendice 1 (la mas cercana a 1.0 km); nada que cruzar.

## Controles de coherencia
- 10.8: 38 pozos; 38 nombres unicos; conteo por pagina 10+7+7+7+7 = 38 (WR-10 contado una vez). Todos los intervalos de perforacion son contiguos (to_k = from_{k+1}) salvo 2 (abajo). Ultimo intervalo = total_depth_m en 26 de 38 pozos; en 12 difiere (ver abajo). Todos los easting en 3.419e6-3.43e6 salvo W-16.
- 10.9: 8 filas = 8 del origen; 8/8 con screen_top < screen_base; 7/8 con screen_base <= total_depth.
- Verificacion visual: las 6 paginas (PDF 178-182, 185) contra PNG.

## Rarezas del origen (todo conservado tal cual, anotado en `nota` y/o a pendientes)
10.8
- Encabezado X/Y invertido en toda la tabla (ver arriba).
- W-16: y_raw 3227420 (probable typo de 3427420).
- Coordenadas identicas en W-7 (PDF 181) y W-10 (PDF 182): 7375500 / 3421500 (dos pozos distintos, construidos 2020 y 2021, con otras profundidades). Anotado.
- Ultimo intervalo de perforacion != total_depth_m: PB-03A (205/204), PB-04 (305/201), PB-06A (194/305), W18-05 (278/270), W18-06 (450/460), W18-23 (486/484), WR-10 (355/445), WR-21 (480/493), W-2 (470/475), W-14 (607.7/494), W-7 (561.81/565), W-10 (490/493); W-12 coincide (530) una vez incluido el intervalo 10 5/8" (499-530).
- W09-06: intervalo 3 "12 1/4" (20-355 m)": inicio 20 != fin del previo (200). W-42: intervalo 2 "17" (12-245 m)": inicio 12 != fin del previo (32).
- W-6: la celda "Total length of screen casing inserted" del intervalo 1 contiene `27" (0-24 m)` (parece texto de intervalo de perforacion en la columna equivocada).
- W-15: sin largo de screen para el intervalo 2 (10"), vacio en origen. Los intervalos 1 de todos los pozos con 3+ intervalos tienen casing 20" sin largo ni screen (normal en el origen).
- W-12 y W-31 tienen un 4to intervalo sin casing/screen (10 5/8" 499-530 m; 12 1/4" 645.4-650 m).
- Los caracteres de pulgada en algunas celdas son comillas tipograficas (”, p.ej. `10 5/8”`); normalizadas a `"`. Las fracciones (1/4, 1/2, 5/8) van como superindice en el PDF; pdfplumber las da con un espacio ("13 1/4 ""); se reunieron a `13 1/4"`.
- pdftotext -layout desordena esta tabla: los nombres/anios/profundidades salen separados del resto de cada fila (y la continuacion de WR-10 aparece colada en PDF 179). Por eso se reconstruyo con coordenadas.
10.9
- Los IDs son `DD19D-xx` (no `DDH19D`). `DD19D-06` tiene piezometro `DD19D-06 BIS`; a la inversa `DD19D-26 BIS` tiene piezometro `DD19D-26` (el BIS esta en columnas distintas). Anotado.
- DD19D-13: screen_base 537 m > total_depth 465 m (inconsistencia del origen; fila conservada y a pendientes).
- El encabezado del origen dice "Plataform" (sic); la columna se llama `plataform`. La columna Plataform repite el borehole ID.
- El titulo habla de 2022 y 2024 pero la tabla no tiene columna de ano.
- Unidades: total depth en m; screen top/base rotulados "mbtw" en el origen (no se interpreta la sigla), nombres de columna `screen_top_mbtw`, `screen_base_mbtw`.

---

## Status: coordinate tables (T15.3, A1-T1, A2-T4, T16.1)

Source: LAC NI 43-101 report (Jan 8 2025). PDF page = printed page + 16 (checked on every table).
Method: pdfplumber `extract_words` / `extract_tables` (pdftotext -layout scrambled rows in T15.3, A1-T1 and A2-T4), verified against the page images.

## Files and rows

| File | Table | Printed pages | PDF pages | Rows |
|---|---|---|---|---|
| `t15_3.csv` | Table 15.3 Steady-state model residuals | 266-267 | 282-283 | 27 (all rows of the table) |
| `tA1_1.csv` | Appendix 1, Table 1 Location and construction info | 426-427 | 442-443 (NOT 441-442) | 12 |
| `tA2.csv` | Appendix 2, Table 4 Updated Mineral Reserve Estimate (OS4, 56 wells) | 430-431 | 446-447 | 56 (29 + 27) |
| `t16_1.csv` | Table 16.1 Infill producing wells 2024 | 283 | 299 | 3 |
| `pendientes_coords.csv` | doubtful rows of all four | | | 5 entries |

Appendix 2 contains only one table with wells/XY (Table 4, `tabla_apendice` = 4). PDF 448 is Figure A1 (no data). Appendix 1 Tables 2 and 3 (PDF 444-445) have no coordinates or elevations of wells, not extracted.

## Conventions
- UTF-8, comma, dot decimal, no index, written with pandas; all CSVs re-read with pandas without errors.
- First columns `tabla, pag_impresa, pag_pdf` (real page of each row). Missing = empty.
- `x_raw`/`y_raw` = text of the Easting/Northing columns as printed (e.g. `3419220.00`); `easting_m`/`northing_m` = numeric by magnitude (easting ~3.4e6, northing ~7.3-7.4e6). **No X/Y swap was needed in any table**: all four print Easting/East/X first and Northing/North/Y second, and all values fall in the expected ranges (E 3418305-3433225, N 7343262-7407612).
- Number convention in all four tables: decimal point, no thousands separator (US style). No ambiguity found. Zero-valued pumping (`0`) is kept as 0.
- T15.3: `residual_m` numeric (asterisk removed), `residual_raw` text as printed (`1.29*` for DDH-17). Source column `source`: `Exar` or `Adv. Lithium, 2018`. "Nivel freático" = `observed_gw_elev_masl` (observed groundwater elevation); `computed_gw_elev_masl` is the model value. Elevations in masl (not depth).
- A1-T1: `land_surface_elev_masl` (m amsl) numeric, `land_surface_elev_raw` as printed; depths in m (bls) as printed; `hsu_raw` = HSU cell text joined with single spaces (multi-line cells are NOT split, see pendientes).
- A2-T4: all columns of the table kept (screen top/bottom masl, start/end year, pumping L/s year 1 and years 2-40, predicted drawdown m and Li concentration mg/L at years 1/10/20/30/40). `top_model_masl` = "Top of Model (masl)". IDs exactly as printed.
- T16.1: `contractor` = "Wichi Toledo" (two printed lines in one cell, joined with a space).

### `fuente_z_raw` (A1-T1)
The table prints the year constructed per well and one footnote `a)` (not tied to any marker in the table). Verbatim note of the report:

> a) coordinates of wells constructed after 2011 based on DEM; wells constructed in 2010 and 2011 are based on reported differential GPS survey (Posgar 94)

Plus "NA = not available". `fuente_z_raw` holds, per row, the clause of the note that applies by `year_constructed`: <=2011 -> "wells constructed in 2010 and 2011 are based on reported differential GPS survey (Posgar 94)"; >2011 -> "coordinates of wells constructed after 2011 based on DEM". Selection by year is mine; the text is verbatim. The note speaks of coordinates, it does not mention the elevation explicitly. Rows 2010-2011: PB-01, PB-03A, PB-04, PB-06A, PB-I; 2018-2019: the other 7.

## Well IDs per table (as written)
- **T15.3 (27)**: SL-001, SL-002, SL-004B, SL-006, SL-007, SL-009, SL-010, SL-13, SL-014, PE-11, DDH-07, DDH-09, DDH-02, PT-1A, PF-3B, PF-1B, PT-2, DDH-04A, PE-15, DDH-15, DDH-05, PE-08, DDH-17, CAU02D, CAU03D, CAU06R, CAU12D. The 14 points of interest (PE-08, PE-11, PE-15, DDH-02/04A/05/07/09/15/17, CAU02D/03D/06R/12D) are all present; the rest (SL-*, PT-*, PF-*) were also extracted.
- **A1-T1 (12)**: PB-01, PB-03A, PB-04, PB-06A, PB-I, W17-06, W18-05, W18-06, W04-A, W11-06, W18-23, CW-62.
- **A2-T4 (56)**: PB-3A, PB4, PB-6A, W18-05, W17-06, W11-06, W18-06, W-02B, W-04A, WR-21, WR-10, WR-07, WR-23, WR-3, W17-12, W18-23, WR-24, W09-01, W10-04, WR-28, W09-06, W-1, W-10, W-11, W-12, W-13, W-14, W-15, W-16 (PDF 446); W-17, W-18, W-19, W-2, W-20, W-21, W-22, W-23, W-24, W-25, W-26, W-27, W-28, W-29, W-3, W-30, W-31, W-32, W-4, W-5, W-6, W-7, W-8, W-9, R64, R66, R67 (PDF 447).
- **T16.1 (3)**: Pozo 44 (platform W-30), Pozo 45 (W-28), Pozo 46 (W-29).

## Checks done
- T15.3: residual = observed - computed re-computed for the 27 rows: 0 mismatches (to 0.01), including DDH-17 (1.29). The report text says 27 monitoring locations: 27 rows.
- A1-T1: screen top < bottom <= total depth in all 12 rows.
- A2-T4: 56 rows = "OS4 (56 Wells)" in the table header; each row has the 20 expected fields; screen top < top of model and bottom < top in all rows; no duplicated IDs.
- T16.1 and the three tables above compared with the page image: values match.
- Cross-check A1-T1 vs A2-T4 (9 wells in common, W04-A/W-04A checked by hand): E/N/Z agree except where noted below.

## Oddities
- **DDH-17** (T15.3): Y=7343262, 20 km south of the next well (PE-08, 7363500); observed 3960.71 masl vs ~3937 elsewhere; marked `*` = flowing well. Kept and flagged in `nota`. Footnote verbatim: "* Reported as flowing well; the observed value was assumed to be greater than land surface and calibrated in Groundwater Vistas using a "censoring" target, where a residual of 0 is given if the simulated value is greater than the observed." (the report prints residual 1.29 anyway).
- **ID `SL-13`** (T15.3): other SL ids have 3 digits (SL-009, SL-010, SL-014). Kept.
- **CAU rows source** (T15.3): the "Adv. Lithium, 2018" cells are offset vertically from their rows in the PDF; assigned 1:1 in order (pendientes).
- **IDs differ between appendices**: A1 `PB-03A`, `PB-04`, `PB-06A`, `W04-A` = A2 `PB-3A`, `PB4`, `PB-6A`, `W-04A` (same coordinates). A1 `PB-I` (letter I, probably PB-1; kept).
- **PB-06A / PB-6A northing**: 7377555.48 (A1) vs 7377554 (A2): 1.48 m. The other shared wells differ by <1 m (A2 looks truncated). Both kept; in pendientes and in `nota`.
- A1 `Land Surface Elevation` vs A2 `Top of Model`: not the same quantity; differ by up to 0.56 m for PB wells, identical for W wells.
- **CW-62** (A1-T1): elevation "NA" -> empty; the well is not in A2-T4.
- A1-T1 `hsu_raw` of W04-A, W11-06, W18-23: several HSUs in one justified cell, not split.
- A2-T4 table header says "Pumping (L/s) Years 2 through 40"; stored as `pumping_years2_40_lps`.
- T16.1: location says "Olaroz" in the table, platforms W-28/29/30; Pozo 44-46 are not in A2-T4.
