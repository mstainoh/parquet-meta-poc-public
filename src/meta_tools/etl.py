"""Small ETL building blocks for table metadata."""

from __future__ import annotations

import re
import json
import logging
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any, Pattern

import pandas as pd
import pyarrow.parquet as pq

from .check import check_authoring, check_provenance

log = logging.getLogger(__name__)

__all__ = [
    "check_table",
    "check_table_links",
    "find_tables",
    "load_input_sources",
    "prune_outputs",
    "read_stamped_metadata",
    "tables_by_name",
]


def read_stamped_metadata(table: str | Path) -> dict:
    """Read the ``meta`` footer stamped by ``write.parquet.to_parquet``.

    Reads only the Parquet schema/footer, not table rows, and does not
    validate the block (see `check_table`).

    Parameters
    ----------
    table : str or Path
        Path to the parquet file.

    Returns
    -------
    dict
        The decoded ``meta`` block as stamped, or an empty dict if the table
        has no ``meta`` footer. Per the contract the expected keys are
        ``keys``, ``semantics``, ``provenance`` and the optional
        ``schema_version`` (ADR-013), but they depend on what the producer
        stamped and are not guaranteed.
    """
    raw_meta = (pq.read_schema(Path(table)).metadata or {}).get(b"meta")
    return json.loads(raw_meta) if raw_meta else {}


def check_table(
    table: str | Path,
    keys: bool = False,
    semantics: bool = False,
    provenance: bool = False,
    on_error_raise: bool = False,
) -> dict[str, bool | None]:
    """Check metadata already stamped in one Parquet table.

    ``keys`` and ``semantics`` are one contract surface and therefore call
    ``check_authoring`` together when either flag is enabled. ``provenance``
    calls ``check_provenance`` independently. The checks read only the Parquet
    footer metadata, not table rows. A field missing from the footer is
    passed to the check as None.

    Parameters
    ----------
    table : str or Path
        Path to the parquet file.
    keys, semantics : bool, default False
        Check the corresponding field via ``check_authoring``.
    provenance : bool, default False
        Check the ``provenance`` + ``schema_version`` block via
        ``check_provenance``.
    on_error_raise : bool, default False
        Forwarded to the underlying check: raise instead of logging and
        returning False on a schema error.

    Returns
    -------
    dict[str, bool or None]
        ``{"keys", "semantics", "provenance"}``, each True/False if checked,
        or None if the corresponding flag was False.
    """
    path = Path(table)
    check_authoring_surface = keys or semantics
    metadata = read_stamped_metadata(path)
    results: dict[str, bool | None] = {
        "keys": None,
        "semantics": None,
        "provenance": None,
    }
    if check_authoring_surface:
        authoring_valid = check_authoring(
            {
                "keys": metadata.get("keys"),
                "semantics": metadata.get("semantics"),
            },
            on_error_raise=on_error_raise,
            label=path.name,
        )
        results["keys"] = authoring_valid if keys else None
        results["semantics"] = authoring_valid if semantics else None
    if provenance:
        results["provenance"] = check_provenance(
            {
                "schema_version": metadata.get("schema_version"),
                "provenance": metadata.get("provenance"),
            },
            on_error_raise=on_error_raise,
            label=path.name,
        )
    return results


def find_tables(
    path: str | Path,
    recurse: bool = True,
    include: str | Pattern[str] | None = None,
    exclude: str | Pattern[str] | None = None,
) -> dict[Path, str]:
    """Find parquet tables below a folder.

    Parameters
    ----------
    path : str or Path
        Root folder to search.
    recurse : bool, default True
        Search nested folders when true.
    include, exclude : str, compiled regex or None
        Regexes matched against each table path relative to the search folder.
        ``include`` must match and ``exclude`` must not match.

    Returns
    -------
    dict[Path, str]
        Sorted parquet paths mapped to their table names (file stems).

    Raises
    ------
    FileNotFoundError
        If `path` is not a directory.
    """
    root = Path(path)
    if not root.is_dir():
        raise FileNotFoundError(f"tables folder not found at {root}")

    include_pattern = re.compile(include) if isinstance(include, str) else include
    exclude_pattern = re.compile(exclude) if isinstance(exclude, str) else exclude
    candidates = root.rglob("*") if recurse else root.glob("*")
    tables: dict[Path, str] = {}
    for candidate in candidates:
        if not candidate.is_file() or candidate.suffix.lower() != ".parquet":
            continue
        relative = candidate.relative_to(root).as_posix()
        if include_pattern is not None and include_pattern.search(relative) is None:
            continue
        if exclude_pattern is not None and exclude_pattern.search(relative) is not None:
            continue
        tables[candidate] = candidate.stem

    return dict(sorted(tables.items(), key=lambda item: item[0].as_posix().lower()))


