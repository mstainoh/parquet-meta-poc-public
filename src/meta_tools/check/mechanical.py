"""Checks the scanner's JSON fragment (group 1, `mechanical`) against
meta_contract.yaml. Written by `ParquetScanner.to_json` (`mechanical.py`,
package root), never by hand - don't confuse the two modules."""

from __future__ import annotations

from .contract import load_contract
from .schema import check_metadata

CONTRACT = load_contract()

__all__ = ["check_mechanical"]


def check_mechanical(data, **kwargs):
    """Validate a `mechanical` (group 1) block against the contract.

    See `check_metadata` (`schema.py`) for the parameters and return value -
    this only binds `top_spec` to the whole `mechanical` group (unlike
    `check_authoring`/`check_provenance`, there's no sub-selection: the
    scanner writes the whole block every time).
    """
    return check_metadata(data, CONTRACT["mechanical"], path="mechanical", **kwargs)
