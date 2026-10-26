"""Tests for the contract and the checker (keys + semantics, authoring stage).

The first one is the one that matters: every `example` in the contract must
validate against its own field's `type` - keeps the spec and the validator
from drifting apart silently.

    python -m pytest tests/test_contract.py -v
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import warnings

import pytest
import pandas as pd
import pyarrow.parquet as pq

from meta_tools.build import build_reading_key
from meta_tools.etl import load_input_sources, prune_outputs, read_stamped_metadata, tables_by_name
from meta_tools.check import (
    CONTRACT_PATH, ContractError, check_authoring, check_inspect,
    check_mechanical, check_metadata, check_provenance, load_contract,
)
from meta_tools.check.schema import _type_ok
from meta_tools.fields import (
    AUTHORING_FIELDS, FK_FIELDS, MECHANICAL_FIELDS, PROVENANCE_FIELDS, VERIFICATION_FIELDS,
)
from meta_tools.mechanical import ParquetScanner
from meta_tools.write.parquet import to_parquet
from meta_tools.write.provenance import get_yaml_provenance


def _load_contract() -> dict:
    return load_contract(CONTRACT_PATH)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _iter_specs(specs: dict, prefix: str = ""):
    for name, spec in specs.items():
        where = f"{prefix}.{name}" if prefix else name
        yield where, spec
        if isinstance(spec, dict) and "fields" in spec:
            yield from _iter_specs(spec["fields"], where)


def _build_example(specs: dict) -> dict:
    out = {}
    for name, spec in specs.items():
        if spec.get("type") == "object":
            out[name] = _build_example(spec["fields"])
        elif spec.get("type") == "list[object]":
            out[name] = [_build_example(spec["fields"])]
        elif "example" in spec:
            out[name] = spec["example"]
    return out


def _meta_authoring() -> dict:
    """What a person writes: only keys + semantics."""
    contract = _load_contract()
    return _build_example({k: contract["meta"][k] for k in ("keys", "semantics")})


def _meta_provenance() -> dict:
    """What the writer stamps: schema_version + provenance."""
    contract = _load_contract()
    return _build_example({k: contract["meta"][k] for k in ("schema_version", "provenance")})


def _mechanical() -> dict:
    """What the scanner writes: the whole mechanical group."""
    return _build_example(_load_contract()["mechanical"])


def _inspect() -> dict:
    """What the agent writes: the whole inspect sidecar (one finding)."""
    return _build_example(_load_contract()["inspect"])


_WITH_EXAMPLE = [
    (w, s)
    for group in ("meta", "inspect", "mechanical")
    for w, s in _iter_specs(_load_contract()[group], group)
    if "example" in s
]

# One valid sample per token of the contract's closed vocabulary (`types:`).
_TYPE_SAMPLES = {
    "str": "W-999",
    "int": 25,
    "bool": True,
    "date": dt.date(2026, 9, 3),
    "datetime": dt.datetime(2026, 9, 3, 14, 22, 10),
    "list[str]": ["well_id"],
    "list": ["W-999", 17],
    "dict[str,str]": {"well_id": "FK to TBL_WELLS"},
    "dict[str,int]": {"well_id": 0},
    "dict[str,list]": {"well_id": ["W-999"]},
    "dict[str,dict]": {"level_m": {"min": 2.1, "max": 182.0}},
    "list[object]": [{"columns": ["level_m"]}],
    "enum": "full_history",
    "object": {"uniques": ["well_id"]},
}


# ---------------------------------------------------------------------------
# 1. self-consistency: every example validates against its own type
# ---------------------------------------------------------------------------

def test_there_are_examples_to_check():
    assert len(_WITH_EXAMPLE) > 10, "the contract lost its `example`s"
    covered = {w for w, _ in _WITH_EXAMPLE}
    assert {w.split(".")[0] for w in covered} == {"meta", "inspect", "mechanical"}
    assert {"meta.schema_version", "inspect.findings.severity"} <= covered


@pytest.mark.parametrize("where,spec", _WITH_EXAMPLE, ids=[w for w, _ in _WITH_EXAMPLE])
def test_example_validates_against_its_type(where, spec):
    assert _type_ok(spec, spec["example"])


@pytest.mark.parametrize("token", _load_contract()["types"])
def test_every_contract_type_is_accepted_by_type_ok(token):
    """Every token of the closed vocabulary (`types:`) has a branch in
    `_type_ok`: a token declared in the contract but unknown to the
    validator would raise ContractError on the first field that uses it."""
    assert token in _TYPE_SAMPLES, f"no sample for `{token}` in _TYPE_SAMPLES"
    assert _type_ok({"type": token, "values": ["full_history"]}, _TYPE_SAMPLES[token])


def test_unknown_type_raises():
    with pytest.raises(ContractError):
        _type_ok({"type": "unicorn"}, "x")


def test_every_object_field_declares_fields():
    """`object` / `list[object]` are validated against their `fields:`:
    without them the checker raises ContractError on the first value."""
    contract = _load_contract()
    missing = [
        where
        for group in ("meta", "inspect", "mechanical")
        for where, spec in _iter_specs(contract[group], group)
        if spec.get("type") in ("object", "list[object]")
        and not isinstance(spec.get("fields"), dict)
    ]
    assert not missing, f"`object` / `list[object]` without `fields:`: {missing}"


@pytest.mark.parametrize("token,value", [("object", {}), ("list[object]", [{}])])
def test_object_without_fields_raises_contract_error(token, value):
    """A broken contract is a ContractError (like an unknown type token),
    not a raw KeyError from the checker."""
    top_spec = {"block": {"type": token, "required": True}}
    with pytest.raises(ContractError, match="meta.block: type `.*` declared without `fields:`"):
        check_metadata({"block": value}, top_spec, path="meta")


@pytest.mark.parametrize("spec,match", [
    ({"required": True}, "meta.block: contract field declared without `type:`"),
    ({"type": "str"}, "meta.block: contract field declared without `required:`"),
    ({"type": "enum", "required": True}, "meta.block: type `enum` declared without `values:`"),
])
def test_incomplete_field_spec_raises_key_error_with_path(spec, match):
    """A field spec missing `type` / `required` (or an `enum` missing
    `values:`) is a broken contract: KeyError naming the field, raised even
    when the value is absent."""
    with pytest.raises(KeyError, match=match):
        check_metadata({}, {"block": spec}, path="meta")


def test_mechanical_example_fk_fields_are_coherent():
    """`fk_orphans` has one entry per verified FK, with or without orphans,
    and any orphan makes `fk_verified: false`: the example must be a state
    the scanner can produce."""
    d = _mechanical()
    assert all(isinstance(fk["orphans"], list) for fk in d["fk_orphans"])
    assert not any(fk["orphans"] for fk in d["fk_orphans"]) or d["fk_verified"] is False


def _reading_key_paths(node: dict, prefix: str = "") -> set:
    """Dotted paths of the leaves (one per `agent_rule`) of a reading key."""
    paths = set()
    for name, value in node.items():
        where = f"{prefix}.{name}" if prefix else name
        if isinstance(value, str) or "rule" in value:
            paths.add(where)
        else:
            paths |= _reading_key_paths(value, where)
    return paths


def test_reading_key_drops_no_agent_rule():
    """`build_reading_key` reads only keys/semantics/inspect: an `agent_rule`
    added anywhere else (provenance, mechanical) would be dropped in
    silence. Every `agent_rule` in the contract must reach the key."""
    contract = _load_contract()
    specs = (
        list(_iter_specs(contract["meta"]))
        + list(_iter_specs(contract["inspect"], "inspect"))
        + list(_iter_specs(contract["mechanical"], "mechanical"))
    )
    declared = {where for where, spec in specs if "agent_rule" in spec}
    assert declared == _reading_key_paths(build_reading_key(contract))


def test_fields_py_mechanical_fields_match_contract():
    """`fields.py` (used by `ParquetScanner.check`, a cheap field-presence
    assert) and `meta_contract.yaml["mechanical"]` (used by
    `check_mechanical`, which validates types) are two hand-kept lists of
    the same fields. If one changes without the other, each checker
    still passes on its own - this test is the one that catches the
    drift."""
    fields_py = set(MECHANICAL_FIELDS) | set(VERIFICATION_FIELDS) | set(FK_FIELDS)
    contract = set(_load_contract()["mechanical"])
    assert fields_py == contract


def test_fields_py_meta_slices_partition_contract_meta():
    """`check_authoring` validates `AUTHORING_FIELDS` and `check_provenance`
    `PROVENANCE_FIELDS`, two slices of `meta`: a `meta` field in neither
    slice is validated by no checker, one in both is an error in one of
    them."""
    authoring, stamped = set(AUTHORING_FIELDS), set(PROVENANCE_FIELDS)
    assert not authoring & stamped
    assert authoring | stamped == set(_load_contract()["meta"])


# ---------------------------------------------------------------------------
# 2. check_authoring behaviour
# ---------------------------------------------------------------------------

def test_full_example_passes():
    assert check_authoring(_meta_authoring()) is True


def test_invalid_enum_is_error(caplog):
    d = _meta_authoring()
    d["semantics"]["temporal_scope"] = "yesterday"
    with caplog.at_level(logging.ERROR):
        assert check_authoring(d) is False
    assert "temporal_scope" in caplog.text


def test_wrong_type_is_error():
    d = _meta_authoring()
    d["keys"]["uniques"] = "well_id"           # str where list[str] goes
    assert check_authoring(d) is False


def test_unknown_field_is_error(caplog):
    """The real case: singular `cross_table` instead of `cross_tables`."""
    d = _meta_authoring()
    d["semantics"]["cross_table"] = d["semantics"].pop("cross_tables")
    with caplog.at_level(logging.ERROR):
        assert check_authoring(d) is False
    assert "cross_table" in caplog.text


def test_old_fk_columns_field_is_error():
    """`keys.foreign_key_columns` (a list of names) gave way to
    `keys.foreign_keys` (ADR-017): stamped with the old field, the table must
    be re-stamped."""
    d = _meta_authoring()
    d["keys"]["foreign_key_columns"] = [fk["source_col"] for fk in d["keys"].pop("foreign_keys")]
    assert check_authoring(d) is False


def test_foreign_key_item_is_validated(caplog):
    """Each `keys.foreign_keys` item is checked against its fields: without
    `target_table` it is an error, with an indexed path; `target_col` may be
    left out."""
    d = _meta_authoring()
    d["keys"]["foreign_keys"] = [{"source_col": "well_id", "target_table": "TBL_WELLS"}]
    assert check_authoring(d) is True
    d["keys"]["foreign_keys"] = [{"source_col": "well_id"}]
    with caplog.at_level(logging.ERROR):
        assert check_authoring(d) is False
    assert "meta.keys.foreign_keys[0].target_table: missing (required)" in caplog.text


def test_hand_written_provenance_is_error():
    """provenance is stamped by the writer - if it shows up in the authoring yaml, error."""
    d = _meta_authoring()
    d["provenance"] = {"repo": "warehouse"}
    assert check_authoring(d) is False


def test_hand_written_schema_version_is_error():
    d = _meta_authoring()
    d["schema_version"] = 1
    assert check_authoring(d) is False


def test_missing_schema_version_is_valid_in_provenance():
    d = _roundtrip_json(_meta_provenance())
    del d["schema_version"]
    assert check_provenance(d) is True


def test_to_parquet_stamps_writer_version_without_mutating_metadata(tmp_path):
    metadata = {"provenance": {"repo": "consumer"}}
    to_parquet(pd.DataFrame({"value": [1]}), tmp_path / "table.parquet", metadata)

    stored = json.loads(
        pq.read_schema(tmp_path / "table.parquet").metadata[b"meta"]
    )
    assert stored["provenance"]["writer_version"] == 1
    assert "writer_version" not in metadata["provenance"]


def test_writer_version_exported_from_write():
    """Producers read the stamped `writer_version` from `meta_tools.write`, not from
    the internal `write.parquet` module."""
    import meta_tools.write as write
    from meta_tools.write import parquet
    assert "WRITER_VERSION" in write.__all__
    assert write.WRITER_VERSION == parquet.WRITER_VERSION


def test_to_parquet_keeps_named_multiindex(tmp_path):
    df = pd.DataFrame(
        {"level_m": [12.5, 13.1]},
        index=pd.MultiIndex.from_tuples(
            [("W-998", "2026-09-03"), ("W-999", "2026-09-03")],
            names=["well_id", "date"],
        ),
    )
    to_parquet(df, tmp_path / "table.parquet")

    back = pd.read_parquet(tmp_path / "table.parquet")
    assert list(back.index.names) == ["well_id", "date"]


def test_to_parquet_drops_unnamed_index(tmp_path):
    to_parquet(pd.DataFrame({"level_m": [12.5]}), tmp_path / "table.parquet")

    assert pq.read_schema(tmp_path / "table.parquet").names == ["level_m"]


def test_to_parquet_attrs_round_trip_without_own_key(tmp_path):
    """`df.attrs` travels in the pandas metadata (pyarrow); no b'attrs' key."""
    df = pd.DataFrame({"level_m": [12.5]})
    df.attrs = {"units": "m"}
    to_parquet(df, tmp_path / "table.parquet")

    assert b"attrs" not in pq.read_schema(tmp_path / "table.parquet").metadata
    assert pd.read_parquet(tmp_path / "table.parquet").attrs == {"units": "m"}


def test_scanner_ignores_flat_meta(tmp_path):
    """Only `meta.keys` declares keys: a flat `meta` (legacy shape) declares
    nothing, as `check_table` sees it (keys missing)."""
    df = pd.DataFrame({"well_id": ["W-999", "W-999"]})       # a PK would fail
    to_parquet(df, tmp_path / "flat.parquet", metadata={"uniques": ["well_id"]})

    assert ParquetScanner(tmp_path / "flat.parquet")._declared() == {}


def test_get_yaml_provenance_preserves_yaml_and_hashes_bytes(tmp_path):
    source_bytes = b"# comment\r\nvalue: 1\r\n"
    (tmp_path / "config.yaml").write_bytes(source_bytes)

    provenance = get_yaml_provenance(
        "config",
        tmp_path,
        tmp_path,
        "test-repo",
    )

    assert provenance["source_yaml"] == source_bytes.decode("utf-8")
    assert provenance["source_sha256"] == hashlib.sha256(source_bytes).hexdigest()


def test_get_yaml_provenance_without_git_commit(tmp_path):
    """add_git_commit=False stamps git_commit as None without calling git
    (tmp_path is no repo: the lookup would warn). It is the last parameter,
    so a positional `notes` keeps its meaning."""
    (tmp_path / "config.yaml").write_text("value: 1\n", encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        provenance = get_yaml_provenance(
            "config", tmp_path, tmp_path, "test-repo", None, "utf-8", None, "sibling of X",
            add_git_commit=False,
        )
    assert provenance["git_commit"] is None
    assert provenance["notes"] == "sibling of X"


def test_missing_required_true_is_error():
    d = _meta_authoring()
    del d["semantics"]["grain"]
    assert check_authoring(d) is False


def test_on_error_raise_propagates():
    d = _meta_authoring()
    d["semantics"]["temporal_scope"] = "yesterday"
    with pytest.raises(ValueError):
        check_authoring(d, on_error_raise=True)


def test_non_dict_is_error():
    assert check_authoring(["not a dict"]) is False  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        check_authoring("neither", on_error_raise=True)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 3. missing fields: info, not error
# ---------------------------------------------------------------------------

def test_missing_expected_logs_info_and_returns_true(caplog):
    d = _meta_authoring()
    del d["keys"]["uniques"]
    with caplog.at_level(logging.INFO):
        assert check_authoring(d) is True
    assert "keys.uniques" in caplog.text
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_expected_null_is_also_missing(caplog):
    d = _meta_authoring()
    d["keys"]["uniques"] = None
    with caplog.at_level(logging.INFO):
        assert check_authoring(d) is True
    assert "keys.uniques" in caplog.text


def test_empty_list_is_not_missing(caplog):
    """`[]` is a declaration ('none'), `null` is the absence of one."""
    d = _meta_authoring()
    d["keys"]["uniques"] = []
    with caplog.at_level(logging.INFO):
        assert check_authoring(d) is True
    assert "keys.uniques" not in caplog.text


def test_label_appears_in_log(caplog):
    d = _meta_authoring()
    del d["keys"]["uniques"]
    with caplog.at_level(logging.INFO):
        check_authoring(d, label="TBL_WATER_LEVELS")
    assert "TBL_WATER_LEVELS" in caplog.text


# ---------------------------------------------------------------------------
# 4. check_provenance / check_mechanical - same engine, another top_spec
# ---------------------------------------------------------------------------
# provenance and mechanical are stamped as JSON (`json.dumps(...,
# default=str)`), not as YAML - that is why these tests round-trip the
# examples through json.loads/dumps instead of using them as they come
# out of the contract: it is the real shape in which the data reaches the
# checker (dates included, which arrive as ISO strings, not `datetime`).

def _roundtrip_json(d: dict) -> dict:
    return json.loads(json.dumps(d, default=str))


def test_provenance_full_example_passes():
    assert check_provenance(_roundtrip_json(_meta_provenance())) is True


def test_provenance_repo_accepts_free_identifier():
    d = _roundtrip_json(_meta_provenance())
    d["provenance"]["repo"] = "other_repo"
    assert check_provenance(d) is True


def test_provenance_null_git_commit_and_username_pass():
    """Both are `required: false`: the writer can't always produce them
    (git unresolvable, caller without a username) - ADR-015."""
    d = _roundtrip_json(_meta_provenance())
    d["provenance"]["git_commit"] = None
    d["provenance"]["username"] = None
    assert check_provenance(d) is True


@pytest.mark.filterwarnings("ignore:get_yaml_provenance:RuntimeWarning")
def test_stamped_get_yaml_provenance_without_username_passes(tmp_path):
    """What the writer produces with `username=None` (and `git_commit` None
    if tmp_path isn't a git repo) passes once stamped by `to_parquet`."""
    (tmp_path / "config.yaml").write_text("value: 1\n", encoding="utf-8")
    provenance = get_yaml_provenance("config", tmp_path, tmp_path, "test-repo", username=None)
    to_parquet(pd.DataFrame({"value": [1]}), tmp_path / "table.parquet",
               {"provenance": provenance})

    stamped = read_stamped_metadata(tmp_path / "table.parquet")
    assert stamped["provenance"]["username"] is None
    assert check_provenance(stamped) is True


def test_provenance_extra_hand_written_field_is_error():
    d = _roundtrip_json(_meta_provenance())
    d["keys"] = {}
    assert check_provenance(d) is False


def test_mechanical_full_example_passes():
    assert check_mechanical(_roundtrip_json(_mechanical())) is True


def test_mechanical_fk_verified_null_is_not_error():
    """fk_verified is `required: false` on purpose: None is an fk column
    without pk_sources, not a missing field."""
    d = _roundtrip_json(_mechanical())
    d["fk_verified"] = None
    assert check_mechanical(d) is True


def test_mechanical_wrong_type_is_error():
    d = _roundtrip_json(_mechanical())
    d["null_count"] = ["well_id"]           # list where dict[str,int] goes
    assert check_mechanical(d) is False


def test_type_ok_datetime_accepts_iso_string():
    """The real data arrives through JSON: `datetime` must validate both
    the native object (authoring via YAML) and the ISO string (mechanical/
    provenance via JSON)."""
    spec = {"type": "datetime"}
    assert _type_ok(spec, dt.datetime(2026, 9, 3, 14, 22, 10))
    assert _type_ok(spec, "2026-09-03T14:22:10")
    assert not _type_ok(spec, "not a date")


def test_type_ok_datetime_accepts_date():
    """A `date` is a `datetime` at midnight: the object validates like the
    date-only ISO string already did (nothing is lost in that direction)."""
    spec = {"type": "datetime"}
    assert _type_ok(spec, "2026-09-03")
    assert _type_ok(spec, dt.date(2026, 9, 3))


def test_type_ok_date_rejects_datetime():
    """`datetime` subclasses `date` in python: a `date` field takes a date,
    as an object or an ISO string, never a timestamp in either form."""
    spec = {"type": "date"}
    assert _type_ok(spec, dt.date(2026, 9, 3))
    assert _type_ok(spec, "2026-09-03")
    assert not _type_ok(spec, dt.datetime(2026, 9, 3, 14, 22, 10))
    assert not _type_ok(spec, "2026-09-03T14:22:10")


def test_bool_is_not_int():
    """`bool` subclasses `int` in python: `row_count: true` must not validate."""
    d = _roundtrip_json(_mechanical())
    d["row_count"] = True
    assert check_mechanical(d) is False


def test_bool_is_not_int_inside_dict():
    d = _roundtrip_json(_mechanical())
    d["null_count"]["well_id"] = True
    assert check_mechanical(d) is False


# ---------------------------------------------------------------------------
# 5. check_inspect - list[object] items are validated against their `fields`
# ---------------------------------------------------------------------------

def test_inspect_full_example_passes():
    assert check_inspect(_inspect()) is True


def test_inspect_observed_at_timestamp_is_error():
    """PyYAML reads `observed_at: 2026-09-03T14:22:10` as a `datetime`, but
    `observed_at` is a `date`."""
    d = _inspect()
    d["observed_at"] = dt.datetime(2026, 9, 3, 14, 22, 10)
    assert check_inspect(d) is False


def test_inspect_finding_invalid_enum_is_error(caplog):
    d = _inspect()
    d["findings"].append({**d["findings"][0], "severity": "BAD"})
    with caplog.at_level(logging.ERROR):
        assert check_inspect(d) is False
    assert "inspect.findings[1].severity: value `BAD`" in caplog.text


def test_inspect_finding_missing_required_is_error(caplog):
    d = _inspect()
    del d["findings"][0]["note"]
    with caplog.at_level(logging.ERROR):
        assert check_inspect(d) is False
    assert "inspect.findings[0].note: missing (required)" in caplog.text


def test_inspect_finding_unknown_field_is_error(caplog):
    d = _inspect()
    d["findings"][0]["column"] = d["findings"][0].pop("columns")
    with caplog.at_level(logging.ERROR):
        assert check_inspect(d) is False
    assert "inspect.findings[0].column: field not declared" in caplog.text


# ---------------------------------------------------------------------------
# 6. ParquetScanner - real output against the contract, and its logs
# ---------------------------------------------------------------------------

_FK_WELLS = {"source_col": "well_id", "target_table": "TBL_WELLS"}
_FK_PUMPS = {"source_col": "pump_id", "target_table": "TBL_PUMPS"}


def _water_levels(tmp_path, uniques: list, foreign_keys: tuple = (_FK_WELLS,)) -> str:
    """Synthetic water-level readings (W-999 read twice), `keys` stamped."""
    df = pd.DataFrame({
        "well_id": ["W-997", "W-998", "W-999", "W-999"],
        "datetime": pd.to_datetime([
            "2018-01-01 00:00", "2018-01-01 06:00", "2026-08-30 00:00", "2026-08-30 12:00",
        ]),
        "level_m": [2.1, None, 182.0, 150.3],
    })
    path = tmp_path / "TBL_WATER_LEVELS.parquet"
    to_parquet(df, path, {"keys": {"uniques": uniques, "foreign_keys": list(foreign_keys)}})
    return path


def test_scanner_output_passes_check_mechanical(tmp_path):
    wells = pd.DataFrame({"well_id": ["W-997", "W-998", "W-999"]})
    scanner = ParquetScanner(_water_levels(tmp_path, ["well_id", "datetime"]))
    scanner.run(pk_sources={"TBL_WELLS": wells})
    result = _roundtrip_json(scanner.result)
    assert check_mechanical(result) is True
    assert result["fk_orphans"] == [
        {"source_col": "well_id", "target_table": "TBL_WELLS", "target_col": "well_id", "orphans": []},
    ]
    assert result["fk_verified"] is True


def test_verify_keys_logs_failure(tmp_path, caplog):
    """A declared unique key with duplicates is logged as an error, not 'OK'."""
    scanner = ParquetScanner(_water_levels(tmp_path, ["well_id"]))
    with caplog.at_level(logging.INFO, logger="meta_tools.mechanical"):
        scanner.compute_mechanical().verify_keys()
    assert scanner.result["uniques_verified"] is False
    [record] = [r for r in caplog.records if "keys verification" in r.getMessage()]
    assert record.levelno == logging.ERROR
    assert "FAILED" in record.getMessage()


def test_verify_foreign_keys_missing_column_fails(tmp_path, caplog):
    """A declared FK column absent from the table fails the verification
    (logged as FAILED), even with its target table, and gets no entry in
    `fk_orphans` (it has no values)."""
    path = _water_levels(tmp_path, ["well_id", "datetime"], foreign_keys=(_FK_PUMPS,))
    pumps = pd.DataFrame({"pump_id": ["P-999"]})
    scanner = ParquetScanner(path)
    with caplog.at_level(logging.INFO, logger="meta_tools.mechanical"):
        scanner.run(pk_sources={"TBL_PUMPS": pumps})
    assert scanner.result["fk_verified"] is False
    assert scanner.result["fk_orphans"] == []
    assert check_mechanical(_roundtrip_json(scanner.result)) is True
    [record] = [r for r in caplog.records if "FK verification" in r.getMessage()]
    assert record.levelno == logging.ERROR
    assert "FAILED" in record.getMessage()


@pytest.mark.parametrize("foreign_keys, expected", [
    ((_FK_WELLS,), None),              # in the table, target not in pk_sources: not verified
    ((_FK_WELLS, _FK_PUMPS), False),   # a missing column fails, even next to an unverified one
    (("well_id",), False),             # malformed (old list-of-names shape): fails, no crash
])
def test_verify_foreign_keys_without_pk_sources(tmp_path, foreign_keys, expected):
    scanner = ParquetScanner(_water_levels(tmp_path, ["well_id", "datetime"], foreign_keys))
    scanner.verify_foreign_keys()
    assert scanner.result["fk_verified"] is expected
    assert scanner.result["fk_orphans"] == []


def test_verify_foreign_keys_reports_orphans_per_relation(tmp_path):
    """Each verified FK is one entry, orphans with their type; any orphan
    makes `fk_verified` false."""
    wells = pd.DataFrame({"well_id": ["W-997", "W-998"]})          # W-999 missing
    scanner = ParquetScanner(_water_levels(tmp_path, ["well_id", "datetime"]))
    scanner.run(pk_sources={"TBL_WELLS": wells})
    assert scanner.result["fk_orphans"] == [
        {"source_col": "well_id", "target_table": "TBL_WELLS", "target_col": "well_id",
         "orphans": ["W-999"]},
    ]
    assert scanner.result["fk_verified"] is False
    assert check_mechanical(_roundtrip_json(scanner.result)) is True


def test_verify_foreign_keys_target_col_with_another_name(tmp_path):
    """`target_col` names the referenced column when it is not called like
    `source_col`; a `target_col` missing from the target fails."""
    fk = {"source_col": "well_id", "target_table": "TBL_WELLS", "target_col": "id"}
    path = _water_levels(tmp_path, ["well_id", "datetime"], foreign_keys=(fk,))
    wells = pd.DataFrame({"id": ["W-997", "W-998", "W-999"]})
    scanner = ParquetScanner(path)
    scanner.run(pk_sources={"TBL_WELLS": wells})
    assert scanner.result["fk_verified"] is True
    assert scanner.result["fk_orphans"][0]["target_col"] == "id"

    scanner = ParquetScanner(path)
    scanner.run(pk_sources={"TBL_WELLS": wells.rename(columns={"id": "well_code"})})
    assert scanner.result["fk_verified"] is False
    assert scanner.result["fk_orphans"] == []


def test_scanner_check_message_names_fields_py(tmp_path):
    scanner = ParquetScanner(_water_levels(tmp_path, ["well_id", "datetime"]))
    scanner.compute_mechanical()             # partial: verification fields missing
    scanner.result["extra"] = 1
    with pytest.raises(AssertionError) as exc:
        scanner.check(on_error_raise=True)
    message = str(exc.value)
    assert "missing fields" in message
    assert "not declared in fields.py" in message


# ---------------------------------------------------------------------------
# 7. load_input_sources - `input:` entries -> tables found per source
# ---------------------------------------------------------------------------
# The path resolver is injected: these tests use a stub rooted at tmp_path,
# with resolve_env's keywords (env + optional subfolder) and no env vars.

def _source_tree(tmp_path):
    """Two source folders: src_a (one table + a nested one + a non-parquet), src_b."""
    for relative in ["src_a/TBL_A.parquet", "src_a/nested/TBL_B.parquet",
                     "src_a/notes.txt", "src_b/TBL_C.parquet"]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
    return tmp_path


def _stub_resolver(root):
    def resolve(env, subfolder=None):
        return root / env / subfolder if subfolder is not None else root / env
    return resolve


def test_load_input_sources_finds_tables_per_source(tmp_path):
    root = _source_tree(tmp_path)
    sources = load_input_sources(
        [
            {"name": "a", "path": {"env": "src_a"}, "params": {"recurse": False}},
            {"name": "a_nested", "path": {"env": "src_a", "subfolder": "nested"}},
            {"name": "b", "path": {"env": "src_b"}},
        ],
        _stub_resolver(root),
    )
    assert sources == {
        "a": {root / "src_a" / "TBL_A.parquet": "TBL_A"},
        "a_nested": {root / "src_a" / "nested" / "TBL_B.parquet": "TBL_B"},
        "b": {root / "src_b" / "TBL_C.parquet": "TBL_C"},
    }


def test_load_input_sources_passes_path_node_as_keywords(tmp_path):
    root = _source_tree(tmp_path)
    calls = []

    def recording_resolver(**path):
        calls.append(path)
        return root / "src_b"

    load_input_sources([{"name": "b", "path": {"env": "X", "subfolder": "y"}}], recording_resolver)
    assert calls == [{"env": "X", "subfolder": "y"}]


def test_load_input_sources_empty_input_is_no_sources(tmp_path):
    assert load_input_sources([], _stub_resolver(tmp_path)) == {}


@pytest.mark.parametrize("entry, error", [
    ({"path": {"env": "src_b"}}, KeyError),                          # no name
    ({"name": "b"}, KeyError),                                       # no path
    ({"name": "b", "path": {"subfolder": "x"}}, TypeError),          # no env for the resolver
    ({"name": "b", "path": {"env": "src_b", "folder": "x"}}, TypeError),  # unknown key
    ({"name": "b", "path": "src_b"}, TypeError),                     # path not a mapping
    ({"name": "z", "path": {"env": "missing"}}, FileNotFoundError),  # root is not a folder
])
def test_load_input_sources_errors(tmp_path, entry, error):
    with pytest.raises(error):
        load_input_sources([entry], _stub_resolver(_source_tree(tmp_path)))


def test_load_input_sources_propagates_resolver_error(tmp_path):
    def unset_env(**path):
        raise RuntimeError("X is not set in .env or in the environment")

    with pytest.raises(RuntimeError, match="X is not set"):
        load_input_sources([{"name": "b", "path": {"env": "X"}}], unset_env)


# ---------------------------------------------------------------------------
# 7b. prune_outputs - artifacts of tables no longer produced
# ---------------------------------------------------------------------------

def _artifact_tree(tmp_path):
    """Schedules-like output: <folder>/<source>/<table>.yaml plus files prune must not touch."""
    for relative in ["out/a/TBL_WELLS.yaml", "out/a/TBL_OLD.yaml", "out/a/notes.txt",
                     "out/a/nested/TBL_NESTED.yaml", "out/b/TBL_LEVELS.yaml",
                     "out/gone/TBL_GONE.yaml"]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x", encoding="utf-8")
    return tmp_path / "out"


def test_prune_outputs_deletes_only_stale_artifacts_of_current_sources(tmp_path):
    folder = _artifact_tree(tmp_path)
    deleted = prune_outputs(folder, {"a": ["TBL_WELLS"], "b": []}, ".yaml")
    assert deleted == [folder / "a" / "TBL_OLD.yaml", folder / "b" / "TBL_LEVELS.yaml"]
    assert not any(path.exists() for path in deleted)
    for kept in ["a/TBL_WELLS.yaml", "a/notes.txt", "a/nested/TBL_NESTED.yaml",
                 "gone/TBL_GONE.yaml"]:              # not a current source: untouched
        assert (folder / kept).exists()


def test_prune_outputs_dry_run_deletes_nothing(tmp_path):
    folder = _artifact_tree(tmp_path)
    would = prune_outputs(folder, {"a": ["TBL_WELLS"]}, ".yaml", dry_run=True)
    assert would == [folder / "a" / "TBL_OLD.yaml"]
    assert all(path.exists() for path in would)


def test_prune_outputs_missing_folder_is_nothing(tmp_path):
    assert prune_outputs(tmp_path / "missing", {"a": []}, ".json") == []


def test_tables_by_name_leaves_out_repeated_names(tmp_path):
    """FK targets are found by file stem: a name in two places is ambiguous
    and left out (its FKs stay unverified)."""
    wells, pumps, other = (pd.DataFrame({"x": [i]}) for i in range(3))
    tables = {
        "a": {tmp_path / "a" / "TBL_WELLS.parquet": wells, tmp_path / "a" / "TBL_PUMPS.parquet": pumps},
        "b": {tmp_path / "b" / "TBL_PUMPS.parquet": other},
    }
    assert tables_by_name(tables) == {"TBL_WELLS": wells}


# ---------------------------------------------------------------------------
# 8. Package exports
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name, module", [
    ("check_authoring", "meta_tools.check"),
    ("check_provenance", "meta_tools.check"),
    ("check_mechanical", "meta_tools.check"),
    ("check_inspect", "meta_tools.check"),
    ("build_reading_key", "meta_tools.build"),
    ("prune_outputs", "meta_tools.etl"),
    ("tables_by_name", "meta_tools.etl"),
])
def test_exported_from_meta_tools(name, module):
    """Per-surface checkers and build_reading_key import from `meta_tools`
    and are the same objects as in their submodule."""
    import importlib
    import meta_tools
    assert name in meta_tools.__all__
    assert getattr(meta_tools, name) is getattr(importlib.import_module(module), name)
