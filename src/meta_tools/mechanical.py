"""ParquetScanner: builds the group 1 (`mechanical`) metadata block for a
parquet file - descriptive stats plus verification of the declared `keys`
(group 2) against the actual data. See `docs/model/metadata_model.md` and
the `mechanical:` block of `meta_contract.yaml` for the field-by-field
spec this module fills in.
"""

from typing import Any, Union, cast
from pathlib import Path
import json
import logging
import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd

log = logging.getLogger(__name__)

__all__ = ["ParquetScanner"]


def _n_distinct(series: pd.Series) -> int:
    """Count distinct values, falling back to their string form if needed."""
    try:
        return int(series.nunique(dropna=True))
    except TypeError:
        return int(series.dropna().astype(str).nunique())

# Contract field names (fields.py). The methods below spell them as
# literal dict keys; only `check()` reads these constants, to catch the
# two drifting apart.
from .fields import (
    MECHANICAL_FIELDS,
    MECHANICAL_SCHEMA_VERSION,
    VERIFICATION_FIELDS,
    FK_FIELDS)


# =====================================================================
# ParquetScanner - group 1 (`mechanical`) of metadata_model.md
# =====================================================================

def _to_native(value: Any) -> Any:
    """Convert a numpy/pandas scalar to a native python value.

    Parameters
    ----------
    value : Any
        A scalar pulled from a pandas Series (numpy int/float, a
        ``pandas.Timestamp``, a plain python value, or NaN/NaT).

    Returns
    -------
    Any
        ``None`` for NaN/NaT, an ISO string for anything with an
        ``isoformat`` method, the plain python equivalent for numpy
        scalars (via ``.item()``), or `value` unchanged otherwise. Keeps
        `json.dumps(..., default=str)` (see `ParquetScanner.to_json`) from
        silently turning numbers into strings.
    """
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


