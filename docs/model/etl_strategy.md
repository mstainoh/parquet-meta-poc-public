# Estrategia de ETL — uso

## Resumen
Cómo correr el pipeline de metadata: armar los artefactos de metadata, regenerar la key de
lectura del agente y —opcionalmente— sincronizar el visor, la metadata y las tablas al
lugar desde donde las lee el público del visor.

Nota: esta estrategia representa un caso de implementación. Se puede ajustar según el caso de uso.

Dónde está el resto: la vista de conjunto del repo y qué artefacto lee quién, en el
[`README.md`](../../README.md); el modelo de cinco grupos, en
[`metadata_model.md`](metadata_model.md); por qué la metadata se reparte así, en
[`ADR.md`](../ADR/ADR.md) (ADR-014).

## Antes del pipeline: estampar las tablas
El pipeline no escribe la metadata de las tablas: la lee. La estampa el ETL que escribe
cada tabla, en su propio repo, al escribirla:
- semantics + keys -> los escribe una persona en el bloque `meta:` del YAML de config de la
  tabla; `check_authoring` los valida antes de correr el ETL.
- provenance -> `get_yaml_provenance`, derivado de ese YAML.
- Los tres -> `to_parquet` los estampa en el footer del parquet (y agrega
  `provenance.writer_version`).

## Pipeline

Tres etapas. La etapa 1 es el núcleo de este repo (`scripts/run_metadata_etl.py`); la etapa 2
es `scripts/build_reading_key.py`; la etapa 3 no tiene script acá. Las etapas 2 y 3 son
opcionales. La 2 es independiente de la 1 (solo lee el contrato); la 3 publica lo que
producen la 1 y la 2, así que va última. Una integración puede envolver las tres en un
único script que las corra en orden (1 → 2 → 3) y se detenga en la primera falla.

