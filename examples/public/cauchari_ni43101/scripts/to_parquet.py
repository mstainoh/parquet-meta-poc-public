"""Convert the dataset's CSV tables to parquet with embedded metadata.

For every ``<dataset>/csv/modified/<stem>.csv`` that has a
``<dataset>/data_processed/parquet/<stem>.yaml``:

1. Read the CSV as text and type it column by column (see `type_column`).
2. Check that typing changed no value (see `check_values`).
3. Build the ``meta`` block: the YAML's ``meta`` (keys + semantics, as is) plus
   ``provenance`` from `meta_tools.write.get_yaml_provenance`.
4. Write ``<dataset>/data_processed/parquet/<stem>.parquet`` (next to its YAML)
   with `meta_tools.write.to_parquet`.

``_edits.csv`` is the edit log of the CSVs, not a table: it has no YAML and is
skipped. The ``inspect/`` findings are a sidecar (they are not embedded) and the
``mechanical`` group is computed later by ``run_metadata_etl.py``.

Source CSV/YAML files are never modified. Re-running overwrites the parquets.

Usage
-----
    python -I to_parquet.py <dataset_dir> [--only STEM]

Run with the repo's venv (needs meta_tools, pandas, pyarrow, yaml).
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

import pandas as pd
import yaml

from meta_tools.write import get_yaml_provenance, to_parquet

log = logging.getLogger("to_parquet")

REPO = "parquet-meta-contract/examples/public/cauchari_ni43101"
QUALITY = "silver"
NOTES = ("Tables extracted from a public NI 43-101 technical report (Cauchari-Olaroz, "
         "effective Jan 8 2025); see DATASET.md")

# Always text: identifiers, raw values and free text.
TEXT_COLUMNS = {
    "tabla", "tabla_apendice", "well_id", "pumping_well", "borehole_id", "dd_borehole_id",
    "piezometer_name", "pozo_a", "pozo_b", "nota", "interval_raw", "platform_raw",
    "plataform", "platform", "description", "fuente_xy", "fuentes_xy", "fuente_z",
}
TEXT_SUFFIXES = ("_id", "_raw")
INT_COLUMNS = {
    "pag_impresa", "pag_pdf", "year", "year_constructed", "start_year", "end_year",
    "interval_no", "brine_samples",
}
BOOL_COLUMNS = {"xy_swapped", "xy_conflicto"}
BOOL_VALUES = {"true": True, "false": False}

NUMBER_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
INT_RE = re.compile(r"^[+-]?\d+$")
LEADING_ZERO_RE = re.compile(r"^[+-]?0\d")


def type_column(name: str, values: pd.Series) -> tuple[pd.Series, str]:
    """Type one column read as text.

    Parameters
    ----------
    name : str
        Column name.
    values : pandas.Series
        Column values as strings (``""`` = empty).

    Returns
    -------
    tuple of (pandas.Series, str)
        The typed column (empty -> null in every type; text uses the
        pandas ``string`` dtype so an all-empty column is still a string column
        in arrow, not a ``null`` one) and the reason for
        its type: ``"forced_text"``, ``"int"``, ``"bool"``, ``"float"``,
        ``"text_non_numeric"``, ``"text_leading_zero"`` or ``"text_empty"``.

    Raises
    ------
    ValueError
        If a forced integer or boolean column holds a value that does not
        parse as such (nothing is coerced silently).
    """
    empty = values == ""
    filled = values[~empty]

    if name in TEXT_COLUMNS or name.endswith(TEXT_SUFFIXES):
        return values.where(~empty, None).astype("string"), "forced_text"

    if name in INT_COLUMNS:
        bad = filled[~filled.str.fullmatch(INT_RE)]
        if len(bad):
            raise ValueError(f"column {name!r}: non-integer values {sorted(set(bad))}")
        return pd.Series([None if v == "" else int(v) for v in values], dtype="Int64",
                         index=values.index), "int"

    if name in BOOL_COLUMNS:
        bad = filled[~filled.isin(list(BOOL_VALUES))]
        if len(bad):
            raise ValueError(f"column {name!r}: non-boolean values {sorted(set(bad))}")
        return pd.Series([BOOL_VALUES.get(v) for v in values], dtype="boolean",
                         index=values.index), "bool"

    if filled.empty:
        return values.where(~empty, None).astype("string"), "text_empty"
    if not filled.str.fullmatch(NUMBER_RE).all():
        return values.where(~empty, None).astype("string"), "text_non_numeric"
    if filled.str.match(LEADING_ZERO_RE).any():
        return values.where(~empty, None).astype("string"), "text_leading_zero"
    return pd.to_numeric(values.where(~empty, None), errors="raise").astype("float64"), "float"


def read_typed_csv(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    """Read a CSV as text and type every column with `type_column`.

    Parameters
    ----------
    path : Path
        CSV file.

    Returns
    -------
    tuple of (pandas.DataFrame, pandas.DataFrame, dict[str, str])
        The raw table (all text, ``""`` = empty), the typed table (default
        RangeIndex) and the type reason per column.
    """
    raw = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    typed, reasons = {}, {}
    for col in raw.columns:
        typed[col], reasons[col] = type_column(col, raw[col])
    return raw, pd.DataFrame(typed, columns=raw.columns), reasons


def check_values(raw: pd.DataFrame, typed: pd.DataFrame) -> None:
    """Check that typing changed no value of the table.

    Parameters
    ----------
    raw : pandas.DataFrame
        The CSV read as text (``""`` = empty).
    typed : pandas.DataFrame
        The typed table.

    Raises
    ------
    ValueError
        If the shape or column order differs, a null does not match an empty
        cell, or a value differs from its CSV text (text exactly, floats and
        integers numerically, booleans as ``true``/``false``).
    """
    if list(raw.columns) != list(typed.columns) or raw.shape != typed.shape:
        raise ValueError("shape or column order changed")
    for col in raw.columns:
        src, out = raw[col], typed[col]
        empty = src == ""
        if not (out.isna() == empty).all():
            raise ValueError(f"column {col!r}: nulls do not match empty cells")
        src, out = src[~empty], out[~empty]
        if pd.api.types.is_float_dtype(out):
            same = out.to_numpy() == src.astype(float).to_numpy()
        elif pd.api.types.is_bool_dtype(out):
            same = out.map({True: "true", False: "false"}).to_numpy() == src.to_numpy()
        elif pd.api.types.is_integer_dtype(out):
            same = out.astype("int64").to_numpy() == src.astype("int64").to_numpy()
        else:
            same = out.astype(str).to_numpy() == src.to_numpy()
        if not same.all():
            raise ValueError(f"column {col!r}: values changed when typing")


def build_meta(stem: str, meta_dir: Path, dataset_dir: Path) -> dict:
    """Build the ``meta`` block of one table: YAML ``meta`` + provenance.

    Parameters
    ----------
    stem : str
        Table name (file stem).
    meta_dir : Path
        Folder holding ``<stem>.yaml``.
    dataset_dir : Path
        Dataset root (``repo_root`` of the provenance).

    Returns
    -------
    dict
        ``{"keys", "semantics", "provenance"}`` (no ``schema_version``).
    """
    config = yaml.safe_load((meta_dir / f"{stem}.yaml").read_text(encoding="utf-8"))
    meta = dict(config["meta"])
    meta["provenance"] = get_yaml_provenance(
        source_file=stem, source_folder=meta_dir, repo_root=dataset_dir, repo=REPO,
        quality=QUALITY, username=None, notes=NOTES, add_git_commit=False,
    )
    return meta


def convert(dataset_dir: Path, only: str | None = None) -> dict[str, dict[str, str]]:
    """Write the parquets next to their YAMLs.

    Parameters
    ----------
    dataset_dir : Path
        Dataset root (holds ``csv/modified`` and ``data_processed/parquet``).
    only : str or None, default None
        Convert only this table (file stem); None converts all.

    Returns
    -------
    dict[str, dict[str, str]]
        Type reason per column, per table written.

    Raises
    ------
    FileNotFoundError
        If `only` has no CSV or no YAML.
    """
    csv_dir = dataset_dir / "csv" / "modified"
    out_dir = dataset_dir / "data_processed" / "parquet"
    paths = [csv_dir / f"{only}.csv"] if only else sorted(csv_dir.glob("*.csv"))
    reasons = {}
    for csv_path in paths:
        stem = csv_path.stem
        yaml_path = out_dir / f"{stem}.yaml"
        if not (csv_path.is_file() and yaml_path.is_file()):
            if only:
                raise FileNotFoundError(f"{stem}: needs {csv_path} and {yaml_path}")
            log.info("skipping %s: no %s", csv_path.name, yaml_path.name)
            continue
        raw, df, reasons[stem] = read_typed_csv(csv_path)
        check_values(raw, df)
        to_parquet(df, out_dir / f"{stem}.parquet",
                   metadata=build_meta(stem, out_dir, dataset_dir), preserve_index=False)
        log.info("%s: %d rows x %d columns", stem, len(df), df.shape[1])
    return reasons


def main() -> None:
    """Parse the arguments and run the conversion."""
    parser = argparse.ArgumentParser(description="Convert the dataset's CSV tables to parquet with embedded metadata.")
    parser.add_argument("dataset_dir", type=Path, help="dataset root")
    parser.add_argument("--only", default=None, help="convert only this table (file stem)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    reasons = convert(args.dataset_dir.resolve(), args.only)
    for stem, cols in reasons.items():
        by_content = [c for c, r in cols.items() if r.startswith("text_")]
        if by_content:
            log.info("%s: text by content: %s", stem,
                     ", ".join(f"{c} ({cols[c]})" for c in by_content))


if __name__ == "__main__":
    main()
