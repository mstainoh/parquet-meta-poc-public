"""The only thing critical to import from another repo's ETL.

    parquet      to_parquet - stamps the `meta` block (keys+semantics+provenance,
                 group 2+3+5) into the parquet; WRITER_VERSION, what it stamps
                 as `provenance.writer_version`
    provenance   get_yaml_provenance - derives group 5
"""

from .parquet import WRITER_VERSION, to_parquet
from .provenance import get_yaml_provenance

__all__ = ["to_parquet", "get_yaml_provenance", "WRITER_VERSION"]
