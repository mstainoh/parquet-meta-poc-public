"""Checks a `meta` block (keys + semantics, authoring stage) against
meta_contract.yaml. The comparison itself lives in `schema.py` (generic,
shared with `provenance.py`, `mechanical.py` and `inspect.py`) - this only
resolves which sub-tree of the contract corresponds to authoring."""

from __future__ import annotations

from .contract import load_contract
from .schema import check_metadata
from ..fields import AUTHORING_FIELDS

CONTRACT = load_contract()

__all__ = ["check_authoring"]


def check_authoring(data, **kwargs):
    """Validate a `meta` block (`keys` + `semantics`) against the contract.

    See `check_metadata` (`schema.py`) for the parameters and return value -
    this only binds `top_spec` to `meta.keys` + `meta.semantics`. Any other
    top-level key (a hand-written `provenance` or `schema_version`) is an
    error: the writer stamps those (`check_provenance`).
    """
    top_spec = {name: CONTRACT["meta"][name] for name in AUTHORING_FIELDS}
    return check_metadata(data, top_spec, path="meta", **kwargs)