def load_input_sources(
    input_sources: Iterable[Mapping[str, Any]],
    resolve_root: Callable[..., Path],
) -> dict[str, dict[Path, str]]:
    """Resolve each ``input:`` source of an ETL config and find its tables.

    Knows the shape of an ``input:`` entry but not what its ``path`` node
    means: `resolve_root` turns that node into the source's root folder, so
    env vars, ``.env`` files or any other path convention stay out of the
    package. Errors raised by `resolve_root` propagate unchanged (e.g.
    RuntimeError from ``resolve_env`` for an unset env var).

    Parameters
    ----------
    input_sources : Iterable[Mapping[str, Any]]
        The ``input:`` list of a parsed ETL config. Each entry has ``name``,
        ``path`` (a mapping, unpacked into `resolve_root`) and optional
        ``params`` (keyword arguments of `find_tables`).
    resolve_root : Callable[..., Path]
        Called as ``resolve_root(**path)`` for each entry; returns the root
        folder to scan. The scripts pass ``project_env.resolve_env`` (keys
        ``env`` + optional ``subfolder``), the same call they use for each
        ``output`` path.

    Returns
    -------
    dict[str, dict[Path, str]]
        One item per source, keyed by its ``name`` (a repeated ``name``
        overwrites the earlier one). Each value maps every parquet path found
        under that source's root to its table name (file stem), as returned
        by `find_tables`.

    Raises
    ------
    KeyError
        If an entry lacks ``name`` or ``path``.
    TypeError
        If ``path`` is not a mapping, or its keys do not match the
        parameters of `resolve_root` (e.g. ``env`` missing for
        ``resolve_env``).
    FileNotFoundError
        If a source root is not a folder (from `find_tables`).
    """
    sources: dict[str, dict[Path, str]] = {}
    for source in input_sources:
        root = resolve_root(**source["path"])
        sources[source["name"]] = find_tables(root, **source.get("params", {}))
    return sources


def tables_by_name(
    tables: Mapping[str, Mapping[Path, pd.DataFrame]],
) -> dict[str, pd.DataFrame]:
    """Index the loaded tables of a run by name, as FK targets.

    The name is the file stem - what ``keys.foreign_keys[].target_table``
    declares. A name found more than once (across or within sources) is
    ambiguous: it is left out with a warning, so the FKs that point at it
    stay unverified.

    Parameters
    ----------
    tables : Mapping[str, Mapping[Path, pandas.DataFrame]]
        Loaded tables, keyed by source name and then by path (as returned
        by `find_tables`, with DataFrames loaded per path).

    Returns
    -------
    dict[str, pandas.DataFrame]
        Table name -> DataFrame: the ``pk_sources`` of
        `ParquetScanner.run`.
    """
    paths: dict[str, list[Path]] = {}
    by_name: dict[str, pd.DataFrame] = {}
    for source_tables in tables.values():
        for path, df in source_tables.items():
            paths.setdefault(path.stem, []).append(path)
            by_name[path.stem] = df
    for name, found in paths.items():
        if len(found) > 1:
            log.warning("table name %s is not unique, not usable as FK target: %s", name, found)
            del by_name[name]
    return by_name


def check_table_links(
    known_tables: Iterable[str],
    schedules: Mapping[str, Mapping[Path, dict]],
) -> list[str]:
    """Flag `semantics.use_instead` / `semantics.cross_tables` that do not
    name a table found in this run.

    Uses the same table-name universe as FK target resolution
    (`tables_by_name`, ADR-017): a name that is ambiguous (repeated across
    or within sources) is not "known" here either.

    Parameters
    ----------
    known_tables : Iterable[str]
        Table names to consider valid targets, e.g. ``tables_by_name(tables)``
        (or its ``.keys()``) for the current run.
    schedules : Mapping[str, Mapping[Path, dict]]
        Per-table schedules (`build_schedule`), keyed by source name and then
        by path, as assembled in the ETL script.

    Returns
    -------
    list[str]
        One message per broken link, already logged as a warning.
    """
    known = set(known_tables)
    problems: list[str] = []
    for source, tables in schedules.items():
        for path, schedule in tables.items():
            semantics = schedule.get("semantics") or {}
            table = f"{source}/{path.stem}"
            use_instead = semantics.get("use_instead")
            if use_instead and use_instead not in known:
                problems.append(f"{table}: use_instead names an unknown table: {use_instead}")
            for target in semantics.get("cross_tables") or []:
                if target not in known:
                    problems.append(f"{table}: cross_tables names an unknown table: {target}")
    for problem in problems:
        log.warning(problem)
    return problems


def prune_outputs(
    folder: str | Path,
    keep: Mapping[str, Iterable[str]],
    suffix: str,
    dry_run: bool = False,
) -> list[Path]:
    """Delete the per-table artifacts of tables that are no longer produced.

    Per-table artifacts live at ``<folder>/<source>/<table><suffix>``. Inside
    the subfolder of each source in `keep`, every file with `suffix` whose
    stem is not listed is deleted. Nothing else is touched - other suffixes,
    nested folders, and subfolders of sources not in `keep` (logged as a
    warning) - so a misconfigured `folder` cannot wipe unrelated files.

    Parameters
    ----------
    folder : str or Path
        Output root of one artifact (e.g. the schedules folder). A missing
        folder is nothing to prune.
    keep : Mapping[str, Iterable[str]]
        Source name -> table names (file stems) to keep. A source mapped to
        an empty iterable loses all its artifacts.
    suffix : str
        Artifact extension, dot included (``".json"``, ``".yaml"``).
    dry_run : bool, default False
        Log what would be deleted without deleting it.

    Returns
    -------
    list[Path]
        The artifacts deleted (or that would be, with `dry_run`).
    """
    folder = Path(folder)
    if not folder.is_dir():
        return []
    stale: list[Path] = []
    for source_folder in sorted(p for p in folder.iterdir() if p.is_dir()):
        if source_folder.name not in keep:
            log.warning("prune: %s is not a current source, left untouched", source_folder)
            continue
        kept = set(keep[source_folder.name])
        stale.extend(
            artifact for artifact in sorted(source_folder.glob(f"*{suffix}"))
            if artifact.is_file() and artifact.stem not in kept
        )
    for artifact in stale:
        if dry_run:
            log.info("prune: would delete %s", artifact)
        else:
            artifact.unlink()
            log.info("prune: deleted %s", artifact)
    return stale