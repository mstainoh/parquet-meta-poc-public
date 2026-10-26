# Visor de datos (`index.html`)

> Cómo funciona el visor: qué hace, cómo se usa y cómo está armado. Describe el código de
> [`index.html`](../../index.html); las decisiones detrás están en
> [`ADR.md`](../ADR/ADR.md) (ADR-006, 007, 014, 018 y 019). Qué es el repo y cómo se
> arman los artefactos que el visor carga: [`README.md`](../../README.md).

## 1. Qué es

Un visor de tablas Parquet con editor SQL, entregado como **un solo archivo**,
`index.html`: estilos, markup y un único `<script type="module">`. No hay build, ni
`package.json`, ni backend. Se abre de dos formas, y las dos tienen que seguir andando:

- **doble clic** (`file://`), o
- servido por cualquier servidor estático (p. ej. `python -m http.server`).

Se prueba en Chrome/Edge. El visor no depende del paquete `meta_tools`: lee los archivos
que este produce (fichas e índice), pero no importa nada de él.

**Por qué las dependencias vienen de un CDN (ADR-006).** Chrome bloquea los imports de
módulos locales relativos sobre `file://`, pero no los imports cross-origin a un CDN.
Traer las librerías de jsDelivr es lo que mantiene vivo el doble clic: bajarlas al repo
o partir el script en módulos locales lo rompe. El costo: la primera carga necesita red.

**Por qué todo queda en el navegador (ADR-007).** Los archivos se leen en memoria y se
consultan con DuckDB dentro del navegador. No hay servidor que reciba datos: abrir un
archivo no es un problema de despliegue ni de custodia del dato.

## 2. Stack

| Librería | Versión cargada | Para qué | Cómo se carga |
|---|---|---|---|
| DuckDB-Wasm (`@duckdb/duckdb-wasm`) | `1.32.0` | motor SQL, en un Web Worker | módulo ES (`+esm`) desde jsDelivr |
| SheetJS (`xlsx`) | 0.18.5 | exportar a Excel | `<script>` clásico |
| Leaflet | 1.9.4 (JS y CSS) | mapa | `<script>` clásico + hoja de estilo |
| Chart.js | 4.4.4 | gráficos | `<script>` clásico |

Las tipografías (Inter, JetBrains Mono) vienen de Google Fonts. DuckDB-Wasm elige su
bundle con `selectBundle(getJsDelivrBundles())` y el worker se crea desde un `Blob` que
hace `importScripts` del worker del CDN: así se puede levantar un worker cross-origin
también desde `file://`. El motor se inicializa recién al cargar el primer archivo o el
índice.

## 3. Uso

### 3.1 Cargar archivos

La barra lateral tiene cuatro botones:

- **Elegir carpeta**: carga todos los `.parquet`, `.geojson` y `.json` de la carpeta,
  subcarpetas incluidas (`<input webkitdirectory>`). Un `.json` que no es un
  `FeatureCollection` se omite, con una línea de aviso. En la misma selección entran los
  fondos offline (`basemap_<nombre>.json` + su imagen `.png`/`.jpg`, ver §3.5).
- **Elegir archivos**: lo mismo, con archivos sueltos.
- **Cargar metadata** y **Cargar índice**: ver §4. Son botones aparte a propósito: cargar
  tablas no arrastra metadata, y cargar metadata no registra tablas.

Cada archivo deja una línea en el panel *Archivos* (filas o features leídas, o el error).
Las tablas aparecen en *Tablas cargadas* con su cantidad de filas; un clic en una escribe
`SELECT * FROM "<tabla>" LIMIT 100;` en el editor (no la corre).

### 3.2 De archivo a vista SQL

- **Parquet**: el archivo entero se lee en memoria, se registra en DuckDB
  (`registerFileBuffer`) y se expone como vista: `CREATE OR REPLACE VIEW "<tabla>" AS
  SELECT * FROM parquet_scan(...)`.
- **GeoJSON** (`FeatureCollection`, en `.geojson` o `.json`): queda como *capa geo* para el mapa, indexada por el
  id de cada feature (`properties.id` / `ID` / `Id`, o el `id` del feature). Además, sus
  propiedades se exponen como vista SQL (vía NDJSON y `read_json_auto`), con una columna
  `__geom` que dice el tipo de geometría. La geometría no entra a DuckDB: no hay extensión
  espacial ni geoprocesamiento en el navegador.

