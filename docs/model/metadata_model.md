# Modelo de metadata — los cinco grupos

> Reglas de construcción de la metadata de tablas. Fija **qué se escribe, quién lo
> escribe, cuándo y dónde vive**. El detalle campo por campo va en
> [`meta_contract.yaml`](../../src/meta_tools/meta_contract.yaml); este documento fija la
> estructura que ese contrato tiene que respetar. Cómo se reparte esa metadata entre los
> artefactos que lee el agente, y cuándo los lee: la tabla de artefactos del
> [`README.md`](../../README.md#artifacts-and-who-reads-them), y el porqué en
> [`ADR.md`](../ADR/ADR.md), ADR-014. Cómo se corre el pipeline que los arma:
> [`etl_strategy.md`](etl_strategy.md).
>
> Los YAML de config y los ETL que consumen el contrato se adaptan a esta estructura, no al
> revés: esto es manoseo de metadata, la tabla en sí no cambia.

Actualizado 2026-10-22

---

## 0. Resumen

Estructura de la metadata, por tabla, que consume el agente de IA para decidir cómo armar
una query (código SQL) o resolver consultas de metainformación, sin ver los datos.

## 1. Por qué cinco grupos

La metadata de una tabla es un **diccionario**, uno por tabla, todos con la misma
estructura, **armado juntando cinco pedazos** de distinta procedencia. No es una tabla
relacional con todo en el mismo plano (una fila por tabla): la metadata real es anidada
(`column_info` es un dict, `findings` una lista, cada grupo con su sello) y un formato
plano la aplana mal.

El motivo de partirla en grupos no es estético. Los pedazos tienen **vidas distintas**:

- unos quedan congelados en el parquet en el momento de armar la tabla,
- otro se recalcula en cada corrida del scanner,
- otro lo escribe una IA después y caduca.

---

## 2. Los cinco grupos

| # | grupo | qué es | quién lo **autora** | quién lo **estampa** | cuándo | dónde vive |
|---|---|---|---|---|---|---|
| 1 | `mechanical` | lo que sale de leer la tabla: row_count, dtypes, nulls, rangos, y el **veredicto** de los checks del grupo 2 | nadie (se calcula) | script de scanning, **en este repo** | con la tabla ya hecha | fragmento JSON por tabla |
| 2 | `keys` | lo declarado **y verificable**: uniques, not_nulls, foreign_keys, index_columns | **persona**, en el YAML de config | el ETL, al armar la tabla | durante el armado | metadata del parquet |
| 3 | `semantics` | lo declarado y **no** verificable: description, grain, caveats, temporal_scope, use_instead, column_info, required_filters, ... | **persona**, en el YAML de config | el ETL, al armar la tabla | durante el armado | metadata del parquet |
| 4 | `inspect` | hallazgos de abrir la tabla y mirarla | la IA (`/inspect-table`) | un agente externo (todavía no existe) | después de que la tabla existe | fragmento YAML por tabla |
| 5 | `provenance` | de dónde vino: identificador libre de repo/origen, source_path, sha256, git_commit, username, written_at, writer_version, YAML de origen verbatim | nadie (se deriva) | el ETL, leyendo el YAML de config | durante el armado, o antes | metadata del parquet |

El grupo 4 todavía no lo produce nada: `/inspect-table` no existe, y la ficha lo lleva en
`null`. `check_inspect` ya valida el sidecar.

### Autorar vs estampar

Los grupos 2 y 3 **los escribe ("autora") una persona** en el YAML de config. El 4 lo
"genera" la IA sobre la tabla hecha, con las reglas a mano.

Los grupos 1 y 5 no tienen un autor. El *mecánico* es un "describe" clásico de la tabla, y
el *provenance* es un log para auditoría del proceso de armado. Si uno de estos está en un
YAML de config (escrito a mano), es un bug.

### Grupo 2 vs Grupo 1

Decir `uniques: [order_id]` (grupo 2) es una **afirmación**: dice lo que el ETL se
comprometió a garantizar. `uniques_verified: false` (grupo 1) es el **veredicto**: sale de
correr el check contra los datos. El check de integridad es responsabilidad de un **script
separado**, no del ETL. Su resultado es mecánico, así que vive en el grupo 1.

Notar que una discrepancia **no es necesariamente fallo duro**: se marca y se sigue. Es una
alerta real (significa que el ETL no hizo lo que el YAML dice), pero el pipeline no se
corta por eso.

---

## 3. Ciclo de vida: generación de metadata

```
   Antes de escribir la tabla
   ├── grupo 2  keys          uniques, not_nulls, ...
   └── grupo 3  semantics     description, grain, caveats, ...
                    │
                    ▼
   Al momento de escribir la tabla
   ├── grupo 5  provenance    written_at, git_commit, ...
                    │
                    ▼
   Luego de escribir la tabla
   ├── grupo 4  inspect       findings, ...
   ├── grupo 1  mechanical    null_count, n_distinct, ...


   Aplicación:

   corre el ETL
   ├── Se lee la metadata como un parámetro más
   ├── Se ejecuta el ETL (varía según el repositorio)
   ├── El ETL estampa 2 + 3 en la metadata del parquet
   └── El ETL deriva y estampa el grupo 5 (provenance)
   Si el ETL estampa más de una tabla, se ajustan los metadatos según el caso (e.g. provenance.quality)

   Cuando la tabla existe─────────┬──────────────────────┐
                                  ▼                      ▼
              script de scanning (acá)          /inspect-table (agente externo,
              grupo 1  mechanical                 todavía no existe)
              + corre los checks del grupo 2    grupo 4  inspect
                                                caduca, lleva ancla
                                                hoy: la ficha lo lleva en null
                                  │                      │
                                  └──────────┬───────────┘
                                             ▼
                                    constructor (build.py)
                                    reparte los 5 grupos (ADR-014)
                                             │
                                             ▼
                  ficha (2 + 3 + 4 + file_columns)  ·  stats (1)
                  audit (5)  ·  índice (una fila por tabla)
```

Nota de construcción para tablas medallion: las reglas del grupo 2 (*keys*) son parte del
meta y del ETL (el ETL las usa para *enforzar* reglas) — `silver` las *aplica*; `bronze`
las ignora.

---

## 4. Reglas duras / Invariantes

1. **Los artefactos finales son derivados. Nunca se editan a mano.** Los arma el
   constructor a partir de los cinco pedazos. Si alguien los edita, el próximo build los
   pisa. Cada pedazo se corrige **en su origen**.
2. **Un `meta` = una tabla de salida.** Siempre. Los scripts que escriben más de una
   salida llevan un bloque por salida.
3. **Cada grupo lleva su propio sello**: cuándo se escribió y contra qué versión de la
   tabla. Los grupos 2, 3 y 5 se estampan junto con la tabla, por lo que su timestamp
   coincide (se graba en el grupo 5, `provenance.written_at`). Los grupos 1
   (`scanned_at`) y 4 (`observed_at`) tienen su propio timestamp.
4. **Nada de estadísticas de la tabla en los grupos 2 y 3.** Si el scanner lo puede
   calcular, es grupo 1. Si requiere entender algo y no sólo contar, es grupo 4. La regla
   de corte está en `meta_contract.yaml`.
5. **Los contratos se chequean por grupo.** Es lo normal durante la autoría: los grupos
   1 y 4 todavía no existen. Un grupo que todavía no existe no se chequea (se apaga con
   los "flags" de chequeo, p. ej. los de `check_table`); dentro del grupo que sí se
   chequea, lo que falta se trata según su `required` (§6).

---

## 5. Formatos, y por qué cada uno

| artefacto | formato | por qué |
|---|---|---|
| YAML de config (grupos 2, 3) | YAML | lo escribe una persona: comentarios, prosa larga, legible |
| metadata del parquet (2, 3, 5) | JSON bajo la key `b'meta'` del schema | no lo lee un humano directamente; viaja con la tabla |
| grupo 1 | **JSON** | puramente máquina-a-máquina, y sus claves son nombres de columna que vienen del dato: el tipado implícito de YAML es un riesgo sin contrapartida |
| grupo 4 | YAML | lo escribe la IA y lo revisa una persona |
| ficha (2 + 3 + 4 + `file_columns`) | YAML | es lo que lee el agente; se diffea |
| stats (1) | JSON | copia del fragmento del scanner, sin reserializar |
| audit (5) | YAML | auditoría; nunca entra al contexto del agente |
| índice | texto pipe-delimited | una línea por tabla (capa "Índice" de ADR-014); pipes porque `description` y `grain` tienen comas |

Todos salen del **mismo build**, así que no pueden divergir. Emitir más de un formato es
barato precisamente porque ninguno es fuente de verdad. Con qué nombre y en qué carpeta
se escribe cada uno: [`etl_strategy.md`](etl_strategy.md).

---

## 6. Chequeo — prioridad B, utility no-bloqueante

No es un gate del pipeline. Su rol es dar la chance de encontrar un problema de esquema
**analizando el dict de metadata directamente**, en vez de enterarse porque algo downstream
(el scanner, un agente, DuckDB levantando la meta del parquet) se cae al intentar leerla
mal formada.

| cuándo se puede correr | qué grupos hay | formato / ubicación | función |
|---|---|---|---|
| **antes** de correr el ETL | 2 + 3 (lo que escribió la persona; el 5 todavía no existe) | el YAML de config | `check_authoring` |
| **después** de correr el ETL | 2 + 3 + 5 (se estampan juntos, misma escritura, regla §4.3) | metadata embebida del parquet | `check_authoring` + `check_provenance` (los dos juntos, desde el footer: `check_table`) |
| **después** de correr el scanner | 1 solo | fragmento JSON | `check_mechanical` |
| **después** de `/inspect-table` | 4 solo | YAML sidecar | `check_inspect` |

`check_mechanical` y `check_inspect` son utilities disponibles: el pipeline
(`run_metadata_etl.py`) no las llama. El scanner trae su propio chequeo
(`ParquetScanner.check()`, que corre con `run(check=True)` y queda en
`ParquetScanner.checked`), pero es de autoconsistencia: compara el conjunto de campos del
resultado contra `fields.py`, no contra el contrato.

En los cuatro casos, dos clases de problema, tratadas distinto:

- **error de esquema** — tipo equivocado, valor fuera de un enum, campo que el contrato no
  declara, o un campo `required: true` ausente o en `null` (también un grupo entero: en
  `meta`, `keys`, `semantics` y `provenance` son `required: true`) → error. El chequeo
  devuelve `False`.
- **deuda** — un campo `required: expected` ausente o en `null` → info en el log. No
  cambia el resultado. Un campo `required: false` ausente no se reporta: `null` es una
  respuesta válida.

El **check de integridad** (corre los checks del grupo 2 contra los datos reales y produce
el veredicto del grupo 1) es otra cosa: abre la tabla, no analiza un dict. Es el script
separado del punto §2 (`ParquetScanner`), no parte de este utility.
