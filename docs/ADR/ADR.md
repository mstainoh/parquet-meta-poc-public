# Decisiones de arquitectura (ADR)

> Registro de decisiones de arquitectura: qué se decidió, por qué, y qué la reemplazó. El archivo tiene dos partes: **vigentes** arriba (lo que gobierna el código) y **superadas / obsoletas** abajo (el registro de lo viejo, conservado para tener trazabilidad del "porque" del descarte).

Diferencia con otros archivos:
- Una decisión de arquitectura por tomar, o tomada pero no implementada, es un pendiente,
  no un ADR.
- [`model/`](../model/): documentos de referencia, no decisiones puntuales —
  [`metadata_model.md`](../model/metadata_model.md) (el modelo de cinco grupos) y
  [`etl_strategy.md`](../model/etl_strategy.md) (cómo correr el pipeline).
- [`CHANGELOG.md`](../../CHANGELOG.md): cambios publicados del paquete `meta_tools`.

*Una decisión superada no se borra, baja a "superadas"*

**Qué entra acá:** una decisión cuyo **motivo no se deduce mirando el código**, y que alguien podría revertir de buena fe sin saber qué rompe (ej: ADR-006, bajar las dependencias al repo parece más robusto y mata el doble clic). 

**Qué no entra acá:**
- renombres, layout de módulos, reorganizaciones que se descubren mirando el árbol de archivos — va a `CHANGELOG.md` y al historial de commits.
- nada que envejezca: los ADR son invariables. Sin números, estimaciones ni descripciones del estado actual ("hoy…", "todavía no…", qué existe o falta en el código); una métrica se puede nombrar, no cuantificar.


**Formato** (copiar para una entrada nueva):

**Fecha:** AAAA-MM-DD · **Estado:** vigente · **Amplía/Reemplaza:** ADR-XXX (opcional)
**Contexto:** qué parte del sistema toca.
**Resumen:** qué se decidió, en una o dos líneas.
**Motivo:** por qué — solo si no se deduce mirando el código.
**Consecuencias:** qué queda distinto (opcional).

Estados posibles: `vigente` · `superada por ADR-XXX` · `obsoleta` (el problema dejó de existir).

---

**Registro**