El nombre de la vista sale del nombre del archivo (`sanitizeTableName`): se quita la
extensión, todo carácter fuera de `[a-zA-Z0-9_]` pasa a `_`, y si empieza con un dígito
se le antepone `t_`. Por ejemplo, `water-levels 2024.parquet` → `water_levels_2024` y
`2024_levels.parquet` → `t_2024_levels`. La carpeta y la extensión no cuentan: dos
archivos con el mismo nombre en subcarpetas distintas, o un parquet y un GeoJSON con el
mismo nombre, terminan en la misma vista, y gana el último registrado (los GeoJSON se
registran después de los parquet). El choque no se resuelve, pero no pasa en silencio: la
línea de estado lista los nombres repetidos que se pisaron, para corregirlos en el origen.
Cada archivo se identifica por su ruta dentro de la carpeta elegida, así que volver a
cargar el mismo archivo no avisa. Con **Elegir archivos** no hay ruta, solo el nombre: dos
homónimos elegidos en tandas distintas desde carpetas distintas se pisan sin aviso.

### 3.3 Editor SQL

- Se corre con **Ejecutar** o `Ctrl/Cmd + Enter`.
- **Solo una consulta de lectura**: el texto tiene que empezar con `SELECT` o `WITH` y
  tener a lo sumo un `;`. Es un filtro de conveniencia por regex, no un sandbox.
- **Pegado tolerante**: al pegar, si el texto trae el SQL entre fences de markdown o con
  prosa alrededor (la respuesta típica de un LLM), el visor extrae solo el SQL. Si no
  encuentra `SELECT`/`WITH`, pega tal cual y avisa.
- **◀ / ▶** recorren las consultas corridas en la sesión (en memoria: se pierden al
  recargar).
- **Guardar .sql** guarda el contenido del editor como archivo. En Chrome/Edge abre el
  diálogo "Guardar como" (se elige nombre y carpeta, sugiere `consulta.sql`); en otros
  navegadores descarga `consulta.sql` directo.
- **Cargar .sql** reemplaza el contenido del editor con un archivo `.sql` (hasta 1 MB). No lo
  ejecuta: se revisa y se pulsa Ejecutar.
- **Ejemplos**: un desplegable de consultas de ejemplo, que define quien despliega el
  visor según sus tablas.
- **Comentario + Guardar** anota la consulta del editor con un comentario libre en un
  log local (`localStorage` del navegador, hasta 200 entradas). **Exportar historial** lo
  baja como CSV (`timestamp, comentario, sql`). Sirve para documentar el uso real del
  visor; no se envía a ningún lado.

### 3.4 Resultados y exportación

El resultado llega de DuckDB en formato Arrow y se sanitiza antes de mostrarlo: `BigInt`
pasa a número (o a texto si no entra en un entero seguro), fechas y timestamps a texto
ISO 8601 en UTC, y los valores anidados a JSON. La línea de estado dice cuántas filas
devolvió y en cuánto tiempo.

- La tabla **muestra hasta 500 filas** (`MAX_DISPLAY_ROWS`). El tope es de la vista, no
  del dato: **las exportaciones operan sobre el resultado completo**.
- **Exportar CSV**: vuelve a correr la consulta con el `COPY (...) TO` nativo de DuckDB
  (encabezado, separador `,`) y descarga el archivo.
- **Exportar Excel**: SheetJS (`XLSX.writeFile`) sobre las filas ya traídas, en una hoja
  `Resultado`. DuckDB-Wasm no escribe `.xlsx`.

### 3.5 Mapa

La pestaña **Mapa** se habilita si el resultado se puede ubicar, de una de dos formas:

- **Puntos por lat/lon**: columnas numéricas con nombres como `lat`/`latitude`/`latitud`
  y `lon`/`lng`/`longitude`/`longitud` (sin distinguir mayúsculas). Se asume WGS84.
- **Join contra una capa GeoJSON**: una columna cuyos valores coinciden con los ids de
  una capa cargada en al menos la mitad de una muestra de 200 filas (una columna llamada
  `id` tiene prioridad). Cada fila se dibuja con la geometría de su feature: punto, línea
  o polígono. Ej.: un resultado de `TBL_WATER_LEVELS` con `well_id = 'W-999'` se pinta
  sobre el feature `W-999` de una capa `wells.geojson`.

Controles:

