"""Metadata contract tooling.

Tooling only, not the runtime of any UI: whatever consumes the metadata
it produces does not depend on anything here.

    from meta_tools import check_authoring
    check_authoring(meta)       # keys + semantics of one `meta` block

Organized by criticality, not only by group of the model (see
`docs/model/metadata_model.md` and `docs/ADR/ADR.md`):

    write/        CRITICAL - what the producer's ETL has to import to
                  stamp the table:
        parquet       to_parquet - stamps the `meta` block (group 2+3+5)
        provenance    get_yaml_provenance - derives group 5
    mechanical.py group 1 (ParquetScanner): stats + verification of the
                  declared `keys` (group 2). Not a requirement of the ETL.
    check/        consistency check against the contract, not a
                  requirement to write:
        contract      loads the spec: CONTRACT_PATH, ContractError, load_contract
        sources       readers for the surfaces (config yaml, today)
        schema        check_metadata - generic dict-vs-contract engine
        authoring     check_authoring - keys+semantics (group 2+3), before
                      the ETL runs
        provenance    check_provenance - provenance+schema_version
                      (group 5), as stamped
        mechanical    check_mechanical - the scanner's JSON fragment
                      (group 1)
        inspect       check_inspect - the inspect/<TABLE>.yaml sidecar
                      (group 4)
    etl.py        find_tables, load_input_sources, read_stamped_metadata,
                  check_table, tables_by_name, check_table_links, prune_outputs
    build.py      agent artifacts (ADR-014): build_schedule, build_audit,
                  dict_to_flat (flat index), build_reading_key
    fields.py     contract field names as constants

Group 4 (`inspect`) is not produced by anything in this package: it is
meant to be written by an external agent (`/inspect-table`).
"""

from .check import (
    CONTRACT_PATH, ContractError, check_authoring, check_inspect, check_mechanical, check_metadata,
    check_provenance, find_meta_blocks, load_contract, read_yaml,
)
from .mechanical import ParquetScanner
from .etl import (
    check_table, check_table_links, find_tables, load_input_sources, prune_outputs,
    read_stamped_metadata, tables_by_name,
)
from .build import build_audit, build_reading_key, build_schedule, dict_to_flat
from .write import get_yaml_provenance, to_parquet

__all__ = [
    "check_metadata", "ContractError", "load_contract", "CONTRACT_PATH",
    "check_authoring", "check_provenance", "check_mechanical", "check_inspect",
    "find_meta_blocks", "read_yaml",
    "get_yaml_provenance", "to_parquet",
    "ParquetScanner",
    "check_table", "find_tables", "load_input_sources", "read_stamped_metadata",
    "tables_by_name", "check_table_links", "prune_outputs",
    "build_schedule", "build_audit", "dict_to_flat", "build_reading_key",
]
