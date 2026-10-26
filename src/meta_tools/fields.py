"""Field-name constants for the metadata contract groups.

Hand-kept copy of names declared in `meta_contract.yaml`. `check/` uses
the `meta` sub-groups to pick its slice of the contract;
`ParquetScanner.check` uses the `mechanical` names to catch the dicts it
builds drifting from the contract (`tests/test_contract.py` checks the
`mechanical` names against the contract).
"""

__all__ = [
    "AUTHORING_FIELDS", "PROVENANCE_FIELDS", "MECHANICAL_SCHEMA_VERSION",
    "MECHANICAL_FIELDS", "VERIFICATION_FIELDS", "FK_FIELDS",
]

# --------------------------- #
# Source parquet fields
# --------------------------- #
AUTHORING_FIELDS = ("keys", "semantics")  # group 2+3, authoring surface (check_authoring)
PROVENANCE_FIELDS = ("schema_version", "provenance")  # group 5 + envelope, stamped (check_provenance)

# --------------------------- #
# Mechanical + check fields
# --------------------------- #
MECHANICAL_SCHEMA_VERSION = 2  # shape of THIS group, versioned separately from the contract

MECHANICAL_FIELDS = (
    "schema_version", "scanned_at", "row_count", "file_columns", "dtypes",
    "null_count", "n_distinct", "min_max", "file_size_bytes",
    "file_index_columns", "file_uniques",
)

VERIFICATION_FIELDS = ("uniques_verified", "not_nulls_verified", "index_columns_verified")

FK_FIELDS = ("fk_orphans", "fk_verified")