- **Colorear por** cualquier columna: numérica → escala continua (seis paletas, **Min** /
  **Max** fijables); otra → colores categóricos, con leyenda.
- **Escalar tamaño** según el valor; un popup por elemento muestra la fila completa.
- **Mes**: si el resultado tiene una columna de fecha con dos meses distintos o más,
  aparece un deslizador para filtrar por mes. Sin Min/Max fijos, la escala se recalcula
  con cada mes.
- **Capas de contexto**: dibuja en gris las otras capas GeoJSON cargadas, como
  referencia.
- Se dibujan hasta 5000 elementos (`MAX_MAP_FEATURES`); la leyenda dice cuántos se
  mostraron y cuántos quedaron sin geometría.

**Fondos** (ADR-018: sin clave de API y con uso comercial permitido, con dos excepciones
aceptadas): Sentinel-2 cloudless 2016 (EOX, CC BY 4.0), satélite de Esri, OpenTopoMap,
la capa base de un organismo cartográfico nacional, y **Sin fondo**. También admite un
**fondo offline**: un `basemap_<nombre>.json` con `west`, `south`, `east`, `north` e
`image_file`, cargado en la misma selección que su imagen (`.png`/`.jpg`). Se dibuja como
imagen sobre esos límites y pasa a ser el fondo por defecto.

### 3.6 XPlot, Barras y Tiempo

- **XPlot** (con dos columnas numéricas o más): dispersión de X contra Y, coloreable por
  cualquier columna (colores categóricos). Si la columna de color es numérica o de fecha,
  aparece la casilla **escala continua**: la pinta con un gradiente, con su leyenda de
  mínimo a máximo.
- **Barras** (con al menos una columna numérica): una barra por categoría de X (cualquier
  columna) con el valor de Y, coloreable por cualquier columna (una serie por valor) y con
  casilla **apilado**. No agrega: pinta la consulta tal cual. Si hay filas repetidas en
  (X, color) conserva la primera y avisa; la agregación va en el SQL (`GROUP BY`). Tope de
  60 categorías: las primeras en el orden del resultado (ordenar en el SQL), con aviso.
  Las filas con Y vacío o no numérico se saltean.
- **Tiempo** (con al menos una columna numérica): el eje X es una columna de fecha o
  numérica, con límites **Desde** / **Hasta**. Dos modos: *Categorías* (barras de un
  valor, separadas por una columna) y *Comparar variables* (hasta dos variables, cada una
  como barra, línea o punto; la segunda en un eje Y a la derecha).

## 4. Metadata: fichas e índice

El visor muestra la metadata que produce el pipeline
([`etl_strategy.md`](../model/etl_strategy.md)); el vocabulario está en
[`metadata_model.md`](../model/metadata_model.md).

- **Cargar metadata** elige una carpeta. Cada `.yaml`/`.yml` que encuentre es la **ficha**
  de una tabla (el *schedule*: `keys` + `semantics` + `inspect` + `file_columns`), y se
  identifica por el nombre del archivo sin extensión: si dos fuentes tienen una tabla con
  el mismo nombre (`<fuente>/<TABLA>.yaml`), la última ficha leída pisa a la otra, sin
  aviso. El panel *Fichas de metadata* tiene
  un selector por tabla y muestra la ficha como texto, sin parsearla ni validarla. Los JSON
  de estadísticas (`mechanical`) no se leen.
- **Cargar índice** elige un `.txt` separado por `|`, con encabezado: el índice plano que
  escribe el ETL de metadata, con cualquier nombre. Se registra como la vista
  **`table_index`**, una fila por tabla, consultable con SQL como cualquier otra.

**La auditoría nunca se lee (decisión de diseño).** Los `.yaml` cuya ruta dentro de la
carpeta elegida contiene `99_audit` se saltean a propósito. La auditoría (`provenance`
completo: YAML de origen, usuario, commit) no se muestra al usuario ni viaja al agente
(ADR-014). Además, ficha y auditoría de una tabla se llaman igual (`<TABLA>.yaml`): sin el
salto, una pisaría a la otra. Para que quede oculta, el `output.audit` del ETL de metadata
tiene que escribir en una carpeta llamada `99_audit` (o dentro de una).

## 5. El agente

