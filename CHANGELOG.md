# Changelog

> High-level summary of the `meta_tools` package (version in `pyproject.toml`), for those
> who import it from another repo. Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
> It covers only the package (the HTML viewer is not versioned and is not listed here); the
> reason behind each decision is in [`docs/ADR/ADR.md`](docs/ADR/ADR.md).

## [0.3.0] — 2026-10-26

First public release. It summarizes the package as it is at this version; earlier versions
were internal and their history is not part of this repository.

### Added
- **Contract** (`meta_tools/meta_contract.yaml`, package data, `contract_version: 2`): the
  five groups of table metadata (`keys`, `semantics`, `provenance`, `mechanical`,
  `inspect`) and, per field, its type from a closed vocabulary, whether it is `required`,
  an `example` and the `agent_rule` that tells the agent how to read it. Foreign keys are
  declared as relations (`keys.foreign_keys`: `{source_col, target_table, target_col}`).
  Loaded with `load_contract` / `CONTRACT_PATH`; a badly declared contract raises
  `ContractError`.
- **Stamping** (`meta_tools.write`, the only hard requirement for a producer's ETL):
  `to_parquet` writes the table and stamps `keys` + `semantics` + `provenance` in the
  parquet footer (`meta` key, with `provenance.writer_version` = `WRITER_VERSION`);
  `get_yaml_provenance` derives `provenance` from the table's config YAML (source YAML and
  its sha256, git commit and user, best effort).
- **Checking against the contract** (`meta_tools.check`): the generic dict-vs-contract
  engine `check_metadata`, and one checker per group: `check_authoring` (keys + semantics,
  before the ETL), `check_provenance`, `check_mechanical` and `check_inspect` (the
  `inspect` sidecar YAML). Readers for config YAMLs: `read_yaml`, `find_meta_blocks`
  (every `meta:` block of a YAML, at any depth).
- **Scanning** (`ParquetScanner`, group `mechanical`): row count, dtypes, nulls, distinct
  values, ranges, and verification of the declared uniques, not-nulls, index columns and
  foreign keys against the data (`fk_orphans` per relation).
- **Pipeline building blocks** (`meta_tools.etl`): `find_tables`, `load_input_sources`,
  `read_stamped_metadata`, `check_table` (a stamped parquet, footer only),
  `tables_by_name`, `check_table_links` (broken `use_instead` / `cross_tables` links, as
  warnings) and `prune_outputs`. The package reads no environment variables: the caller
  injects the paths.
- **Agent artifacts** (`meta_tools.build`): `build_schedule` (per-table schedule: keys +
  semantics + inspect + the real columns of the file), `build_audit` (full provenance),
  `dict_to_flat` (index rows) and `build_reading_key` (what each contract field means for
  the agent).
- **Scripts** (outside the package, run from a clone): `scripts/run_metadata_etl.py`
  (stage 1: checks, scans and writes index, schedules, stats, audit and run log from an ETL
  config; options `--config`, `--dry-run`, `--clean`, `--strict`) and
  `scripts/build_reading_key.py` (stage 2: regenerates `reading_key.yaml`), with the
  templates `config/etl.example.yaml` and `.env.example`.
- **Example dataset** `examples/public/cauchari_ni43101/`: drilling, piezometer, coordinate
  and brine-chemistry tables of a public NI 43-101 report, as CSVs, parquets stamped with
  `to_parquet`, `inspect` sidecars and the outputs of the pipeline (its own config,
  `etl.sampledata.yaml`). Not part of the wheel (ADR-020).
- **Tests** (`tests/`): the contract's self-consistency, the checkers, the scanner and the
  writer, plus the example dataset against the contract (skipped when the example folder
  is absent, e.g. testing an installed wheel).
