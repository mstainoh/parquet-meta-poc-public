"""Build the metadata artifacts of ADR-014: per-table schedule and audit, the
flattening used for the index, and the contract-wide reading key."""

from __future__ import annotations

import json
from pathlib import Path

from .check.contract import load_contract
from .etl import read_stamped_metadata
from .mechanical import ParquetScanner

__all__ = ["build_schedule", "build_audit", "dict_to_flat", "build_reading_key"]


def build_schedule(table: str | Path, scanner: ParquetScanner) -> dict:
    """Build one table's schedule: the canonical YAML minus ``provenance`` and
    ``mechanical`` (ADR-014).

    Parameters
    ----------
    table : str or Path
        Parquet path. Only used to read back the stamped ``keys`` and
        ``semantics`` (groups 2+3), plus the optional ``schema_version``,
        via `read_stamped_metadata`.
    scanner : ParquetScanner
        At least ``compute_mechanical()`` already run (``run()`` in the
        pipeline). Only ``file_columns`` is pulled from its `result`.

    Returns
    -------
    dict
        ``{"schema_version", "keys", "semantics", "inspect", "file_columns"}``.
        ``file_columns`` is promoted out of ``mechanical`` on purpose: it is
        not opt-in, it is what lets the agent avoid inventing column names.
        ``inspect`` (group 4) is always ``None`` today: ``/inspect-table``
        doesn't exist yet.
    """
    stamped = read_stamped_metadata(table)
    mechanical = json.loads(json.dumps(scanner.result, default=str))
    return {
        "schema_version": stamped.get("schema_version"),
        "keys": stamped.get("keys"),
        "semantics": stamped.get("semantics"),
        "inspect": None,
        "file_columns": mechanical.get("file_columns"),
    }


def build_audit(table: str | Path) -> dict | None:
    """Return one table's full ``provenance`` block (group 5).

    Feeds the audit artifact, which never enters the agent's
    context (ADR-014): ``source_yaml``, ``source_sha256``, ``username``,
    ``notes``, ``git_commit``.

    Parameters
    ----------
    table : str or Path
        Parquet path. Only used to read back the stamped ``provenance``
        block via `read_stamped_metadata`.

    Returns
    -------
    dict or None
        The stamped ``provenance`` block, or None if the table has no
        ``meta`` footer yet.
    """
    return read_stamped_metadata(table).get("provenance")


def dict_to_flat(nested: dict, sep: str = ".") -> dict:
    """Flatten a nested dict into dot-path keys.

    Only ``dict`` values recurse; lists and scalars are treated as leaves.
    Used to build the flat index, where every table's schedule/mechanical/
    provenance share the same shape so a fixed set of leaf paths (e.g.
    ``semantics.description``) can be pulled out of each one uniformly.

    Parameters
    ----------
    nested : dict
        Dict to flatten, possibly with nested ``dict`` values.
    sep : str, default "."
        Separator joining parent and child keys in the flattened output.

    Returns
    -------
    dict
        Flat dict mapping dot-joined key paths to their leaf values.
    """
    flat: dict = {}
    for key, value in nested.items():
        if isinstance(value, dict):
            for sub_key, sub_value in dict_to_flat(value, sep=sep).items():
                flat[f"{key}{sep}{sub_key}"] = sub_value
        else:
            flat[key] = value
    return flat


def _extract_agent_rules(fields_spec: dict) -> dict:
    """Recursively pull ``agent_rule`` (+ ``value_descriptions``) out of
    a contract sub-tree, keyed by field name.

    Parameters
    ----------
    fields_spec : dict
        Mapping of field name -> spec, a `meta_contract.yaml` sub-tree.

    Returns
    -------
    dict
        One entry per field that declares ``agent_rule`` (directly, or
        via a nested ``fields:`` sub-tree, e.g. ``inspect.findings``).
        A field's value is its ``agent_rule`` string, or
        ``{"rule": ..., "value_descriptions": {...}}`` when the field also
        declares ``value_descriptions``. Fields with neither are omitted.
    """
    out: dict = {}
    for name, spec in fields_spec.items():
        if "agent_rule" in spec:
            rule = spec["agent_rule"].strip()
            if "value_descriptions" in spec:
                out[name] = {"rule": rule, "value_descriptions": spec["value_descriptions"]}
            else:
                out[name] = rule
        elif "fields" in spec:
            nested = _extract_agent_rules(spec["fields"])
            if nested:
                out[name] = nested
    return out


def build_reading_key(contract: dict | None = None) -> dict:
    """Build the agent's field-reading key: every ``agent_rule`` declared
    in ``meta.keys``, ``meta.semantics`` and ``inspect``, grouped the same
    way as a schedule (`build_schedule`).

    Not per-table - generated once from the contract itself, independent
    of any parquet or table data. A field with no ``agent_rule`` in
    the contract is the contract's own inclusion rule: it does not appear
    here, and is not owed to the agent.

    Parameters
    ----------
    contract : dict or None, default None
        Parsed contract. Loads `check.contract.load_contract` if not given.

    Returns
    -------
    dict
        ``{"keys": {...}, "semantics": {...}, "inspect": {...}}``. A group
        with no ``agent_rule`` anywhere in it is omitted entirely. Only
        these three groups are read: ``provenance`` and ``mechanical``
        carry no ``agent_rule`` by contract design, and one added there
        would be ignored (``tests/test_contract.py`` fails if one appears).
    """
    if contract is None:
        contract = load_contract()

    result: dict = {}
    for group in ("keys", "semantics"):
        extracted = _extract_agent_rules(contract["meta"][group]["fields"])
        if extracted:
            result[group] = extracted

    inspect_extracted = _extract_agent_rules(contract.get("inspect", {}))
    if inspect_extracted:
        result["inspect"] = inspect_extracted

    return result
