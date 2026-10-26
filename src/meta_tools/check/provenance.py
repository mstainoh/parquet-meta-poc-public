"""Checks `provenance` + `schema_version` (group 5), already stamped in
the parquet, against meta_contract.yaml. Unlike `authoring.py`, this
surface is never hand-written - the writer (`meta_tools.write`) builds it
and it arrives JSON-serialized, so `written_at` arrives as an ISO string,
not a `datetime` (`schema.py` accepts both forms). Run it on the stamped
block (`etl.read_stamped_metadata`), not on `get_yaml_provenance` output:
`writer_version` is only added by `to_parquet`."""

from __future__ import annotations

from .contract import load_contract
from .schema import check_metadata
from ..fields import PROVENANCE_FIELDS

CONTRACT = load_contract()

__all__ = ["check_provenance"]


def check_provenance(data, **kwargs):
    """Validate a `provenance` + `schema_version` block against the contract.

    See `check_metadata` (`schema.py`) for the parameters and return value -
    this only binds `top_spec` to `meta.schema_version` + `meta.provenance`.
    """
    top_spec = {name: CONTRACT["meta"][name] for name in PROVENANCE_FIELDS}
    return check_metadata(data, top_spec, path="meta", **kwargs)