| # | Decisión | Estado |
|---|---|---|
| [020](#adr-020--el-ejemplo-del-repo-es-un-dataset-público-real-y-sus-salidas-commiteadas-son-datos-de-test) | El ejemplo del repo es un dataset público real, y sus salidas commiteadas son datos de test | vigente |
| [019](#adr-019--las-estadísticas-pueden-viajar-al-agente-la-frontera-es-la-fila) | Las estadísticas pueden viajar al agente; la frontera es la fila | vigente |
| [018](#adr-018--fondos-del-mapa-sin-clave-y-con-uso-comercial-permitido) | Fondos del mapa: sin clave y con uso comercial permitido | vigente |
| [017](#adr-017--fk-declaradas-como-relaciones-y-fk_orphans-por-relación) | FK declaradas como relaciones, y `fk_orphans` por relación | vigente |
| [016](#adr-016--el-repositorio-público-nace-congelado-la-integración-privada-sigue-su-curso) | El repositorio público nace congelado; la integración privada sigue su curso | vigente |
| [015](#adr-015--tablas-de-auditoríalog-sin-yaml-de-origen-provenance-flexible-y-temporal_scope-audit) | Tablas de auditoría/log sin YAML de origen: `provenance` flexible y `temporal_scope: audit` | vigente |
| [014](#adr-014--qué-metadata-ve-el-agente-y-cuándo) | Qué metadata ve el agente, y cuándo | vigente |
| [013](#adr-013--schema_version-opcional-y-writer_version-estampado-por-to_parquet) | `schema_version` opcional; `writer_version` estampado por `to_parquet` | vigente |
| [012](#adr-012--provenancerepo-es-un-identificador-libre-del-consumidor) | `provenance.repo` es un identificador libre del consumidor | vigente |
| [011](#adr-011--el-desarrollo-vive-en-un-repositorio-privado-lo-público-se-extrae-aparte) | El desarrollo vive en un repositorio privado; lo público se extrae aparte | vigente, ampliada por 016 |
| [010](#adr-010--vocabulario-cerrado-de-tipos-ampliado-dicts-por-columna-y-datedatetime-vía-json) | Vocabulario cerrado de tipos ampliado: dicts por columna y `date`/`datetime` vía JSON | vigente, ampliada por 017 |
| [009](#adr-009--meta_tools-organizado-por-criticidad-no-solo-por-grupo) | `meta_tools` organizado por criticidad, no solo por grupo | vigente |
| [008](#adr-008--sin-campo-de-linaje-estructurado-a-nivel-tabla-nota-libre-en-provenance) | Sin campo de linaje estructurado a nivel tabla; nota libre en `provenance` | vigente |
| [007](#adr-007--todo-el-procesamiento-en-el-cliente-sin-backend) | Todo el procesamiento en el cliente, sin backend | vigente |
| [006](#adr-006--el-visor-es-un-solo-index-html-sin-build-y-sus-dependencias-vienen-de-cdn) | El visor es un solo `index.html` sin build, y sus dependencias vienen de CDN | vigente |
| [005](#adr-005--validación-sin-pydantic-comparación-directa-contra-el-contrato) | Validación sin pydantic: comparación directa contra el contrato | vigente |
| [003](#adr-003--los-cinco-grupos-como-estructura-de-primer-nivel-del-contrato) | Los cinco grupos como estructura de primer nivel del contrato | vigente |
| [004](#adr-004--stages-como-conjunto-de-grupos-en-vez-de-tags-cat) | `STAGES` como conjunto de grupos en vez de tags `cat:` | superada por 005 |
| [002](#adr-002--política-de-stages-en-python-fuera-del-contrato) | Política de stages en python, fuera del contrato | obsoleta |
| [001](#adr-001--generador-pydantic-desde-el-contrato--test-de-auto-consistencia) | Generador pydantic desde el contrato + test de auto-consistencia | superada por 005 |

---
---

# Vigentes

## ADR-020 — El ejemplo del repo es un dataset público real, y sus salidas commiteadas son datos de test

**Fecha:** 2026-10-26 · **Estado:** vigente
**Contexto:** `examples/` y `tests/test_example_dataset.py`.
**Resumen:** el ejemplo se arma con datos de un informe público de un tercero (un NI 43-101), no
con datos sintéticos ni de la empresa. Se commitean los CSV, los parquet estampados, los
sidecars `inspect` y las salidas del ETL, y la suite los valida contra el contrato.
**Motivo:** los datos sintéticos no ejercitan lo que el contrato tiene que expresar
(convenciones mezcladas, contradicciones de la fuente, FK reales), y los datos propios no
pueden ir al público (ADR-011). Un informe público de minería da casos reales sin cruzar la
frontera. Commitear las salidas convierte al ejemplo en un test agnóstico del contrato: si
cambian el contrato o el writer, el test se rompe.
**Consecuencias:**
- Cambiar el contrato o el writer obliga a regenerar el ejemplo con sus scripts.
- Los YAML del ejemplo van en LF: su hash viaja en el `provenance` del parquet.
- Los valores del ejemplo son los del informe, tal como están publicados: no se corrigen ni
  se completan por suposición. Si un valor parece un error de la fuente, se deja igual y se
  explica en un finding `inspect`. Solo se cambia un valor cuando otra tabla del mismo
  informe da el correcto.

---

## ADR-019 — Las estadísticas pueden viajar al agente; la frontera es la fila

**Fecha:** 2026-10-22 · **Estado:** vigente · **Amplía:** ADR-014

**Contexto:** el grupo `mechanical` describe la tabla sin contenerla, pero dos de sus
campos llevan valores reales: `min_max` (rangos por columna) y `fk_orphans` (claves que no
joinean). ADR-014 prevé que el agente pida las estadísticas cuando la pregunta lo
requiere, y la regla de gobernanza dice que del tenant solo sale metadata.

**Decisión:**

- Las estadísticas pueden viajar al agente, como prevé ADR-014.
- La frontera es la fila: ninguna fila de una tabla sale nunca. Las estadísticas son
  metadata, aunque lleven valores reales.
- Si esos valores pueden salir en un despliegue concreto lo decide quien despliega, no el
  paquete. La documentación pública lo avisa.

**Motivo:** las estadísticas responden lo que la ficha declara pero no garantiza
(unicidad, rango real, claves que no joinean); sin ellas el agente adivina. Cuánto pesa un
rango o una clave huérfana depende del dato y del contexto de cada usuario: una regla fija
en el paquete sería demasiado estricta para unos y demasiado laxa para otros.

**Consecuencias:**

- "Solo sale metadata" se lee como "ninguna fila sale".
- El README y la documentación del visor dicen qué campos llevan valores reales y que
  compartirlos es decisión de quien despliega.
- `fk_orphans` lista todos los valores huérfanos, sin tope: una tabla con muchos manda una
  lista larga de valores reales. Acotarla es otra decisión.

**Alternativas descartadas:**

- **Estadísticas sin valores reales para el agente** (sin `min_max` ni `fk_orphans`):
  pierden justo lo que responde "hasta cuándo hay datos" y "qué no joinea". Queda como
  opción para un despliegue que la necesite.
- **No mandar estadísticas:** el agente responde peor, y la regla quedaría en el paquete
  en vez de en quien despliega.

---

## ADR-018 — Fondos del mapa: sin clave y con uso comercial permitido

**Fecha:** 2026-10-21 · **Estado:** vigente · **Amplía:** ADR-006

**Contexto:** los fondos online del mapa no viajan con el visor: el navegador le pide las
imágenes al proveedor cuando se elige el fondo, bajo las condiciones de uso de cada uno.
Esas condiciones no son la licencia del código ni la de las librerías por CDN, que son
permisivas. El visor se usa dentro de empresas, o sea con fines comerciales, y se abre con
doble clic desde `file://` (ADR-006).

**Decisión:**

- Un fondo online entra al visor si carga sin clave de API ni cuenta, también desde
  `file://`, y si sus condiciones permiten uso comercial con atribución.
- La atribución va completa en el mapa, con el texto que pide cada proveedor.
- De Sentinel-2 cloudless (EOX) se usa la capa 2016, CC BY 4.0, y no la de un año
  posterior. La etiqueta del desplegable dice el año.
- Se aceptan a sabiendas dos excepciones: el satélite de Esri, que carga sin clave pero
  cuyas condiciones piden una cuenta ArcGIS para uso comercial, y el fondo de un organismo
  cartográfico nacional, que no declara licencia para su capa base.

**Motivo:**

- Una clave de API dentro de un archivo que se distribuye queda expuesta, y los
  proveedores prohíben compartirla: un fondo que la exige no puede venir configurado.
- Las capas de Sentinel-2 cloudless de 2018 en adelante son CC BY-NC-SA (no comercial).
  Pasar la URL a un año más reciente parece una mejora inocua y cambia la licencia.
- Un servidor que exige el encabezado `Referer` bloquea los pedidos de una página abierta
  desde `file://`, que no lo manda: el fondo anda servido y falla con doble clic.
- Las dos excepciones aportan lo que los fondos libres no tienen (imagen de alta
  resolución, cartografía oficial) y se dejan por esa utilidad.

**Consecuencias:**

- Cumplir las condiciones de un fondo es responsabilidad de quien despliega el visor: el
  visor apunta a la URL y muestra la atribución.
- Un fondo nuevo se evalúa con los mismos criterios.
- Un fondo offline (imagen local) hereda la licencia de las imágenes de las que salió.
- Una captura del mapa lleva la atribución del fondo; con uno CC BY-SA, también su
  licencia.
- El fondo Sentinel-2 muestra la imagen de 2016: lo construido después no aparece.

**Alternativas descartadas:**

- **Sentinel-2 cloudless de un año reciente:** imagen más nueva, licencia no comercial.
- **CARTO (fondos oscuro y claro):** exige clave de API para sus tiles raster.
- **Servidores de tiles de OpenStreetMap:** bloquean los pedidos sin `Referer`, así que
  desde `file://` no cargan; además avisan que a los servicios comerciales les pueden
  cortar el acceso.

---

## ADR-017 — FK declaradas como relaciones, y `fk_orphans` por relación

**Fecha:** 2026-10-21 · **Estado:** vigente · **Amplía:** ADR-010

**Contexto:** `keys.foreign_key_columns` nombraba columnas, no la tabla ni la columna a
las que apuntan. El destino lo resolvía el consumidor del scanner con un mapeo por nombre
de columna, uno para toda la corrida: un mismo nombre que es FK hacia tablas distintas
según la tabla (p. ej. un `id` de período) no tenía cómo declararse, la columna
referenciada tenía que llamarse igual, y el agente no veía con qué tabla joinea cada FK.

**Decisión:**

- `keys.foreign_keys` reemplaza a `keys.foreign_key_columns`: una lista de relaciones
  `{source_col, target_table, target_col}`. `target_table` es el nombre del archivo, sin
  extensión; `target_col` es opcional, y si falta es `source_col`.
- El destino se busca por nombre entre las tablas que recibe el scanner. Si no aparece, o
  aparece más de una vez, la FK queda sin verificar (`fk_verified: null`), con un warning.
- `mechanical.fk_orphans` es una lista con una entrada por FK verificada: la relación
  resuelta y sus `orphans` (`[]` si no hay).
- Los huérfanos no se declaran: todo huérfano, conocido o nuevo, da `fk_verified: false`.
- El vocabulario de tipos suma `list`, una lista que no tipa sus items, para los valores
  huérfanos, que conservan el tipo de la columna.

**Motivo:**

- El destino es un dato de cada tabla, no de la corrida. Declararlo en la tabla resuelve
  los nombres repetidos y las columnas con otro nombre, y viaja con la ficha: el agente ve
  con qué joinea cada FK.
- `fk_orphans` por relación dice contra qué se verificó cada FK, también cuando no hay
  huérfanos.
- Un huérfano conocido sigue siendo una fila que no joinea: la señal tiene que saltar
  igual. Declararlo aceptado la apagaría.
- Pasar los huérfanos a texto pierde el tipo de la columna: un id numérico y su texto se
  verían iguales.

**Consecuencias:**

- Cambiar de forma obliga a re-estampar la metadata de cada tabla con FK. Una tabla con
  el campo viejo da "campo no declarado".
- Una FK compuesta se declara como una relación por columna: se verifica cada columna, no
  la tupla. Una tupla inexistente con valores válidos en cada columna no se detecta.
- Una `source_col` que no existe en la tabla, o una `target_col` que no existe en el
  destino, da `fk_verified: false`, sin entrada en `fk_orphans`.
- `contract_version` y `mechanical.schema_version` suben.
- Una tabla con huérfanos conocidos queda en `fk_verified: false` mientras existan; los
  nuevos se distinguen mirando `fk_orphans`.
- `list` no tipa sus items, como `dict[str,list]` no tipa sus listas (ADR-010): cualquier
  valor pasa la validación.

**Alternativas descartadas:**

- **Mapeo por nombre de columna en la config del ETL** (el modelo anterior): un solo
  destino por nombre para toda la corrida.
- **Léxico `TABLA.columna` dentro de `foreign_key_columns`:** no cambia los tipos ni
  obliga a re-estampar, pero no expresa una columna destino con otro nombre.
- **Mapeo por tabla en un YAML aparte:** no toca el contrato, pero el destino queda lejos
  de la tabla y el agente no lo ve.
- **Huérfanos aceptados por relación:** taparían filas que no joinean.
- **`orphans` como `list[str]`:** no amplía el vocabulario, pero pierde el tipo de los
  valores.

---

## ADR-016 — El repositorio público nace congelado; la integración privada sigue su curso

**Fecha:** 2026-10-21 · **Estado:** vigente · **Amplía:** ADR-011

**Contexto:** ADR-011 fija la dirección de la dependencia (la integración privada consume
la superficie pública, nunca al revés) y deja la extracción para cuando el contrato y el
visor estén maduros. Si el privado consume una versión pública etiquetada, cada cambio del
contrato o de `meta_tools` que pide la integración tiene que pasar por un release público
antes de llegar al privado.

**Resumen:** la separación se hace en tres pasos; esta decisión fija los dos primeros.

1. **Público congelado.** Se extrae un repositorio público con la superficie agnóstica
   (ADR-011), como demostración del enfoque. Se publica y no se mantiene: no recibe los
   cambios del privado ni promete compatibilidad.
2. **El privado sigue su curso.** Conserva su propia copia del contrato y de `meta_tools`
   y la evoluciona a su ritmo, sin depender del público ni sincronizarse con él.
3. **Dirección, no decisión:** más adelante, el público se separa como un contrato
   estandarizado que el privado importa. Cuándo y con qué forma se decide entonces.

**Motivo:** el contrato y `meta_tools` cambian al ritmo de la integración privada. Un
público vivo del que dependa el privado convierte cada cambio en un release coordinado
entre dos repositorios: es el costo de coordinación que ADR-011 ya quería evitar. Un
público congelado muestra el enfoque sin ese costo; la dependencia real se arma recién
cuando el contrato sea lo bastante estable para estandarizarlo.

**Consecuencias:**

- La extracción del público no espera a que el contrato madure (amplía la última
  consecuencia de ADR-011): al estar congelado, no compromete estabilidad.
- Hasta el paso 3, ADR-011 vale en una sola dirección: lo público no depende de nada
  privado. El privado no instala el público; mantiene su copia.
- Público y privado divergen desde la extracción, y se acepta: un arreglo en el privado no
  se replica en el público.
- El versionado del privado es propio hasta el paso 3. Importar el contrato estandarizado
  reemplaza su copia por una dependencia externa: es un cambio mayor de versión en el
  privado, no una actualización.
- El público tiene que salir limpio (sin referencias privadas, ADR-011): congelado, no
  prevé correcciones posteriores.

---

## ADR-015 — Tablas de auditoría/log sin YAML de origen: `provenance` flexible y `temporal_scope: audit`

**Fecha:** 2026-09-10 · **Revisada:** 2026-10-20 · **Estado:** vigente

**Contexto:** antes de esta decisión, el contrato asumía que toda tabla nace de un YAML de
config autorado por una persona — es lo que `provenance.source_yaml`/`source_sha256`
(`required: true`) garantizaban: poder reconstruir de dónde salió una tabla sin acceso al
repo de origen. El propio pipeline de metadata genera tablas que rompen ese supuesto — el
log de una corrida es un parquet que no sale de ningún YAML de config: existe porque el
código lo arma directamente. El mismo supuesto alcanzaba al entorno del productor: que git
resuelve el commit y que quien invoca el writer conoce al usuario. Ninguno de los dos está
garantizado — el writer corre donde lo corra el consumidor (fuera de un repo, sin git, en
una corrida automática), y `get_yaml_provenance` ya los trataba como best-effort.

**Decisión:**

- Regla general: un campo de `provenance` que el writer no siempre puede producir es
  `required: false`. Un `null` ahí significa "no se pudo resolver", no un error de
  validación.
- Por esa regla pasan de `required: true` a `required: false`:
  - `source_sha256` y `source_yaml`: tablas sin YAML de origen (no hay archivo que
    hashear ni embeber).
  - `git_commit`: git puede no resolver el commit (no instalado, o el productor no corre
    dentro de un repo); `get_yaml_provenance` lo deja en `null` con un warning.
  - `username`: el consumidor puede no conocer al usuario; `get_yaml_provenance` lo
    recibe opcional y lo estampa tal cual.
- `semantics.temporal_scope` gana el valor `audit` — "tablas internas de auditoría o
  log", distinto de los valores que describen la ventana temporal de datos de negocio.

**Motivo:** exigir un campo que el writer no siempre puede producir convierte una
limitación del entorno en un error de validación: la tabla se escribe bien y queda marcada
inválida, sin nada que el autor pueda corregir. Para el YAML de origen, dejaría afuera del
contrato sin alternativa a una tabla que el pipeline genera internamente. `required:
expected` tampoco aplica: la deuda es para un campo que alguien puede completar después, y
`provenance` no se autora a mano. `temporal_scope: audit` da la señal declarada de "esta
tabla es de ese tipo", en vez de forzar alguno de los valores existentes (todos describen
semántica de negocio, no aplican a un log de corrida).

**Consecuencias:**

- El `false` de `source_sha256`/`source_yaml` solo habilita que una tabla `audit` invoque
  el writer con ambos campos en `None` sin romper la validación. El caso normal sigue
  siendo `get_yaml_provenance`, que completa ambos.
- El contrato por sí solo no distingue "no se pudo" de "se omitió": el `required: false`
  vale para cualquier tabla. Si hace falta reforzarlo, le corresponde al chequeo de
  provenance — p. ej. exigir `source_sha256`/`source_yaml` salvo que
  `temporal_scope == "audit"`.
- Un `git_commit` en `null` no se detecta al validar: la señal es el warning de
  `get_yaml_provenance` al escribir.

---

## ADR-014 — Qué metadata ve el agente, y cuándo

**Fecha:** 2026-09-10 · **Revisada:** 2026-10-20 · **Estado:** vigente

**Contexto:** el agente escribe consultas sin acceso a los datos: solo ve metadata. Cargar
la metadata completa de todo el catálogo en cada pregunta es caro, y casi todo lo que pesa
(la auditoría de origen y las estadísticas) no sirve para escribir la consulta. Además, lo
que viaja en todas las preguntas crece con cada tabla nueva.

**Decisión:** la metadata se reparte en capas, y cada capa tiene una regla de carga fija.

| Capa | Contenido | Entra al contexto |
|---|---|---|
| Reglas | reglas transversales (preprompt) + key de lectura (qué significa cada campo, derivada de los `agent_rule` del contrato) | siempre |
| Índice | una línea por tabla: identificación, descripción, grano, alcance temporal, redirección, calidad y fechas de actualización | siempre |
| Ficha | por tabla: `keys` + `semantics` + columnas reales del archivo + hallazgos de `inspect` | en la segunda vuelta, solo de las tablas elegidas |
| Estadísticas | por tabla: el grupo `mechanical` | solo si la pregunta lo requiere; decide el agente |
| Auditoría | `provenance` | nunca |

**Pregunta y respuesta:**

- *Primera vuelta* (reglas + índice + pregunta): el agente elige las tablas. Si el índice
  alcanza para contestar (qué hay, cuándo se actualizó), contesta ahí; si no se puede
  responder, lo dice.
- *Segunda vuelta* (se suman las fichas elegidas): el agente escribe la consulta y sus
  notas. Puede pedir estadísticas de una tabla cuya ficha ya tiene, cuando la respuesta
  depende de verificar algo que la ficha declara pero no garantiza (unicidad, nulos, claves
  foráneas, índice, rango real). El gatillo es la pregunta, no que el usuario nombre las
  estadísticas.
- La consulta se ejecuta en local (ADR-007). Si falla, al agente vuelve solo el error,
  nunca filas.

**Transporte:** la lógica es la misma en los dos modos. En el Project, reglas, índice y
fichas están disponibles juntos, y el agente abre solo las fichas de las tablas que eligió.
En la vía API, las dos vueltas son explícitas y las arma el propio visor, no un servidor
(ADR-007). El formato de los mensajes de cada vuelta es otra decisión.

**Motivo:**

- Lo que viaja siempre se limita a lo necesario para elegir tabla, así crece lo menos
  posible con el catálogo. El detalle llega solo para las tablas elegidas.
- `provenance` es auditoría: es la capa más pesada (embebe la config de origen, que
  duplica `semantics`) y no ayuda a escribir la consulta.
- Las estadísticas tienen valores reales y casi nunca cambian la consulta; entran solo
  cuando la pregunta las necesita.
- La key de lectura va en las reglas porque el agente la necesita para elegir tablas desde
  la primera vuelta.
- Las fechas de actualización van en el índice para contestar "¿cuándo se actualizó X?"
  sin abrir ninguna ficha.

**Consecuencias:**

- La ficha siempre trae las columnas reales del archivo: es lo que permite cumplir "no
  inventes nombres de columna".
- El índice cubre todo lo consultable, no solo gold. Si una tabla no se debe consultar, lo
  dice el índice, no las reglas.
- Una regla que vale para una sola tabla va en sus `caveats` / `column_info`, no en las
  reglas transversales.
- Los hallazgos de `inspect` viajan todos con la ficha, sin filtrar: con las tablas ya
  elegidas, el agente lee cada hallazgo y decide si toca la pregunta.

**Alternativas descartadas:**

- **Cargar la metadata completa de cada tabla:** caro, y casi todo es auditoría y
  estadísticas.
- **Keywords por tabla y una tercera vuelta:** cuestan lo mismo que las descripciones y
  dan menos señal. Se reconsidera si la capa "siempre" deja de entrar en el contexto.
- **Inventario plano `tabla:columna` en el índice:** es aditivo; se agrega si aparece un
  fallo de selección por columna.
- **Campos cortos** (`description_short`, `grain_short`): innecesarios.
- **Parquet como transporte al agente:** es binario, y en la vía API no hay sandbox para
  abrirlo.
- **Fichas por dominio:** las consultas cruzan dominios.

---

## ADR-013 — `schema_version` opcional y `writer_version` estampado por `to_parquet`

**Fecha:** 2026-09-07 · **Estado:** vigente

**Contexto:** versionado de la metadata embebida en el parquet.

**Resumen:** `meta.schema_version` es opcional. `to_parquet` agrega
`provenance.writer_version` automáticamente cuando escribe un bloque de metadata,
con la versión del propio writer por defecto. `mechanical.schema_version` conserva su
versionado independiente y obligatorio.

**Motivo:** los consumidores confundían la versión de la forma del sobre `meta`, la
versión del writer y la versión del resultado del scanner. La forma más clara es no
obligar a todos los consumidores a estampar una versión del sobre, dejar la versión
del código en el único writer común y mantener el scanner con su propio contrato.

**Consecuencias:**

- La autoría y los consumidores pueden omitir `meta.schema_version`.
- `writer_version` no se espera en la salida de `get_yaml_provenance` antes de escribir;
  lo agrega `to_parquet` dentro de `provenance`.
- `mechanical.schema_version` sigue describiendo exclusivamente la forma del resultado
  producido por el scanner.

---

## ADR-012 — `provenance.repo` es un identificador libre del consumidor

**Fecha:** 2026-09-07 · **Estado:** vigente · **Reemplaza:** la restricción de valores de `repo` documentada previamente

**Contexto:** el campo `meta.provenance.repo` identifica el origen que el writer
estampa en cada tabla.

**Resumen:** `repo` permanece como campo obligatorio de tipo `str`, pero el contrato
no mantiene una lista cerrada de repositorios válidos. Cada consumidor decide el
identificador al llamar a `get_yaml_provenance` o al fijarlo con un wrapper, por
ejemplo `functools.partial`.

**Motivo:** la lista de referencia obligaba a modificar este repo cada vez que
aparecía un consumidor nuevo, aunque el valor ya es trivial de proporcionar en el
call site y no existe una validación útil que este contrato pueda hacer sobre sus
posibles nombres.

**Consecuencias:**

- Se elimina la lista cerrada de valores de la spec (antes, un conjunto fijo de
  identificadores); cualquier string puede identificar al consumidor.
- La elección del identificador queda en el ETL o aplicación que usa el writer,
  cerca de su configuración y de su llamada.
- `repo` sigue siendo obligatorio para conservar la trazabilidad de provenance.

---

## ADR-011 — El desarrollo vive en un repositorio privado; lo público se extrae aparte

**Fecha:** 2026-09-06 · **Revisada:** 2026-10-22 (texto válido en los dos repositorios) ·
**Estado:** vigente · **Ampliada por:** ADR-016 (forma de la primera extracción)

**Contexto:** El repositorio de desarrollo reúne el contrato y `meta_tools`, que son
agnósticos y potencialmente públicos, con la publicación del visor, prompts, rutas y
configuración de una integración concreta con los repos de datos internos.

**Resumen:** El desarrollo se mantiene en un repositorio privado, que conserva la
integración privada; la superficie reusable se extrae a un repositorio público aparte.

**Motivo:** Mientras el diseño del contrato y del viewer siga cambiando, separar
físicamente agregaría coordinación sin aportar estabilidad. La dependencia conceptual,
sin embargo, queda fijada con esta decisión: la integración privada consume la
superficie pública; el producto público nunca depende de la integración privada.

**Consecuencias:**

- La publicación del visor, rutas, prompts y datos de dominio no son candidatos a formar
  parte del repositorio público.
- La futura extracción debe verificar el árbol de imports y las referencias de
  configuración para demostrar que no existe dependencia privada -> pública invertida.
- La extracción se hace cuando el contrato y el viewer estén maduros, no antes.

---

## ADR-010 — Vocabulario cerrado de tipos ampliado: dicts por columna y `date`/`datetime` vía JSON

**Fecha:** 2026-09-06 · **Estado:** vigente · **Amplía:** ADR-005 · **Ampliada por:**
ADR-017 (token `list`)
**Contexto**: campos permitidos (*type*) en `meta_contract.yaml`
**Resumen**: Se amplian los tipos de datos posibles en el meta_contract; el vocabulario que fija esta decisión es:
  - Escalares: *str, int, bool, date, datetime*
  - Compuestos simples: *"list[str]", "dict[str,str]", "dict[str,int]"*,
  - Anidados: "dict[str,list]", "dict[str,dict]", "list[object]"
  - Lista de referencia (*enum*): requiere `values:`
  - Diccionario con claves especificas (*object*):requiere `fields:`
 
**Motivacion**: Al extender el chequeo al grupo `mechanical` aparecieron dos huecos en el
vocabulario cerrado de ADR-005:

- `null_count` / `n_distinct` (dict por columna con valores `int`), `fk_orphans` (dict por
   columna con una lista de valores huérfanos) y `min_max` (dict por columna con un
   `{min, max}` interno) no entraban en ningún token existente — `dict[str,str]` exige
   valores string, y `object` exige `fields:` fijos, que no tiene sentido cuando las claves
   son nombres de columna (no se conocen de antemano). Se agregaron tres tokens genéricos
   en el valor, sin recursar en su contenido: `dict[str,int]`, `dict[str,list]`,
   `dict[str,dict]`.
- `mechanical` y `provenance` no se autoran a mano: los estampa el scanner/writer como
   JSON, así que un campo `type: datetime` (`scanned_at`, `written_at`) le llega al
   checker como string ISO, no como objeto `datetime` — al revés de `keys`/`semantics`,
   que se autoran en YAML y donde PyYAML ya entrega objetos `date`/`datetime` nativos.
   Por eso la comparación de tipos acepta ambas representaciones para `date`/`datetime`.

ADR-005 fija el vocabulario cerrado como no negociable ("un tipo que no se
entiende es un campo que no se valida, nunca degrada a `Any`"), pero se diseñó mirando
solo la superficie de autoría (YAML, `keys`+`semantics`). Al extender el mismo motor de
comparación a `mechanical`/`provenance` (superficies JSON, con dicts por columna)
aparecieron formas de dato que ese vocabulario no representaba — esto no relaja el
principio, lo completa para las superficies que faltaban.

**Consecuencias:**

- El vocabulario sigue cerrado: un token desconocido sigue rompiendo con `ContractError`,
  nunca degrada a "cualquier cosa".
- Los tres tokens nuevos no tipan la forma interna de cada valor (p.ej. qué tipo tiene
  `min`/`max` dentro de `min_max`) — solo que es un dict con claves `str` y valores del
  tipo dado. Tipar esa forma interna, si hace falta, es una extensión futura, no algo que
  este ADR resuelva.
- Para `date`/`datetime`, un valor `str` se acepta solo si parsea como fecha ISO
  (`fromisoformat`); si no parsea, es error de tipo como cualquier otro.

---

## ADR-009 — `meta_tools` organizado por criticidad, no solo por grupo

**Fecha:** 2026-09-05 · **Estado:** vigente

`write/` (estampa `keys` + `semantics` + `provenance` — lo único que un ETL externo
necesita importar) y `check/` (valida contra el contrato, no un requisito para escribir)
son paquetes separados; el scanner del grupo `mechanical` queda como módulo plano porque
corre acá y es importable pero no crítico.

---

## ADR-008 — Sin campo de linaje estructurado a nivel tabla; nota libre en `provenance`

**Fecha:** 2026-09-05 · **Estado:** vigente

Se decidió no agregar un campo de linaje a nivel tabla (ni en `mechanical` ni en
`semantics`). En su lugar, `provenance` gana `notes` (`type: str`, `required: false`,
sin `agent_rule`): texto libre que el writer completa cuando la tabla sale de un proceso
que produce varias tablas a la vez y conviene dejar la relación anotada.

**Motivo:** `provenance.source_yaml` ya embebe la config de origen verbatim por tabla,
así que lo único que faltaba era la relación entre tablas hermanas de una misma corrida,
que un config individual no necesariamente menciona. Esa relación no necesita ser
estructurada ni verificable: es dato de auditoría, no algo que el agente SQL consulte —
por eso no lleva `agent_rule`, igual que el resto de `provenance`.

**Consecuencias:**

- Si en el futuro hace falta recorrer el linaje programáticamente (no solo leerlo como
  texto), esta decisión se revisa — `notes` no es parseable de forma confiable.

---

## ADR-007 — Todo el procesamiento en el cliente, sin backend

**Decidida:** desde el inicio del proyecto · **Registrada:** 2026-09-05 · **Estado:** vigente

Los archivos que el usuario abre nunca salen del browser: DuckDB corre en el cliente (en
un Web Worker) y los archivos elegidos se registran en memoria y se exponen como vistas
SQL. No hay componente de servidor, y es por diseño.

**Motivo:** el dato es interno y el visor tiene que poder abrirse en cualquier máquina sin
pedirle permiso a nadie ni levantar nada. Un backend convertiría "abrí el archivo" en un
problema de despliegue y de custodia del dato.

**Consecuencias:**

- Las exportaciones también se generan en el cliente, y su implementación difiere según
  lo que cada librería del browser sabe hacer (p. ej. CSV con el `COPY … TO` nativo de
  DuckDB, XLSX con SheetJS); ninguna pasa por un servidor.
- El renderizado de filas se topea por performance del DOM, pero **las exportaciones
  operan sobre el resultado completo**. El tope es de la vista, no del dato.
- El python de `meta_tools/` es **tooling, nunca runtime del visor**: `index.html` no
  depende de nada de ahí.

---

## ADR-006 — El visor es un solo `index.html` sin build, y sus dependencias vienen de CDN

**Decidida:** desde el inicio del proyecto · **Registrada:** 2026-09-05 · **Estado:** vigente

Estilos, markup y un único `<script type="module">` viven en `index.html`.
No hay build, ni `package.json`, ni bundler. Ambas formas de abrirlo — doble clic
(`file://`) y servido por HTTP — tienen que seguir funcionando siempre.

Las dependencias se importan desde un CDN (jsDelivr), no se vendorean:

- las que se publican como módulo ES (p. ej. **duckdb-wasm**), como import cross-origin
  desde el `<script type="module">`;
- las demás (p. ej. **SheetJS**, **Leaflet**) como `<script>` clásicos (no módulo), y sus
  hojas de estilo también desde el CDN.

**Motivo:** Chrome bloquea los imports de módulos **locales relativos** sobre `file://`,
pero los imports cross-origin hacia un CDN funcionan igual. Traer las librerías del CDN es
justamente lo que mantiene vivo el doble clic; vendorearlas o dividir el script en módulos
locales propios lo rompería.

**Consecuencia (la trampa):** la restricción es contraintuitiva — "bajar las dependencias
al repo" parece más robusto y es exactamente lo que no se puede hacer. Por eso se anota
también en el propio `index.html`, junto al código que alguien estaría tentado de dividir.

**Costo aceptado:** la primera carga necesita red, y el visor queda atado a la
disponibilidad del CDN y a lo que este sirva para cada versión declarada (si es un rango
y no una versión fija, una versión nueva entra sin aviso).

---

## ADR-005 — Validación sin pydantic: comparación directa contra el contrato

**Fecha:** 2026-09-04 · **Estado:** vigente · **Reemplaza:** ADR-001, ADR-004

El generador dinámico de modelos pydantic se reemplazó por una comparación directa de
dicts: el checker compara el dict de la instancia contra el dict del contrato campo por
campo, en forma recursiva — sin `create_model` ni `ValidationError`. Cargar el contrato
se reduce a leer la spec y señalar una spec rota (`ContractError`).

**Motivo:** el generador dinámico existía únicamente para llegar a esa misma comparación
por un camino más largo. Construir un modelo pydantic en runtime para después comparar es
una indirección que no compra nada: el vocabulario de tipos ya era cerrado y chico.

**Consecuencias:**

- `STAGES` / `model_for` / `Stage` desaparecen: el chequeo ya no toma `stage`. El
  chequeo de autoría valida siempre `keys` + `semantics` y nada más; la comparación queda
  como un motor genérico, que recibe el sub-árbol del contrato a comparar.
- `provenance` / `schema_version` / `mechanical` / `inspect` quedan para otros chequeos
  con el mismo motor, sobre lo que se estampa o se genera después de autorar (ver
  ADR-010).
- La lectura del YAML de config va aparte: una recursión ubica todo bloque `meta` de un
  YAML (puede haber más de uno por archivo).

**Lo que sobrevive de ADR-001:** el test de auto-consistencia (cada `example:` del
contrato valida contra el `type:` de su propio campo) y la regla de que un token de tipo
desconocido rompe con error y nunca degrada a `Any`.

---

## ADR-003 — Los cinco grupos como estructura de primer nivel del contrato

**Fecha:** 2026-09-04 · **Estado:** vigente

`meta_contract.yaml` se reescribió con los cinco grupos (`mechanical`, `keys`,
`semantics`, `inspect`, `provenance`) como forma del archivo, no como tags sobre claves
planas. `meta:` quedó anidado, con `keys` / `semantics` / `provenance` cada uno como
`type: object` con sus `fields:` adentro, terminando el mismo patrón que `mechanical` e
`inspect` ya tenían como bloques propios. `schema_version` queda como hermano de los
tres: no es de ninguno en particular — versiona el sobre que `keys` + `semantics` +
`provenance` comparten al escribirse juntos (su obligatoriedad: ADR-013).

`categories:` se renombró a `groups:`, con los nombres reales en vez de números.

**Motivo:** antes eran claves planas distinguibles solo por un tag numérico (`cat: N`).
Con el cambio, la forma del archivo misma dice a qué grupo pertenece cada campo, y se
cierra el problema de doble vocabulario (`cat N` vs. nombre de grupo).

**Dos reclasificaciones:**

- `required_filters`: de `keys` a `semantics`. No es verificable — la tabla puede contener
  a propósito filas que lo violan; es el consumidor quien tiene que filtrarlas.
- `index_columns`: de `semantics` a `keys`. Sí es verificable — el scanner computa
  `file_index_columns` específicamente para contrastarlo. Consecuencia: `mechanical` gana
  `index_columns_verified`, simétrico con `uniques_verified` / `not_nulls_verified` /
  `fk_verified`.

**Nombre del grupo:** `keys` no es exacto (`not_nulls` e `index_columns` no son
"claves"); se evaluó `constraints` y se mantuvo `keys`, porque renombrar un grupo del
contrato rompe la API pública para una ganancia solo de nombre.

---
---

# Superadas / obsoletas

> Decisiones que ya no gobiernan el código. Se conservan porque el motivo del descarte es
> lo que evita volver a tomarlas.

## ADR-004 — `STAGES` como conjunto de grupos en vez de tags `cat:`

**Fecha:** 2026-09-04 · **Estado:** superada por [ADR-005](#adr-005--validación-sin-pydantic-comparación-directa-contra-el-contrato)

Con los tags `cat:` eliminados del contrato (ADR-003), `STAGES` pasó de operaciones
`drop` / `demote` sobre tags a un `groups: frozenset` por stage: el subconjunto de claves
top-level de `meta:` que aplica en cada momento (`{keys, semantics}` en `authoring`;
`{schema_version, keys, semantics, provenance}` en `stamped`).

**Motivo:** simplificación real, no cosmética. Como `schema_version` no pertenece al grupo
de `authoring`, deja de ser un campo del modelo en ese stage — no hace falta "demotarlo" a
deuda con una regla propia.

**Detalle de implementación (ya no vigente):** `_build_model` juntaba los paths punteados
de los campos `expected` (`"keys.uniques"`, no `"uniques"`) en la misma pasada en la que
armaba el modelo, a cualquier profundidad de anidamiento; `check.py` los navegaba con un
helper `_get_nested` que caminaba submodelos pydantic.

**Por qué se superó:** ADR-005 elimina los stages enteros junto con el generador.

---

## ADR-002 — Política de stages en python, fuera del contrato

**Fecha:** 2026-09-03 · **Estado:** obsoleta

Se decidió que la política de stages (`authoring` / `stamped` / `inspect`) viviera en
`STAGES`, en python y no en el YAML, porque es política del validador y no forma del dato.
`extra="forbid"` hacía cumplir sola la regla del grupo `provenance`: el modelo de
`authoring` no lo conoce, así que "si aparece escrito a mano es un error" no necesitaba
código propio.

**Limitación que arrastraba:** en `authoring` no se podía distinguir si el grupo `keys`
faltaba de verdad o venía declarado en la sección del paso de limpieza del ETL. Desde el
dict solo no se ve la variante; habría hecho falta pasarle el tipo de config.

**Por qué quedó obsoleta:** esa limitación era síntoma de un diseño ya corregido. El paso
de limpieza nunca declaró las reglas, solo las aplicaba mal ubicadas conceptualmente. Con el grupo de
`keys` autorado siempre en `meta`, la asimetría por variante desaparece y no queda nada
que resolver. Los stages en sí murieron después con ADR-005.

---

## ADR-001 — Generador pydantic desde el contrato + test de auto-consistencia

**Fecha:** 2026-09-03 · **Estado:** superada por [ADR-005](#adr-005--validación-sin-pydantic-comparación-directa-contra-el-contrato)

El checker de metadata se genera **desde** `meta_contract.yaml`, no se escribe contra él.
Dos piezas:

**a) Generador.** Lee el contrato y arma el modelo pydantic desde las claves `type` /
`required` / `default` / `values` / `fields`. El vocabulario de tipos es cerrado (la clave
`types:` del contrato), así que es un dict chico más `create_model()`.
**No negociable:** un token de tipo desconocido tiene que romper la generación con error,
nunca degradar a `Any` — un tipo que no se entiende es un campo que no se valida.

Mapeo de `required`:

| valor | comportamiento |
|---|---|
| `true` | falta o `null` → error de validación |
| `expected` | falta o `null` → se loguea (`log.info`) como deuda y sigue |
| `false` | `null` es una respuesta legítima |

Dos clases de problema, tratadas distinto: **error de esquema** (tipo, enum, `required:
true` ausente, campo desconocido) → `log.error` + `False`, o `raise` con `on_error_raise`;
**faltantes** (`required: expected` en null) → `log.info` y sigue siendo `True`.
`ContractError` se propaga siempre: un contrato roto es un bug de la spec, y validar contra
él no significa nada.

**b) Test de auto-consistencia.** Cada `example:` del contrato tiene que validar contra el
`type:` de su propio campo. Es lo que evita que la spec y el validador se separen en
silencio, y es la razón por la que los ejemplos viven en el **valor** y no en un
comentario (`yaml.safe_load` descarta los comentarios).

**Por qué se superó:** ver ADR-005. El generador era un rodeo para llegar a una comparación
de dicts. La parte (b) y la regla del token desconocido las conserva ADR-005.
