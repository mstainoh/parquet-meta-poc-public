"""Run the full metadata ETL pipeline.

Regenerates ALL configured outputs for ALL tables declared under ``input:`` on every
run: mechanical stats, per-table schedules and audit YAMLs, the flat index and the run log.
There is no incremental mode - each run overwrites every table's output unconditionally,
even tables that did not change. Artifacts of tables no longer produced (removed from
``input:``, or failed in this run) stay unless ``--clean`` is passed.

Usage: python scripts/run_metadata_etl.py [--config PATH] [--dry-run] [--clean] [--strict]
       [--debug | --silent]

Config: ``config/etl.yaml`` by default (override with ``--config PATH``) - declares the
``input:`` sources to scan, the ``check_tables`` / ``mechanical.run_params`` parameters
for `check_table` and `ParquetScanner` and the ``output`` path for each artifact listed
below. FK targets are not configured: each table declares them in ``keys.foreign_keys``,
resolved by name among the tables of the run (`tables_by_name`). ``.env`` resolves the env var each of those paths
points at. ``semantics.use_instead`` / ``semantics.cross_tables`` are checked against that
same table-name universe and logged as warnings when they name an unknown table
(`check_table_links`) - this does not fail the run.

Reads:
    - every parquet table under each source declared under ``input:``, including the
      ``keys``/``semantics`` metadata already stamped on it.

Writes (each is independently optional - a missing ``output.<name>`` section logs a
warning and skips it; nothing is written with ``--dry-run``):
    - ``output.mechanical``: one JSON per table (`ParquetScanner.to_json`).
    - ``output.schedules``: one YAML per table (keys+semantics+inspect+file_columns,
      `build_schedule`).
    - ``output.audit``: one YAML per table, full provenance (`build_audit`) - never
      shipped to the agent.
    - ``output.index``: one flat, pipe-delimited ``.txt``, one row per table.
    - ``output.log``: one ``.parquet``, one row per input table with that run's check
      flags, plus ``error_stage`` / ``error`` (null unless the table failed).

With ``--clean``, the mechanical, schedules and audit folders keep only the tables
produced by this run (`prune_outputs`); the index and the log are single files, already
rewritten whole.

Table errors: an unreadable parquet or bad stamped metadata (``OSError``, ``ValueError``,
pyarrow and YAML errors) fails that table only - logged, no artifacts, no index row,
``error_stage`` / ``error`` in its log row - and the script exits 1 at the end. FKs that
point at a table that could not be read are left unverified (it is not an FK target). ``--strict`` aborts on the
first table error instead. Any other exception is a bug and always aborts.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import yaml

from meta_tools.build import build_audit, build_schedule, dict_to_flat
from meta_tools.etl import (
    check_table, check_table_links, load_input_sources, prune_outputs, tables_by_name,
)
from meta_tools.mechanical import ParquetScanner
from project_env import load_project_env, resolve_env

log = logging.getLogger("metadata_etl")

# Errors a single table's file or stamped metadata can raise (unreadable parquet,
# bad footer JSON, a check run with on_error_raise): without --strict they fail that
# table only. Anything else (KeyError, AttributeError, ContractError...) is a bug in
# the code or the contract and always propagates.
_TABLE_ERRORS = (OSError, ValueError, pa.ArrowException, yaml.YAMLError)


class _ColorFormatter(logging.Formatter):
    """ANSI-colors DEBUG (blue) and ERROR/CRITICAL (red); everything else plain."""

    _COLORS = {
        logging.DEBUG: "\033[34m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[31m",
    }
    _RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        color = self._COLORS.get(record.levelno)
        return f"{color}{message}{self._RESET}" if color else message


def parse_args() -> argparse.Namespace:
    """Parse the script's CLI arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments: ``config`` (Path or None - None means the default
        ``config/etl.yaml`` at the repo root), ``dry_run``, ``clean``,
        ``strict``, ``debug``, ``silent``.
    """
    parser = argparse.ArgumentParser(description="Build mechanical metadata from the tables.")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        metavar="PATH",
        help="path to etl.yaml (default: config/etl.yaml at the repo root)",
    )
    parser.add_argument("--dry-run", action="store_true", help="process without writing files")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="delete the mechanical/schedules/audit artifacts of tables not produced by "
             "this run (removed from input: or failed)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="abort on the first table error (default: log it, skip the table, exit 1 "
             "at the end)",
    )
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument("--debug", action="store_true", help="DEBUG logging")
    verbosity.add_argument("--silent", action="store_true", help="warnings and errors only")
    return parser.parse_args()


def _record_failure(
    failures: dict[str, dict[Path, dict[str, str]]],
    source: str,
    path: Path,
    stage: str,
    exc: Exception,
) -> None:
    """Log a table error and keep it for the run log (non-strict mode).

    Parameters
    ----------
    failures : dict[str, dict[Path, dict[str, str]]]
        Source -> table path -> ``{"error_stage", "error"}``; mutated in place.
    source : str
        Name of the table's ``input:`` source.
    path : Path
        The failed table.
    stage : str
        Where it failed: ``read``, ``check``, ``mechanical`` or ``build``.
    exc : Exception
        The error raised.

    Returns
    -------
    None
    """
    failures.setdefault(source, {})[path] = {
        "error_stage": stage,
        "error": f"{type(exc).__name__}: {exc}",
    }
    log.error(
        "[%s] %s failed at %s: %s", source, path.stem, stage, exc,
        exc_info=log.isEnabledFor(logging.DEBUG),
    )


def main() -> None:
    """Run the metadata ETL: load input tables, check stamped metadata,
    compute mechanical stats, build the per-table agent artifacts (schedule +
    audit) and write every configured output (mechanical, schedules, audit,
    index, log).

    Reads the ETL config (``--config``, default ``config/etl.yaml``) for
    source/output configuration; honors ``--dry-run`` (from `parse_args`) to
    process without writing files.

    Returns
    -------
    None
    """
    args = parse_args()
    level = logging.DEBUG if args.debug else logging.WARNING if args.silent else logging.INFO
    handler = logging.StreamHandler()
    handler.setFormatter(_ColorFormatter("%(levelname)s %(message)s"))
    logging.basicConfig(level=level, handlers=[handler])

    # Set up the environment and read the config
    repo_root = load_project_env()
    config_path = args.config if args.config is not None else repo_root / "config" / "etl.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))

    # Table errors, by source and path: {"error_stage", "error"} (only without --strict)
    failures: dict[str, dict[Path, dict[str, str]]] = {}

    # Step 1: input. Read all tables
    input_tables = load_input_sources(config.get("input", []), resolve_env)
    tables: dict[str, dict[Path, pd.DataFrame]] = {}
    for source, paths in input_tables.items():
        tables[source] = {}
        for path in paths:
            try:
                tables[source][path] = pd.read_parquet(path)
            except _TABLE_ERRORS as exc:
                if args.strict:
                    raise
                _record_failure(failures, source, path, "read", exc)

    # Step 2: FK targets for the scanner, by table name (keys.foreign_keys,
    # ADR-017). A table that could not be read is not among them.
    mechanical_config = config["mechanical"]
    if "foreign_keys" in mechanical_config:
        log.warning("mechanical.foreign_keys is ignored: each table declares its FK targets")
    pk_sources = tables_by_name(tables)
    run_params = mechanical_config.get("run_params", {})

    # Step 3: per table - check the stamped metadata against the contract,
    # mechanical metadata, and the agent artifacts (ADR-014): schedule (keys+
    # semantics+inspect+file_columns) and audit (full provenance)
    check_config = config.get("check_tables", {})
    checks: dict[str, dict[Path, dict[str, bool | None]]] = {}
    mechanical_metadata: dict[str, dict[Path, ParquetScanner]] = {}
    schedule_metadata: dict[str, dict[Path, dict]] = {}
    audit_metadata: dict[str, dict[Path, dict | None]] = {}
    for source, source_tables in tables.items():
        checks[source] = {}
        mechanical_metadata[source] = {}
        schedule_metadata[source] = {}
        audit_metadata[source] = {}
        n_invalid = 0
        for path in source_tables:
            stage = "check"
            try:
                flags = checks[source][path] = check_table(path, **check_config)
                n_invalid += any(result is False for result in flags.values())
                stage = "mechanical"
                scanner = ParquetScanner(path)
                scanner.run(pk_sources=pk_sources, **run_params)
                flags.update(
                    uniques=scanner.result.get("uniques_verified"),
                    not_nulls=scanner.result.get("not_nulls_verified"),
                    index_columns=scanner.result.get("index_columns_verified"),
                    foreign_keys=scanner.result.get("fk_verified"),
                    mechanical=scanner.checked,
                )
                stage = "build"
                schedule = build_schedule(path, scanner)
                audit = build_audit(path)
            except _TABLE_ERRORS as exc:
                if args.strict:
                    raise
                _record_failure(failures, source, path, stage, exc)
                continue
            mechanical_metadata[source][path] = scanner
            schedule_metadata[source][path] = schedule
            audit_metadata[source][path] = audit
        if n_invalid:
            log.warning("%s: %d tables with invalid metadata", source, n_invalid)

    # Cross-table links (semantics.use_instead / semantics.cross_tables) against
    # the same table-name universe used to resolve FK targets (pk_sources).
    broken_links = check_table_links(pk_sources.keys(), schedule_metadata)
    if broken_links:
        log.warning("%d broken use_instead/cross_tables links", len(broken_links))

    # Tables produced by this run, by source: what --clean keeps
    produced = {
        source: [path.stem for path in scanners]
        for source, scanners in mechanical_metadata.items()
    }

    # Step 4: output
    output_cfg = config['output']

    # Step 4.a: mechanical
    output_cfg_mech = output_cfg.get('mechanical')
    if output_cfg_mech is None:
        log.warning('No mechanical output data configuration')
    else:
        target_folder = resolve_env(**output_cfg_mech['path'])
        for src, scanners in mechanical_metadata.items():
            source_folder = target_folder / src
            if not args.dry_run:
                source_folder.mkdir(parents=True, exist_ok=True)
            for tbl_path, scanner in scanners.items():
                output_path = source_folder / f"{tbl_path.stem}.json"
                if not args.dry_run:
                    scanner.to_json(output_path)
        action = "would be written" if args.dry_run else "written"
        log.info(
            "mechanical: %d tables %s",
            sum(len(scanners) for scanners in mechanical_metadata.values()),
            action,
        )
        if args.clean:
            prune_outputs(target_folder, produced, ".json", dry_run=args.dry_run)

    # Step 4.b: schedules (one YAML per table, keys+semantics+inspect+file_columns)
    output_cfg_schedules = output_cfg.get('schedules')
    if output_cfg_schedules is None:
        log.warning('No schedules output data configuration')
    else:
        target_folder = resolve_env(**output_cfg_schedules['path'])
        for src, tables_schedules in schedule_metadata.items():
            source_folder = target_folder / src
            if not args.dry_run:
                source_folder.mkdir(parents=True, exist_ok=True)
            for tbl_path, schedule in tables_schedules.items():
                output_path = source_folder / f"{tbl_path.stem}.yaml"
                if not args.dry_run:
                    output_path.write_text(
                        yaml.safe_dump(schedule, sort_keys=False, allow_unicode=True),
                        encoding="utf-8",
                    )
        action = "would be written" if args.dry_run else "written"
        log.info(
            "schedules: %d tables %s",
            sum(len(tf) for tf in schedule_metadata.values()),
            action,
        )
        if args.clean:
            prune_outputs(target_folder, produced, ".yaml", dry_run=args.dry_run)

    # Step 4.c: audit (one YAML per table, full provenance - never shipped to the agent)
    output_cfg_audit = output_cfg.get('audit')
    if output_cfg_audit is None:
        log.warning('No audit output data configuration')
    else:
        target_folder = resolve_env(**output_cfg_audit['path'])
        for src, tables_audit in audit_metadata.items():
            source_folder = target_folder / src
            if not args.dry_run:
                source_folder.mkdir(parents=True, exist_ok=True)
            for tbl_path, provenance in tables_audit.items():
                output_path = source_folder / f"{tbl_path.stem}.yaml"
                if not args.dry_run:
                    output_path.write_text(
                        yaml.safe_dump(provenance, sort_keys=False, allow_unicode=True),
                        encoding="utf-8",
                    )
        action = "would be written" if args.dry_run else "written"
        log.info(
            "audit: %d tables %s",
            sum(len(ta) for ta in audit_metadata.values()),
            action,
        )
        if args.clean:
            prune_outputs(target_folder, produced, ".yaml", dry_run=args.dry_run)

    # Step 4.d: index (<output.index.name>.txt, one row per table, pipe-delimited, whole catalog)
    output_cfg_index = output_cfg.get('index')
    if output_cfg_index is None:
        log.warning('No index output data configuration')
    else:
        columns = output_cfg_index.get('params', {}).get('columns', {})
        rows = []
        for src, tables_schedules in schedule_metadata.items():
            for tbl_path, schedule in tables_schedules.items():
                combined = {
                    **schedule,
                    "mechanical": mechanical_metadata[src][tbl_path].result,
                    "provenance": audit_metadata[src][tbl_path],
                }
                flat = dict_to_flat(json.loads(json.dumps(combined, default=str)))
                row: dict[str, object] = {"table": tbl_path.stem}
                for column, path in columns.items():
                    value = flat.get(path)
                    row[column] = value.replace("\n", " ") if isinstance(value, str) else value
                rows.append(row)
        target_folder = resolve_env(**output_cfg_index['path'])
        output_path = target_folder / f"{output_cfg_index['name']}.txt"
        if not args.dry_run:
            target_folder.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows).to_csv(output_path, sep="|", index=False, encoding="utf-8")
        action = "would be written" if args.dry_run else "written"
        log.info("index: %d tables, %s (%s)", len(rows), action, output_path)

    # Step 5: log (parquet, one row per input table with the run's status)
    output_cfg_log = output_cfg.get('log')
    if output_cfg_log is None:
        log.warning('No log output data configuration')
    else:
        rows = [
            {
                "source": src,
                "table": tbl_path.stem,
                **checks.get(src, {}).get(tbl_path, {}),
                "error_stage": None,
                "error": None,
                **failures.get(src, {}).get(tbl_path, {}),
            }
            for src, paths in input_tables.items()
            for tbl_path in paths
        ]
        target_folder = resolve_env(**output_cfg_log['path'])
        output_path = target_folder / f"{output_cfg_log['name']}.parquet"
        if not args.dry_run:
            target_folder.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows).to_parquet(output_path)
        action = "would be written" if args.dry_run else "written"
        log.info("log: %d tables, %s (%s)", len(rows), action, output_path)

    # Step 6: a failed table fails the run, after writing everything else
    failed = [f"{src}/{path.stem}" for src, paths in failures.items() for path in paths]
    if failed:
        log.error("%d tables failed: %s", len(failed), ", ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()