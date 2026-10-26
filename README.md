# parquet-meta-contract

Metadata contract + tools (`meta_tools`) so that an AI agent can write SQL over Parquet
tables from their metadata, without seeing the data.

Separating "what the data means" from "the data itself" lets an LLM help build queries by
reading the description of the tables instead of their rows. Each table carries its
metadata in its own parquet footer; a pipeline turns it into small text artifacts (a
catalog, one schedule per table, stats) that the agent reads by layers, loading only what
each question needs.

**Contents:** [What is in the repo](#what-is-in-the-repo) ·
[How it works](#how-it-works) ·
[Artifacts and who reads them](#artifacts-and-who-reads-them) ·
[Installation](#installation) · [Python API](#python-api) ·
[Running the pipeline](#running-the-pipeline) · [Privacy](#privacy) ·
[Documentation map](#documentation-map)

## What is in the repo

| Part | Where | What it is |
|---|---|---|
| Contract | [`meta_contract.yaml`](src/meta_tools/meta_contract.yaml) | The spec: the five groups of metadata and, per field, its type, whether it is required and the `agent_rule` that tells the agent how to read it. Ships with the package |
| Package | [`src/meta_tools/`](src/meta_tools/) | `meta_tools`: stamp the metadata into a parquet, check it against the contract, scan the table, build the agent's artifacts ([Python API](#python-api)) |
| Scripts | [`scripts/`](scripts/) | The metadata pipeline, run from a clone (not installed): `run_metadata_etl.py`, `build_reading_key.py`, and `project_env.py`, which loads `.env` for them |
| Templates | [`config/etl.example.yaml`](config/etl.example.yaml), [`.env.example`](.env.example) | Commented templates of the pipeline config and of the `.env` that points it at your folders |
| Reading key | [`reading_key.yaml`](reading_key.yaml) | What each contract field means for the agent. Generated from the contract, committed |
| Viewer | [`index.html`](index.html) | A Parquet viewer + SQL editor in a single HTML file (DuckDB-Wasm, no backend), to explore the tables and the artifacts by hand. Not part of the package: it imports nothing from it. It can also load GeoJSON layers, expected already processed (WGS84, valid geometry) by whatever pipeline produced them — this package does not generate GeoJSON |
| Tests | [`tests/`](tests/) | pytest suite of the package and the contract, including the example dataset checked end to end |
| Example dataset | [`examples/public/cauchari_ni43101/`](examples/public/cauchari_ni43101/) | Real, public data stamped with the package: drilling, piezometer, coordinate and brine-chemistry tables of a public NI 43-101 report (Cauchari-Olaroz). CSVs (raw and cleaned), stamped parquets, `inspect` findings and the outputs of the pipeline. See its [`DATASET.md`](examples/public/cauchari_ni43101/DATASET.md) |

The metadata of a table has five groups: `keys` and `semantics`, written by hand by the
table's author; `provenance`, derived when the table is written; `mechanical`, computed by
scanning the table; and `inspect`, findings of an AI that looked at the table (nothing in
this repo produces it yet). Who writes each group, when, and why they are kept apart:
[`metadata_model.md`](docs/model/metadata_model.md).

## How it works

```text
producer's ETL (any repo that writes tables)
  config YAML, `meta:` block -- keys + semantics, by hand -- check_authoring (optional)
  get_yaml_provenance        -- provenance, derived from that YAML
  to_parquet  ──►  <TABLE>.parquet: the rows, plus `meta` in the footer
                   (keys + semantics + provenance)
        │
        ▼
stage 1 · scripts/run_metadata_etl.py, for every table under the config's `input:`
  check_table       re-checks the stamped metadata against the contract (footer only)
  ParquetScanner    stats + verdict on the declared keys (reads every row, locally)
  build_schedule, build_audit
  check_table_links use_instead / cross_tables name tables of the run (warning only)
        ──►  index · schedules · stats · audit · run log

stage 2 · scripts/build_reading_key.py, from the contract alone
        ──►  reading_key.yaml

stage 3 · publish the artifacts where the consumers read them (deployment-specific)
        ──►  agent:  rules + index  →  schedules of the chosen tables  →  stats, if needed
        ──►  viewer: tables + schedules + index, loaded in the browser
```

1. **Stamp** (producer side, in whatever repo writes the table). The author declares
   `keys` + `semantics` in the `meta:` block of the table's config YAML, and can validate
   them before running (`check_authoring`). The ETL writes the table with `to_parquet`,
   which stamps them into the parquet footer together with `provenance`
   (`get_yaml_provenance`). `meta_tools.write` is all a producer has to import.
2. **Build the metadata** (`scripts/run_metadata_etl.py`). For every table of the sources
   in the config's `input:`, it re-checks the stamped metadata against the contract, scans
   the table (`ParquetScanner`: stats, plus verification of the declared uniques,
   not-nulls, index and foreign keys against the data) and writes the artifacts below. A
   mismatch is flagged, not fatal. Then it checks that the tables named in
   `semantics.use_instead` / `semantics.cross_tables` are among the tables of the run
   (`check_table_links`); a broken link is only a warning.
3. **Build the reading key** (`scripts/build_reading_key.py`). Regenerates
   `reading_key.yaml` from the contract's `agent_rule`s. Run it when a rule changes; the
   output is committed.
4. **Publish and consume.** Copying the artifacts to where the agent and the viewer read
   them depends on each deployment: there is no script for it here. The agent reads them
   by layers (next section). The viewer loads tables, schedules and index locally and never
   calls the agent ([`viewer.md`](docs/html/viewer.md)).

How to run stages 1 and 2: [Running the pipeline](#running-the-pipeline).

## Artifacts and who reads them

The pipeline's artifacts are derived: each run rebuilds them, and they are never edited by
hand (a fix goes to the table's metadata, at its source, or to the contract). The agent
loads them by layers, so what travels on every question stays small as the catalog grows
(ADR-014):

| Layer / artifact | Content | Written by | Agent | Viewer |
|---|---|---|---|---|
| Rules | cross-cutting instructions for the agent (a prompt written by the deployer, not part of this repo) + `reading_key.yaml`, what each contract field means | the deployer; stage 2 | always | — |
| Index | the catalog: one row per table, with the columns the config picks (description, grain, temporal scope, redirection, quality, update dates...) | stage 1, `output.index`: one pipe-delimited `.txt` | always: it picks the tables from it, or answers from it ("what is there", "when was it updated") | button **Cargar índice**, as the SQL view `table_index` |
| Schedule (*ficha*) | per table: `keys` + `semantics` + `inspect` + `file_columns`, the real columns of the file | stage 1, `output.schedules`: one YAML per table | second round, only for the chosen tables | button **Cargar metadata**, shown as text |
| Stats | per table: the full `mechanical` group (row count, dtypes, nulls, distinct values, ranges, verification of the declared keys, FK orphans) | stage 1, `output.mechanical`: one JSON per table | only if the question needs them; the agent decides. They carry real values: see [Privacy](#privacy) | not read |
| Audit | per table: the full `provenance` (source config verbatim, user, commit) | stage 1, `output.audit`: one YAML per table | never | skipped (folder `99_audit`) |
| Run log | one row per input table: the check flags of the last run, and `error_stage` / `error` | stage 1, `output.log`: one parquet | no: it is for whoever runs the pipeline | as any parquet |

A question goes in two rounds. First, rules + index + the question: the agent picks the
tables, or answers from the index, or says it cannot answer. Then the schedules of those
tables are added and the agent writes the query; it asks for a table's stats only when
the answer depends on checking something the schedule declares but does not guarantee
(uniqueness, nulls, foreign keys, the real range). The query runs locally; if it fails,
only the error message goes back to the agent, never rows. How the files reach the agent
(a chat project with the files attached, or an API call) is up to each deployment.

Why it is split this way: ADR-014 in [`ADR.md`](docs/ADR/ADR.md). Formats and why each one:
[`metadata_model.md`](docs/model/metadata_model.md), §5. Config keys, folders and file
names: [`etl_strategy.md`](docs/model/etl_strategy.md).

## Installation

Requires Python >= 3.12. It is not published on PyPI: install it from a tagged version
(`vX.Y.Z`, see [`CHANGELOG.md`](CHANGELOG.md)) of the repository:

```bash
pip install "git+https://github.com/mstainoh/parquet-meta-poc-public.git@vX.Y.Z"
```

From source (development, tests and scripts):

```bash
git clone https://github.com/mstainoh/parquet-meta-poc-public.git
cd parquet-meta-poc-public
pip install -e ".[dev]"   # adds pytest and python-dotenv
pytest
```

The package is imported as `meta_tools`.

The dependencies have no upper bound. Tested with Python 3.12.7, PyYAML 6.0.3, pandas
3.0.5 and pyarrow 25.0.1.

## Python API

Everything below is imported from `meta_tools`; signatures and options are in the
docstrings.

| To | Use |
|---|---|
| Stamp a table (the producer's ETL; the only hard requirement) | `to_parquet`, `get_yaml_provenance` |
| Check metadata against the contract | `check_authoring` (keys + semantics, before the ETL), `check_table` (a stamped parquet, footer only), `check_provenance`, `check_mechanical`, `check_inspect`; the generic engine `check_metadata`, plus `load_contract`, `CONTRACT_PATH`, `ContractError` |
| Read config YAMLs | `read_yaml`, `find_meta_blocks` (every `meta:` block of a YAML, at any depth) |
| Scan a table (group `mechanical`) | `ParquetScanner` |
| Build the artifacts | `build_schedule`, `build_audit`, `dict_to_flat` (index rows), `build_reading_key` |
| Pipeline building blocks | `find_tables`, `load_input_sources`, `read_stamped_metadata`, `tables_by_name`, `check_table_links`, `prune_outputs` |

```python
from meta_tools import (
    check_authoring, to_parquet, get_yaml_provenance, check_table, ParquetScanner,
    build_schedule,
)

# keys + semantics (groups 2+3): written by hand by the table's author,
# usually in the `meta:` block of the config YAML that defines it
meta = {
    "keys": {
        "uniques": ["well_id", "datetime"],
        "not_nulls": ["well_id", "datetime"],
        "foreign_keys": [{"source_col": "well_id", "target_table": "TBL_WELLS"}],
    },
    "semantics": {
        "description": "water level readings for each monitoring well",
        "grain": "one row per well and reading time",
        "temporal_scope": "full_history",
        "column_info": {"level_m": "depth to water below top of casing, in meters"},
    },
}

# 1. Before the ETL: validate keys + semantics against the contract.
#    Returns True/False and logs the errors; on_error_raise=True to make it raise.
check_authoring(meta)

# 2. When writing the table: provenance (group 5) from the config YAML
#    (config/water_levels.yaml) and everything stamped in the parquet footer
provenance = get_yaml_provenance(
    "water_levels", source_folder="config", repo_root=".",
    repo="warehouse", username="analyst", quality="silver",
)
to_parquet(df, "water_levels.parquet", metadata={**meta, "provenance": provenance})

# 3. Afterwards: re-check what was stamped (reads only the footer, not the rows)
check_table("water_levels.parquet", keys=True, semantics=True, provenance=True)
# -> {"keys": True, "semantics": True, "provenance": True}

# 4. Scan the table (group 1): stats + verification of the declared keys
#    against the data. pk_sources: referenced table (target_table) -> DataFrame
scanner = ParquetScanner("water_levels.parquet")
scanner.run(pk_sources={"TBL_WELLS": wells_df})
scanner.to_json("water_levels.mechanical.json")

# 5. What the agent reads per table: keys + semantics + inspect + file_columns
schedule = build_schedule("water_levels.parquet", scanner)
```

The checkers share the signature of `check_authoring` (`data`, plus `on_error_raise` and
`label`), but each one expects its own group in `data`:

| Checker | `data` |
|---|---|
| `check_authoring` | `{"keys": ..., "semantics": ...}`, as in the `meta:` block |
| `check_provenance` | `{"provenance": ..., "schema_version": ...}` as stamped in the footer (`read_stamped_metadata`), not the output of `get_yaml_provenance`: `writer_version` is required and only `to_parquet` adds it |
| `check_mechanical` | the scanner's result (`scanner.result`, or the stats JSON) |
| `check_inspect` | the `inspect` sidecar YAML, parsed |

For a stamped table, `check_table` runs the first two from the footer.

## Running the pipeline

The scripts run from a clone installed with `pip install -e ".[dev]"`: they import
`meta_tools`, and `run_metadata_etl.py` reads `.env` with `python-dotenv`.

```bash
cp .env.example .env                          # point the variables at your folders
cp config/etl.example.yaml config/etl.yaml    # adapt the sources (input:) and artifacts (output:)
python scripts/run_metadata_etl.py --dry-run  # process every table, write nothing
python scripts/run_metadata_etl.py            # stage 1
python scripts/build_reading_key.py           # stage 2, when a field's agent_rule changes
```

The config holds no paths: each `path:` names an environment variable plus an optional
subfolder, and `.env` gives the variable its value. The package itself reads no
environment variable; used from your own code, it takes paths. If you use the viewer, keep
the audit in a folder named `99_audit`, as the template does: the viewer skips the YAML
files under it. Every option (`--config`, `--clean`, `--strict`...), the error handling
and the output layout: [`etl_strategy.md`](docs/model/etl_strategy.md).

The example dataset ships its own config. From the repo root, with `SAMPLEDATAPATH`
pointing at `examples/public/cauchari_ni43101`:

```bash
python scripts/run_metadata_etl.py --config examples/public/cauchari_ni43101/etl.sampledata.yaml --clean
```

## Privacy

The package transmits nothing: it makes no network calls nor calls to AI services;
everything runs locally. But it does read data:

- `ParquetScanner` reads every row of the table, locally, to compute the stats and verify
  the declared keys.
- `check_table`, `build_schedule` and `build_audit` read only the metadata stamped in the
  parquet footer, not the rows.

No artifact copies rows of a table, but some carry real values from the table or its
environment:

| Where | Real values |
|---|---|
| Stats: `mechanical.min_max` | minimum and maximum of each numeric or date column |
| Stats: `mechanical.fk_orphans` | every value of a foreign key that does not appear in the referenced table, with no cap |
| Audit, and the parquet footer: `provenance` | the full config YAML (`source_yaml`), the `username`, the `git_commit` and the path of the YAML |
| Schedule, and the parquet footer: `semantics` | hand-written text: whatever the author writes |
| Index | the fields the config picks, which can include any of the above |

The rest of `mechanical` describes the table without containing it (column names and
types, counts of rows, nulls and distinct values).

> **Disclaimer: the stats may reach the agent.** Rows never leave: that is the line this
> package draws. The stats are metadata and may travel to the agent when the question
> needs them (ADR-014), real values included. Whether `min_max` and `fk_orphans` may leave
> your environment depends on your data and context: **it is the deployer's call, not the
> package's** (ADR-019, in [`ADR.md`](docs/ADR/ADR.md)). The package does not filter those
> values. The schedule does not carry them; the stats JSON does, and the index does if the
> config picks them. Check which artifacts you share before handing them to an external
> model.

The viewer keeps tables and metadata in the browser; what does leave it is listed in
[`viewer.md`](docs/html/viewer.md), §6.

## Documentation map

| Document | Language | What it holds | Read it when |
|---|---|---|---|
| `README.md` | English | This page: what the repo is, how it works, the artifacts, install, API, privacy | First |
| [`docs/model/metadata_model.md`](docs/model/metadata_model.md) | Spanish | The five-group model: what is written, by whom, when and where; lifecycle, invariants, formats, what to check when | Before writing metadata, or touching the contract or `meta_tools` |
| [`src/meta_tools/meta_contract.yaml`](src/meta_tools/meta_contract.yaml) | English comments; `agent_rule` and `value_descriptions` text in Spanish (and so [`reading_key.yaml`](reading_key.yaml)) | The spec, field by field: type, `required`, `agent_rule`, example | For field-level questions |
| [`docs/model/etl_strategy.md`](docs/model/etl_strategy.md) | Spanish | Running the pipeline: stages, config and `.env`, options, errors, output layout | Before setting up or running the pipeline |
| [`docs/html/viewer.md`](docs/html/viewer.md) | Spanish | The viewer: usage, loading metadata, the agent flow, what leaves the browser, code map, limits | Before using or changing `index.html` |
| [`docs/ADR/ADR.md`](docs/ADR/ADR.md) | Spanish | Design decisions and why, superseded ones included | Before changing a design decision, or to know why something is the way it is |
| [`examples/public/cauchari_ni43101/DATASET.md`](examples/public/cauchari_ni43101/DATASET.md) | English | The example dataset: source, layout, how it was built, tables, caveats and findings | Before using the example, or as a model of a documented dataset |
| [`CHANGELOG.md`](CHANGELOG.md) | English | Changes of the `meta_tools` package by version (the viewer is not versioned) | When upgrading |
| [`config/etl.example.yaml`](config/etl.example.yaml), [`.env.example`](.env.example) | English | Commented templates of the pipeline config and the `.env` | When setting up the pipeline |
| [`CLAUDE.md`](CLAUDE.md) | English | Contributor working rules and the module-by-module architecture | Before contributing |
