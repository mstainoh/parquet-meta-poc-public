"""Consistency checking against `meta_contract.yaml`.

    contract     loads the spec: CONTRACT_PATH, ContractError, load_contract
    sources      readers for the surfaces where metadata lives (config yaml)
    schema       generic dict-vs-contract comparison engine: check_metadata
    authoring    validates keys+semantics (group 2+3), the surface before the ETL
    provenance   validates provenance+schema_version (group 5), already stamped in the parquet
    mechanical   validates the scanner fragment (group 1)
    inspect      validates the inspect/<TABLE>.yaml sidecar (group 4), written by an agent
"""

from .authoring import check_authoring
from .contract import CONTRACT_PATH, ContractError, load_contract
from .inspect import check_inspect
from .mechanical import check_mechanical
from .provenance import check_provenance
from .schema import check_metadata
from .sources import find_meta_blocks, read_yaml

__all__ = [
    "check_authoring", "check_provenance", "check_mechanical", "check_inspect",
    "check_metadata",
    "CONTRACT_PATH", "ContractError", "load_contract",
    "find_meta_blocks", "read_yaml",
]
