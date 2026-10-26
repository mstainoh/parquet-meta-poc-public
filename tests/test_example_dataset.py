"""The example dataset (`examples/public/cauchari_ni43101`) against the contract.

Real, public data stamped with the package: every parquet must pass the
same checks the metadata ETL runs (`check_table`, `ParquetScanner` +
`check_mechanical`), its `inspect` sidecars must pass `check_inspect`, and one
table is rebuilt end to end from its YAML (authoring -> provenance ->
to_parquet -> check_table -> scanner -> check_mechanical). Skipped when the
example folder is not there (e.g. running from an installed wheel).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from meta_tools.check import check_authoring, check_inspect, check_mechanical
from meta_tools.etl import check_table, read_stamped_metadata, tables_by_name
from meta_tools.mechanical import ParquetScanner
from meta_tools.write.parquet import WRITER_VERSION, to_parquet
from meta_tools.write.provenance import get_yaml_provenance

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "public" / "cauchari_ni43101"
PARQUET = EXAMPLE / "data_processed" / "parquet"
INSPECT = EXAMPLE / "data_processed" / "inspect"
TABLES = sorted(p.stem for p in PARQUET.glob("*.parquet")) if PARQUET.is_dir() else []

pytestmark = pytest.mark.skipif(not TABLES, reason="example dataset not present")


@pytest.fixture(scope="module")
def frames() -> dict[str, pd.DataFrame]:
    """All example tables by name, as the ETL indexes FK targets."""
    return tables_by_name({"cauchari_ni43101": {PARQUET / f"{t}.parquet": pd.read_parquet(PARQUET / f"{t}.parquet")
                                                for t in TABLES}})


def _yaml_meta(table: str) -> dict:
    return yaml.safe_load((PARQUET / f"{table}.yaml").read_text(encoding="utf-8"))["meta"]


@pytest.mark.parametrize("table", TABLES)
def test_example_footer_passes_contract(table):
    path = PARQUET / f"{table}.parquet"
    assert all(check_table(path, keys=True, semantics=True, provenance=True).values())
    stamped = read_stamped_metadata(path)
    meta = _yaml_meta(table)
    assert {k: stamped[k] for k in ("keys", "semantics")} == meta
    # The hash stamped at write time is the hash of the YAML as committed (LF, .gitattributes)
    yaml_bytes = (PARQUET / f"{table}.yaml").read_bytes()
    assert stamped["provenance"]["source_sha256"] == hashlib.sha256(yaml_bytes).hexdigest()


@pytest.mark.parametrize("table", TABLES)
def test_example_keys_and_foreign_keys_verify(table, frames):
    scanner = ParquetScanner(PARQUET / f"{table}.parquet")
    scanner.run(pk_sources=frames)
    result = json.loads(json.dumps(scanner.result, default=str))
    assert check_mechanical(result) is True
    assert result["row_count"] == len(frames[table])
    assert result["uniques_verified"] is True
    assert result["not_nulls_verified"] is True
    if _yaml_meta(table)["keys"]["foreign_keys"]:
        assert result["fk_verified"] is True
    assert all(fk["orphans"] == [] for fk in result["fk_orphans"])


@pytest.mark.parametrize("sidecar", sorted(INSPECT.glob("*.yaml")) if INSPECT.is_dir() else [],
                         ids=lambda p: p.stem)
def test_example_inspect_sidecars_are_valid_and_current(sidecar, frames):
    doc = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
    assert check_inspect(doc) is True
    df = frames[sidecar.stem]
    assert doc["observed_row_count"] == len(df)
    assert all(set(f["columns"]) <= set(df.columns) for f in doc["findings"])


def test_example_end_to_end_restamp(tmp_path, frames):
    """YAML -> check_authoring -> get_yaml_provenance -> to_parquet -> check_table
    -> ParquetScanner -> check_mechanical, on a real table with FKs."""
    table = "t10_7_piezometer_brine_chemistry"
    meta = _yaml_meta(table)
    assert check_authoring(meta) is True
    provenance = get_yaml_provenance(table, PARQUET, EXAMPLE, repo="test", add_git_commit=False)
    out = tmp_path / f"{table}.parquet"
    to_parquet(frames[table], out, metadata={**meta, "provenance": provenance})

    stamped = read_stamped_metadata(out)
    assert {k: stamped[k] for k in ("keys", "semantics")} == meta
    assert stamped["provenance"]["writer_version"] == WRITER_VERSION
    assert all(check_table(out, keys=True, semantics=True, provenance=True).values())
    assert pd.read_parquet(out).equals(frames[table])

    scanner = ParquetScanner(out)
    scanner.run(pk_sources=frames)
    result = json.loads(json.dumps(scanner.result, default=str))
    assert check_mechanical(result) is True
    assert result["fk_verified"] is True
    assert [fk["target_table"] for fk in result["fk_orphans"]] == [fk["target_table"] for fk in meta["keys"]["foreign_keys"]]
