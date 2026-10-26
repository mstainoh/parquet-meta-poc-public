"""Checks the `inspect/<TABLE>.yaml` sidecar (group 4, `inspect`) against
meta_contract.yaml. Written by an agent (`/inspect-table`), never the
scanner or the ETL - unlike `mechanical`, this surface goes stale (see
`observed_row_count` in the contract)."""

from __future__ import annotations

from .contract import load_contract
from .schema import check_metadata

CONTRACT = load_contract()

__all__ = ["check_inspect"]


def check_inspect(data, **kwargs):
    """Validate an `inspect` (group 4) block against the contract.

    See `check_metadata` (`schema.py`) for the parameters and return value -
    this only binds `top_spec` to the whole `inspect` group (unlike
    `check_authoring`/`check_provenance`, there's no sub-selection: the
    sidecar file is the whole block every time). Each ``findings`` item is
    validated against the ``fields:`` of ``inspect.findings``, with an
    indexed path in messages (``inspect.findings[0].severity``, see
    `_check_group`).
    """
    return check_metadata(data, CONTRACT["inspect"], path="inspect", **kwargs)