El visor **no llama a ningún agente**: no hace pedidos de red con datos ni con metadata.
El agente trabaja aparte, con la metadata por capas de ADR-014. Qué artefacto entra a su
contexto, y cuándo, está en la tabla de artefactos del
[`README.md`](../../README.md#artifacts-and-who-reads-them).

El flujo en el visor:

1. El usuario le hace la pregunta al agente y recibe el SQL.
2. Lo pega en el editor; el pegado tolerante descarta la prosa y los fences.
3. La consulta corre en local (ADR-007).
4. Si falla, al agente vuelve solo el mensaje de error, **nunca filas**.

Las fichas y el índice cargados en el visor sirven para que el usuario vea lo mismo que
lee el agente. La vía API de ADR-014, en la que el propio visor arma las dos vueltas, no
está implementada en `index.html`.

## 6. Qué sale del navegador

- **Nunca**: las filas, los archivos cargados, la metadata, las consultas ni el log local.
- **Sí**: los pedidos al CDN (librerías, bundle de DuckDB-Wasm, tipografías) y, con un
  fondo online, los pedidos de tiles al proveedor del fondo, que así se entera de qué zona
  se está mirando. **Sin fondo** y el fondo offline no hacen ningún pedido.

Lo que llega al agente no pasa por el visor: lo comparte el usuario, o el despliegue, por
fuera. Ahí rige la misma frontera (ADR-019): **las filas nunca salen**; la metadata sí
puede salir, estadísticas incluidas, aunque lleven valores reales (`min_max`: mínimos y
máximos; `fk_orphans`: valores huérfanos de FK). Si esos valores pueden salir en un
despliegue concreto lo decide quien despliega, no el paquete. Qué artefacto lleva qué
valores: *Privacy* en el [`README.md`](../../README.md#privacy).

## 7. Para desarrolladores

El `<script type="module">` está ordenado por bloques (separadores `// ── … ──`):

| Bloque | Funciones principales |
|---|---|
| Motor y carga | `initDuckDB`, `sanitizeTableName`, `registerParquetFile`, `registerGeoJsonFile`, `handleFileSelection` |
| Paneles | `dragSplitter` (divisores arrastrables, doble clic reinicia), secciones plegables; sin estado persistido |
| Consulta | `isSelectOnlySql`, `runQuery`, `sanitizeValue`, `isDateField` (tipos Arrow Date/Timestamp), `renderResults` |
| Mapa | `detectGeometry`, `prepareMap`, `drawMap`, `BASEMAPS`, `setBasemap`, `registerLocalBasemap`, `buildColorFn` |
| XPlot / Barras / Tiempo | `prepareChart`, `drawChart`, `prepareBars`, `drawBars`, `prepareTime`, `drawTime` |
| Export | `exportCsv` (`COPY`), `exportXlsx` (SheetJS) |
| Editor | `extractSqlFromPaste`, historial ◀/▶, log local (`saveQueryLogEntry`, `exportQueryLog`), `EXAMPLES` |
| Metadata | `handleMetadataSelection` (fichas, salto de `99_audit`), `handleIndexSelection` (`table_index`) |

Al cambiarlo:

- No partir el script en módulos locales ni vendorear librerías (ADR-006). Una librería
  nueva va por CDN: como módulo ES si se publica así, si no como `<script>` clásico.
- Nada de backend ni de enviar datos (ADR-007).
- Un fondo nuevo se evalúa con los criterios de ADR-018.
- No hay tests automáticos: se verifica a mano en el navegador, por `file://` y servido.
  Mínimo: cargar un `.parquet`, correr una consulta y probar las dos exportaciones.

## 8. Límites y fuera de alcance

- Sin persistencia: al recargar la página hay que volver a elegir los archivos. Solo el
  log local sobrevive, en el `localStorage` de ese navegador.
- Cada Parquet se lee entero en memoria: el tamaño lo limita el navegador.
- La primera carga necesita red (CDN), y el visor depende de que el CDN siga sirviendo
  las versiones fijadas (costo aceptado en ADR-006).
- Solo lectura: una consulta `SELECT`/`WITH` por vez.
- Tabla hasta 500 filas y mapa hasta 5000 elementos (las exportaciones no tienen tope).
- Sin geoprocesamiento: lat/lon o join por atributo contra GeoJSON ya en WGS84.
- Las fichas se muestran como texto: el visor no valida la metadata (eso es `meta_tools`).
- El visor no tiene versión ni entra en el `CHANGELOG.md`, que es del paquete.
