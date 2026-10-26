"""
Loads `meta_contract.yaml`: the spec every metadata surface (`meta`,
`mechanical`, `inspect`) is validated against. The only place that knows
where the contract lives.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

__all__ = ["CONTRACT_PATH", "ContractError", "load_contract"]

# meta_contract.yaml lives at the package root, one level above check/.
CONTRACT_PATH = Path(__file__).resolve().parents[1] / "meta_contract.yaml"


class ContractError(Exception):
    """The contract itself is malformed. A bug in the spec, not in the data."""


@lru_cache(maxsize=1)
def load_contract(path: str | Path = CONTRACT_PATH) -> dict:
    """Load and parse the metadata contract.

    Parameters
    ----------
    path : str or Path, default CONTRACT_PATH
        Location of the contract YAML file.

    Returns
    -------
    dict
        Parsed contract, with at least the top-level `types` and `meta` keys.

    Raises
    ------
    ContractError
        If `path` does not exist, the YAML fails to parse, or a required
        top-level key (`types`, `meta`) is missing.

    Notes
    -----
    Cached with `functools.lru_cache`: the contract is read from disk only
    once per process.
    """
    p = Path(path)
    if not p.is_file():
        raise ContractError(f"contract not found at {p}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ContractError(f"{p} failed to parse: {exc}") from exc
    for key in ("types", "meta"):
        if key not in data:
            raise ContractError(f"{p}: missing top-level key `{key}`")
    return data