class ParquetScanner:
    """Build the group 1 (``mechanical``) metadata block for a parquet file.

    See ``docs/model/metadata_model.md`` and the ``mechanical:`` block of
    ``meta_contract.yaml`` for the field-by-field spec this class fills in.

    One instance per table scanned - not a global singleton: each parquet
    needs its own path and its own cache of the data it reads, so it gets
    instantiated once per table, not once per process.

    Parameters
    ----------
    path : str or Path
        Path to the parquet file to scan.

    Attributes
    ----------
    result : dict
        Accumulates the fields written by `compute_mechanical`,
        `verify_keys` and `verify_foreign_keys`, in that order. It can
        intentionally contain only the table facts from
        `compute_mechanical`: those facts do not depend on metadata
        declared in the parquet and allow analysis of a clean parquet.
    checked : bool or None
        Outcome of the last `check()`; None until it runs.

    Raises
    ------
    FileNotFoundError
        If `path` does not point to an existing file.

    Examples
    --------
    Direct use::

        ParquetScanner(path).run()                      # no FK check
        ParquetScanner(path).run(pk_sources={"TBL_WELLS": wells_df})  # with FK check

    Step by step, to inspect the partial result in between::

        scanner = ParquetScanner(path)
        scanner.compute_mechanical()   # needs no metadata or verification
        scanner.verify_keys()          # uniques / not_nulls / index_columns
        scanner.verify_foreign_keys()  # fk_orphans / fk_verified
        scanner.result

    A scanner can therefore be used in two modes. For an agnostic table
    analysis, call `compute_mechanical()` and read `result`; the parquet
    need not contain the `b"meta"` key. To produce the complete mechanical
    artifact, call `run()` (or all verification methods) before `to_json()`.
    `to_json(check=True)` validates completeness with `check()` and refuses
    a partial result; the default `to_json()` writes whatever `result`
    holds.
    """

    SCHEMA_VERSION = MECHANICAL_SCHEMA_VERSION

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError(f"parquet file not found at {self.path}")
        self.result: dict = {}
        self.checked: Union[bool, None] = None
        self._table = None
        self._declared_keys: Union[dict, None] = None

    # ------------------------------------------------------------------
    # internals

    @property
    def _arrow_table(self):
        """Read the parquet file once and cache the full arrow table."""
        if self._table is None:
            self._table = pq.read_table(self.path)
        return self._table

    @property
    def df(self) -> pd.DataFrame:
        """DataFrame with ALL physical columns of the file, without
        restoring the pandas index - so `file_columns` and the stats
        match the arrow schema 1:1, index columns included (those are
        reported separately, see `get_parquet_index`)."""
        return self._arrow_table.to_pandas(ignore_metadata=True)

    def _declared(self) -> dict:
        """Return the ``keys`` block already stamped in the parquet.

        Returns
        -------
        dict
            The group 2 block (``uniques`` / ``not_nulls`` /
            ``foreign_keys`` / ``index_columns``) as written by
            `to_parquet`. ``{}`` if the table has no stamped metadata yet
            (``b'meta'`` absent) - not an error, the normal case during
            authoring - or if `meta` has no ``keys``.

        Notes
        -----
        Only the contract shape is read (nested under ``meta["keys"]``). A
        flat `meta` (``uniques``/``not_nulls``/... at its top level) declares
        nothing here; `check_table` reports its missing ``keys``.
        """
        if self._declared_keys is None:
            schema_meta = self._arrow_table.schema.metadata or {}
            raw = schema_meta.get(b"meta")
            meta = json.loads(raw) if raw else {}
            self._declared_keys = meta.get("keys") or {}
        return cast(dict, self._declared_keys)

    @staticmethod
    def get_parquet_index(parquet_schema) -> list:
        """Physical columns that pandas restores as a named index.

        Parameters
        ----------
        parquet_schema : pyarrow.Schema
            Schema of the parquet file, e.g. ``pyarrow.Table.schema`` or
            ``pyarrow.parquet.read_schema(path)``.

        Returns
        -------
        list of str
            Column names pandas will treat as index columns when reading
            the file back with `pandas.read_parquet`. Entries in the
            ``b'pandas'`` metadata that describe a default ``RangeIndex``
            (dicts, not backed by a physical column) are excluded - an
            empty list means the file uses the default RangeIndex.

        Notes
        -----
        This is purely a pandas/pyarrow round-trip convention, not a
        parquet-format feature: parquet itself has no notion of an
        index. Any reader that doesn't special-case pandas' ``b'pandas'``
        metadata key - DuckDB included - sees these columns as perfectly
        ordinary columns.
        """
        raw = parquet_schema.metadata.get(b"pandas") if parquet_schema.metadata else None
        pandas_meta = json.loads(raw) if raw else {}
        return [c for c in pandas_meta.get("index_columns", []) if isinstance(c, str)]

    # ------------------------------------------------------------------
    # 1. pure mechanical - needs no verification against anything declared
    # ------------------------------------------------------------------

    def compute_mechanical(self) -> "ParquetScanner":
        """Compute the fields that don't require a declared assertion.

        Fills in ``schema_version``, ``scanned_at``, ``row_count``,
        ``file_columns``, ``dtypes``, ``null_count``, ``n_distinct``,
        ``min_max``, ``file_size_bytes``, ``file_index_columns`` and
        ``file_uniques`` in `result`.

        Returns
        -------
        ParquetScanner
            `self`, for chaining.

        Notes
        -----
        This method only reads the parquet schema and data. It does not
        read or require the embedded metadata, so it also works for a
        parquet that has no ``b"meta"`` entry. The resulting `result` is
        deliberately partial until the verification methods are run.
        """
        df = self.df
        file_index_columns = self.get_parquet_index(self._arrow_table.schema)

        numeric_or_date = [
            c for c in df.columns
            if pd.api.types.is_numeric_dtype(df[c])
            or pd.api.types.is_datetime64_any_dtype(df[c])
        ]

        self.result.update({
            "schema_version": self.SCHEMA_VERSION,
            "scanned_at": pd.Timestamp.now(),
            "row_count": len(df),
            "file_columns": list(df.columns),
            "dtypes": {c: str(df[c].dtype) for c in df.columns},
            "null_count": {c: int(v) for c, v in df.isnull().sum().items()},
            "n_distinct": {c: _n_distinct(df[c]) for c in df.columns},
            "min_max": {
                c: {"min": _to_native(df[c].min()), "max": _to_native(df[c].max())}
                for c in numeric_or_date
            },
            "file_size_bytes": self.path.stat().st_size,
            "file_index_columns": file_index_columns,
            "file_uniques": [c for c in df.columns if not df[c].duplicated().any()],
        })
        log.info(
            "[%s] mechanical: OK (row_count=%s, columns=%s)",
            self.path.name, self.result["row_count"], len(self.result["file_columns"]),
        )
        return self

    # ------------------------------------------------------------------
    # 2. verify what's declared in `keys` (group 2) against the data
    # ------------------------------------------------------------------

    def verify_keys(self) -> "ParquetScanner":
        """Verify ``uniques`` / ``not_nulls`` / ``index_columns`` against
        the data.

        ``uniques`` / ``not_nulls`` with nothing declared (``null``,
        ``[]``, or absent) are vacuously satisfied (``True``) - there's no
        assertion to violate; a declared column missing from the table
        makes them ``False``. ``index_columns`` is always compared as a
        set against ``file_index_columns``: nothing declared means "no
        index", so an undeclared named index gives ``False``. Whether a
        ``null`` is real authoring debt is a separate concern, already
        handled by `check_metadata` / the ``required: expected`` states in
        the contract, not by this scanner.

        Returns
        -------
        ParquetScanner
            `self`, for chaining.
        """
        if "file_index_columns" not in self.result:
            self.compute_mechanical()

        df = self.df
        declared = self._declared()

        raw_uniques = declared.get("uniques")
        uniques = raw_uniques or []
        if uniques:
            missing = [c for c in uniques if c not in df.columns]
            uniques_verified = not missing and not df.duplicated(subset=uniques).any()
        else:
            uniques_verified = True  # nothing declared -> vacuously true
            if raw_uniques is None:
                log.info(
                    "[%s] `uniques` is null (not declared, or written as "
                    "null) - treating as no key declared; use [] to state "
                    "explicitly that the table has none.",
                    self.path.name,
                )

        not_nulls = declared.get("not_nulls") or []
        if not_nulls:
            missing_nn = [c for c in not_nulls if c not in df.columns]
            not_nulls_verified = not missing_nn and not df[not_nulls].isnull().to_numpy().any()
        else:
            not_nulls_verified = True  # nothing declared -> vacuously true

        index_columns = set(declared.get("index_columns") or [])
        index_columns_verified = index_columns == set(self.result["file_index_columns"])

        self.result.update({
            "uniques_verified": bool(uniques_verified),
            "not_nulls_verified": not_nulls_verified,
            "index_columns_verified": index_columns_verified,
        })
        verified = uniques_verified and not_nulls_verified and index_columns_verified
        level = logging.INFO if verified else logging.ERROR
        log.log(
            level,
            "[%s] keys verification: %s (uniques=%s, not_nulls=%s, index_columns=%s)",
            self.path.name, "OK" if verified else "FAILED",
            uniques_verified, not_nulls_verified, index_columns_verified,
        )
        return self

    # ------------------------------------------------------------------
    # 3. verify `foreign_keys` (group 2) - requires opening OTHER tables
    #    to read the referenced columns.
    # ------------------------------------------------------------------

    def verify_foreign_keys(
            self, pk_sources: Union[dict[str, pd.DataFrame], None] = None
            ) -> "ParquetScanner":
        """Run `fk_orphans` / `fk_verified` against the referenced tables.

        Parameters
        ----------
        pk_sources : dict[str, pandas.DataFrame] or None
            Referenced tables by name (file stem): the ``target_table`` of
            each FK declared in ``keys.foreign_keys``. Built by the caller
            (e.g. `etl.tables_by_name` over the tables of an ETL run). A
            declared FK whose ``target_table`` is not here is left
            unverified (it counts neither as orphaned nor as verified;
            ``fk_verified`` is None unless another FK fails).

        Returns
        -------
        ParquetScanner
            `self`, for chaining.

        Notes
        -----
        ``fk_orphans`` has one entry per FK verified - ``target_table``
        found and both columns present - with ``target_col`` resolved
        (``source_col`` when not declared) and its ``orphans`` (``[]`` if
        none). A ``source_col`` missing from the table, a ``target_col``
        missing from the referenced table, or a malformed declaration (no
        ``source_col`` / ``target_table``) fails the verification
        (``fk_verified`` False) with no entry, like a missing ``uniques``
        column in `verify_keys`: there is nothing to compare.
        """
        declared = self._declared()
        foreign_keys = declared.get("foreign_keys") or []
        pk_sources = pk_sources or {}
        df = self.df

        fk_orphans: list[dict] = []
        missing = []      # malformed, or a column absent from its table -> fails
        unverified = []   # target table not in pk_sources -> not verified
        for fk in foreign_keys:
            if not isinstance(fk, dict) or not fk.get("source_col") or not fk.get("target_table"):
                missing.append(f"malformed {fk!r}")
                continue
            source_col, target_table = fk["source_col"], fk["target_table"]
            target_col = fk.get("target_col") or source_col
            if source_col not in df.columns:
                missing.append(source_col)
                continue
            target = pk_sources.get(target_table)
            if target is None:
                unverified.append(f"{source_col} -> {target_table}")
                continue
            if target_col not in target.columns:
                missing.append(f"{target_table}.{target_col}")
                continue
            orphans = sorted(set(df[source_col].dropna()) - set(target[target_col].dropna()))
            fk_orphans.append({
                "source_col": source_col,
                "target_table": target_table,
                "target_col": target_col,
                "orphans": orphans,
            })

        with_orphans = [fk for fk in fk_orphans if fk["orphans"]]
        if missing or with_orphans:
            fk_verified = False      # malformed or absent column, or real orphans
        elif unverified:
            fk_verified = None       # some target tables not in pk_sources
        else:
            fk_verified = True       # nothing declared, or all checked clean

        self.result.update({
            "fk_orphans": fk_orphans,
            "fk_verified": fk_verified,
        })
        status = {True: "OK", False: "FAILED", None: "SKIPPED (target table not found)"}[fk_verified]
        level = logging.ERROR if fk_verified is False else logging.INFO
        log.log(level, "[%s] FK verification: %s", self.path.name, status)
        if missing:
            log.error(
                "[%s] FK declarations malformed or naming a missing column: %s",
                self.path.name, missing,
            )
        if unverified:
            log.warning(
                "[%s] FK not verified (target table not in pk_sources): %s",
                self.path.name, unverified,
            )
        for fk in with_orphans:
            log.debug(
                "[%s] FK %s -> %s.%s orphans: %s", self.path.name,
                fk["source_col"], fk["target_table"], fk["target_col"], fk["orphans"],
            )

        return self

    # ------------------------------------------------------------------

    def check(self, on_error_raise: bool = False) -> "ParquetScanner":
        """Check that `result` has exactly the fields declared in
        `fields.py`, recording the outcome in `checked`.

        A cheap self-consistency check, not a data validation: it only
        catches the group 1 code and the field names declared in
        `MECHANICAL_FIELDS` / `VERIFICATION_FIELDS` / `FK_FIELDS` drifting
        apart in silence (a field renamed on one side and not the other,
        a step that forgot to run).

        Parameters
        ----------
        on_error_raise : bool, default False
            Raise `AssertionError` on failure instead of only recording it
            in `checked` and logging it.

        Returns
        -------
        ParquetScanner
            `self`, for chaining.

        Raises
        ------
        AssertionError
            If `on_error_raise` and `result` is missing a declared field,
            or has one that isn't declared anywhere in `fields.py`.
        """
        expected = set(MECHANICAL_FIELDS) | set(VERIFICATION_FIELDS) | set(FK_FIELDS)
        actual = set(self.result)
        missing = expected - actual
        extra = actual - expected
        problems = []
        if missing:
            problems.append(f"missing fields: {sorted(missing)}")
        if extra:
            problems.append(f"fields not declared in fields.py: {sorted(extra)}")
        self.checked = not problems
        if problems:
            message = f"[{self.path.name}] check: " + "; ".join(problems)
            if on_error_raise:
                raise AssertionError(message)
            log.error(message)
        return self

    def run(
            self,
            pk_sources: Union[dict, None] = None,
            verify_keys: bool = True,
            verify_foreign_keys: bool = True,
            check: bool = True,
            on_error_raise: bool = False,
            ) -> dict:
        """Run the requested mechanical steps and return the result.

        Parameters
        ----------
        pk_sources : dict[str, pandas.DataFrame] or None
            Referenced tables by name, forwarded to `verify_foreign_keys`.
        verify_keys : bool, default True
            Run verification of declared unique, not-null and index keys.
        verify_foreign_keys : bool, default True
            Run verification of declared foreign keys.
        check : bool, default True
            Run `check()`: verify the result holds the complete mechanical
            field set (recorded in `checked`; raises only with
            `on_error_raise`).
        on_error_raise : bool, default False
            Forwarded to `check()`: raise instead of only recording the
            failure in `checked`.

        Returns
        -------
        dict
            `result`: the full ``mechanical`` block when both verifications
            run, ready for ``json.dumps(..., default=str)``.
        """
        self.compute_mechanical()
        if verify_keys:
            self.verify_keys()
        if verify_foreign_keys:
            self.verify_foreign_keys(pk_sources=pk_sources)
        if check:
            self.check(on_error_raise=on_error_raise)
        return self.result

    def to_json(self, path: Union[str, Path], check: bool=False) -> Path:
        """Write the current `result` to `path` as a JSON file.

        The output is flat, with one field per key at the top level. If
        `result` was produced by `run()`, it is the complete
        ``mechanical:`` block expected by `meta_contract.yaml`
        (`check_mechanical`), copied as-is to the stats artifact (ADR-014).
        If only `compute_mechanical()` was called, the JSON contains the
        available table facts and can be used as a partial, metadata-
        agnostic analysis.

        Validation is opt-in. `run()` already calls `check()`, so the
        default `check=False` avoids checking the same complete result a
        second time. Pass `check=True` when this method should reject a
        partial or otherwise inconsistent result before writing it.

        Parameters
        ----------
        path : str or Path
            Destination file.
        check : bool, default False
            Validate that `result` contains exactly the complete mechanical
            field set before writing. Leave false to write a partial result
            from `compute_mechanical()` or to avoid repeating the check
            already performed by `run()`.

        Returns
        -------
        Path
            `path`, for chaining.

        Raises
        ------
        AssertionError
            If `check=True` and `result` is incomplete or contains an
            undeclared field.
        """
        if check:
            self.check(on_error_raise=True)
        path = Path(path)
        path.write_text(
            json.dumps(self.result, default=str, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path