### 1. Armar la metadata (obligatoria)
Lee tablas que ya fueron estampadas con `keys` + `semantics` + `provenance` (grupos 2/3/5,
ver arriba), rechequea esa metadata contra el contrato, corre el scanner mecánico sobre
cada una (grupo 1: conteo de filas, dtypes, conteo de nulos, y verificación de las
claves/claves foráneas declaradas contra los datos reales), y escribe los artefactos
derivados en la carpeta de salida de metadata. Cómo se corre:
[Correr la etapa 1](#correr-la-etapa-1); qué escribe: [Artefactos en disco](#artefactos-en-disco).

El grupo 4 (`inspect`) todavía no lo produce nada: la ficha lo lleva en `null`.

### 2. Armar la key de lectura del agente (opcional)
Regenera la key de lectura de los campos — qué significa cada campo del contrato y cómo
debe actuar el agente en base a él — directamente desde las reglas por campo del propio
contrato (`agent_rule`). Independiente: depende solo del contrato, no de ninguna tabla ni
corrida. Se corre a mano cada vez que cambia la regla de un campo; su salida se commitea
en lugar de regenerarse en cada armado de metadata, así que la etapa 1 no depende de ella
y no la dispara.

`python scripts/build_reading_key.py`: sin opciones ni `.env`; sobrescribe
`reading_key.yaml` en la raíz del repo.

### 3. Sincronizar a un consumidor (opcional)
Publica el visor y un espejo de la metadata + tablas donde sea que el público del visor
los levante — una carpeta compartida, un sitio estático, cualquier cosa desde la que lea
el consumidor. Esta etapa es por naturaleza propia de cada despliegue: los destinos, las
rutas y qué cuenta como "las tablas a publicar" los decide quien integra la herramienta,
no el núcleo de este repo. Una implementación concreta de esta etapa (rutas de destino,
de qué repos de origen traer las tablas) es configuración de despliegue: este repo no la
incluye.

Lo que suele hacer una integración típica (extract → load, sin transform):
- Origen: la salida de metadata de la etapa 1, las tablas de entrada (las de `input:`), el
  visor mismo y sus archivos de soporte (key de lectura, instrucciones del agente, docs de
  referencia). Las raíces, en `.env`; las subcarpetas, en la config o en el propio script
  de la integración.
- Transform: ninguna; se copia tal cual.
- Destino: la carpeta o sitio del consumidor, resuelto igual (raíz en `.env`, subcarpetas
  en la config o en el script).
- Conviene que el script de la integración ofrezca un dry-run y una forma de publicar solo
  una parte (p. ej. saltear la metadata o las tablas).

## Configuración: `.env` + config del ETL

Los punteros globales van en `.env`; todo lo demás, en la config (YAML):
- `.env` -> la raíz de cada fuente de tablas de entrada y la raíz de la salida de metadata.
- config -> subcarpetas, patrones de tablas a incluir o ignorar, parámetros de los
  chequeos y del scanner, y un `path` por artefacto.

La config no tiene rutas: cada `path:` es `{env: NOMBRE, subfolder: ...}` y resuelve a
`<valor de NOMBRE>/<subfolder>`. Los nombres de variable son libres, siempre que `.env` y
la config coincidan. Para armarlas, copiar [`.env.example`](../../.env.example) a `.env` y
[`config/etl.example.yaml`](../../config/etl.example.yaml) a `config/etl.yaml`, en la raíz
del repo; las dos plantillas comentan cada bloque. El paquete `meta_tools` no lee
variables de entorno: el `.env` lo cargan los scripts (`scripts/project_env.py`, con
`python-dotenv`), y `build_reading_key.py` no lo usa.

| Sección de la config | Qué fija |
|---|---|
| `input:` | una entrada por fuente: `name` (nombra la subcarpeta de la fuente en la salida y llena la columna `source` del log), `path`, y `params` opcionales de `find_tables` (`recurse`; `include` / `exclude`, regex sobre la ruta relativa a la raíz de la fuente) |
| `check_tables:` | parámetros de `check_table`: qué rechequear (`keys`, `semantics`, `provenance`) y `on_error_raise` |
| `mechanical.run_params:` | **obligatoria** (la sección `mechanical:`; `run_params` puede faltar). Parámetros de `ParquetScanner.run` (`verify_keys`, `verify_foreign_keys`, `check`, `on_error_raise`); `pk_sources` lo arma el script con las tablas de la corrida |
| `output:` | **obligatoria**. Un bloque por artefacto, cada uno opcional (si falta, un warning y se saltea): ver [Artefactos en disco](#artefactos-en-disco) |

## Correr la etapa 1

```bash
python scripts/run_metadata_etl.py [--config PATH] [--dry-run] [--clean] [--strict] [--debug | --silent]
```

| Opción | Efecto |
|---|---|
| `--config PATH` | otra config (por defecto, `config/etl.yaml` en la raíz del repo) |
| `--dry-run` | procesa todas las tablas y no escribe nada |
| `--clean` | borra los artefactos por tabla (estadísticas, fichas, auditoría) de las tablas que esta corrida no produjo: sacadas de `input:` o fallidas. Solo poda dentro de las subcarpetas de las fuentes que siguen en `input:`: la subcarpeta de una fuente sacada entera queda intacta, con un warning, y se borra a mano (a propósito: una config mal escrita no puede vaciar carpetas ajenas). El índice y el log se reescriben enteros siempre |
| `--strict` | corta en el primer error de tabla |
| `--debug` / `--silent` | log en nivel DEBUG / solo warnings y errores |

Qué hace:
1. Encuentra las tablas de cada fuente de `input:` (`load_input_sources`) y las lee
   enteras, en local. **Todas quedan en memoria a la vez** durante la corrida (son los
   destinos de las FK del paso 2), y el scanner relee cada una al procesarla: la memoria
   necesaria es la suma de las tablas de `input:` más una. Si no alcanza, se achica la
   corrida desde la config: menos fuentes, o `include` / `exclude` en sus `params`.
2. Indexa las tablas leídas por nombre de archivo (`tables_by_name`): son los destinos
   posibles de las FK. Cada tabla declara las suyas en `keys.foreign_keys`; si el
   `target_table` no está entre las tablas de la corrida, o está repetido, esa FK queda
   sin verificar (`fk_verified: null`).
3. Por tabla: rechequea la metadata estampada (`check_table`, solo el footer), corre el
   scanner (`ParquetScanner.run`) y arma la ficha y la auditoría (`build_schedule`,
   `build_audit`).
4. Chequea los vínculos entre tablas (`check_table_links`): `semantics.use_instead` y
   `semantics.cross_tables` tienen que nombrar una tabla de la corrida, con el mismo
   universo de nombres que los destinos de las FK (`tables_by_name`: un nombre repetido
   no cuenta como conocido).
5. Escribe los artefactos configurados en `output:`.

No hay modo incremental: cada corrida regenera los artefactos de todas las tablas, aunque
no hayan cambiado.

Errores:
- Metadata que no cumple el contrato, o claves declaradas que los datos no cumplen: se
  loguea, queda en `false` en el log y la tabla sigue (sus artefactos se escriben). Una
  discrepancia no corta el pipeline ([`metadata_model.md`](metadata_model.md), §2 y §6).
- Un `use_instead` / `cross_tables` que nombra una tabla desconocida: un warning en el
  log. No corta la corrida, no cambia el código de salida ni los artefactos.
- Una tabla ilegible, un footer que no se puede leer, o un chequeo de `check_tables` con
  `on_error_raise: true` que falla: esa tabla se saltea (sin artefactos ni fila en el
  índice) y su fila del log lleva `error_stage` (`read`, `check`, `mechanical` o `build`)
  y `error`. El resto de la corrida sigue, y el script termina con código 1. Con
  `--strict`, corta en el primero.
- Errores de config: cortan la corrida antes de procesar tablas. Una carpeta de fuente
  que no existe (`FileNotFoundError`), una variable de `.env` sin definir
  (`RuntimeError`), o que falte la sección `mechanical:` u `output:` (`KeyError`).
- El chequeo propio del scanner (`mechanical.run_params.check`) con `on_error_raise: true`
  que falla (`AssertionError`) corta siempre, aun sin `--strict`: el conjunto de campos
  del resultado no depende de la tabla, así que falla para todas. Es un bug del código
  (desfase con `fields.py`) o un paso apagado en `run_params` (p. ej.
  `verify_foreign_keys: false` con `check: true`).
- Cualquier otra excepción es un bug del código o del contrato, y corta siempre.

## Artefactos en disco

Cada artefacto sale de su bloque de `output:`. `<path>` es el `path:` de ese bloque, ya
resuelto; `<source>` es el `name` de la fuente de `input:` en la que se encontró la tabla.

| Artefacto | Bloque de `output:` | Archivo | Contenido | Lo escribe |
|---|---|---|---|---|
| Estadísticas | `mechanical` | `<path>/<source>/<TABLA>.json` | el grupo `mechanical` completo | `ParquetScanner.to_json` |
| Ficha | `schedules` | `<path>/<source>/<TABLA>.yaml` | `schema_version` + `keys` + `semantics` + `inspect` + `file_columns` | `build_schedule` |
| Auditoría | `audit` | `<path>/<source>/<TABLA>.yaml` | `provenance` completo | `build_audit` |
| Índice | `index` | `<path>/<name>.txt` | el catálogo: una fila por tabla procesada, delimitado por pipes, con encabezado | el script, con `dict_to_flat` |
| Log de corrida | `log` | `<path>/<name>.parquet` | una fila por tabla de entrada, de la última corrida: `source`, `table`, los flags de chequeo (`keys`, `semantics`, `provenance`, `uniques`, `not_nulls`, `index_columns`, `foreign_keys`, `mechanical`), `error_stage` y `error` | el script |

- Columnas del índice: `table` (el nombre del archivo, sin extensión) va siempre primera;
  el resto las fija `output.index.params.columns`, como `columna: ruta`. La ruta, con
  puntos, apunta a un campo de la ficha, de `mechanical` o de `provenance` de la tabla,
  aplanados (p. ej. `semantics.description`). Cualquier campo de esos tres puede ir al
  índice, también los que llevan valores reales (ver *Privacy* en el
  [`README.md`](../../README.md#privacy)).
- Flags del log (`true` / `false`, o `null` = no se chequeó o no se pudo verificar):
  - `keys`, `semantics`, `provenance`: el resultado de `check_table` (la metadata
    estampada contra el contrato); `null` si `check_tables:` no pide ese chequeo.
  - `uniques`, `not_nulls`, `index_columns`, `foreign_keys`: los veredictos del scanner
    (`uniques_verified`, `not_nulls_verified`, `index_columns_verified`, `fk_verified`):
    las claves declaradas contra los datos. `foreign_keys` queda en `null` si algún
    `target_table` no está entre las tablas de la corrida.
  - `mechanical`: `ParquetScanner.checked`, el autochequeo del scanner (el resultado
    tiene exactamente los campos de `fields.py`). No valida el JSON contra el contrato
    ([`metadata_model.md`](metadata_model.md), §6).
- La ficha y la auditoría de una tabla se llaman igual: van en carpetas distintas. Si se
  usa el visor, la de la auditoría tiene que llamarse `99_audit` (o estar dentro de una):
  el visor saltea los YAML bajo esa carpeta ([`viewer.md`](../html/viewer.md), §4).
- Las carpetas se crean si hace falta. Con `--dry-run` no se escribe nada.

Quién lee cada artefacto, y cuándo: [README](../../README.md#artifacts-and-who-reads-them).
Formatos, y por qué cada uno: [`metadata_model.md`](metadata_model.md), §5.
