"""Writer for parquet-embedded schema metadata (the `meta` block: keys +
semantics + provenance, groups 2+3+5 of the metadata model).
"""


import json
from pathlib import Path
from typing import Union
import pyarrow.parquet as pq
import pyarrow as pa
import logging
log = logging.getLogger(__name__)

__all__ = ["to_parquet"]

WRITER_VERSION = 1

def to_parquet(df, path: Path, metadata: Union[dict, None] = None,
               force_overwrite_metadata: bool = False, 
               preserve_index: bool|None = None,
               writer_version: int|None=WRITER_VERSION,
               **kwargs):
    """
    Write a DataFrame to parquet, embedding metadata as schema-level
    metadata.

    Parameters
    ----------
    df : pandas.DataFrame
        Data to write.
    path : Path
        Destination file.
    metadata : dict or None, default None
        Extra metadata to embed under the b'meta' schema key (JSON-encoded)
        - e.g. the meta: block from a YAML config plus provenance. When the
        provenance block is present, ``writer_version`` is stamped there.
        Skipped if falsy.
    force_overwrite_metadata : bool, default False
        If False (default), raise if b'meta' is already present
        in the table's schema metadata. Set True to overwrite instead.
    preserve_index : bool or None, default None
        Whether to keep the DataFrame index as a column in the parquet
        file. None (default) preserves it only if the index has a name - an
        unnamed index is treated as leftover from an upstream
        dropna/query/sort, not meaningful data.
    writer_version : int or None, default WRITER_VERSION
        Version of the writer code stamped into ``metadata["provenance"]``.
        ``None`` skips the stamp.
    **kwargs
        Passed through to pyarrow.parquet.write_table (e.g. compression).

    Raises
    ------
    ValueError
        If b'meta' is already in the schema metadata and
        `force_overwrite_metadata` is False.

    Notes
    -----
    `metadata` (if given) is embedded under b'meta', JSON-encoded, separate
    from any existing schema metadata already on the table. ``df.attrs`` gets
    no key of its own: pyarrow already keeps it in the pandas metadata
    (``attributes``), and ``pandas.read_parquet`` restores it.
    Encoding uses ``json.dumps(..., default=str)``: a timestamp such as
    ``provenance.written_at`` is read back as a string.
    """
    # Only a named index is preserved: naming it is the caller's deliberate
    # choice. An unnamed index is leftover from an upstream dropna/query/sort,
    # and pyarrow would write it as a ghost __index_level_0__ column.
    # A MultiIndex has `.name` None even when its levels are named: check every level.
    if preserve_index is None:
        preserve_index = any(name is not None for name in df.index.names)

    table = pa.Table.from_pandas(df, preserve_index=preserve_index)

    # Stamp writer-owned metadata without mutating the caller's dictionary.
    if metadata and "provenance" in metadata and writer_version is not None:
        metadata = dict(metadata)
        metadata["provenance"] = dict(metadata["provenance"])
        metadata["provenance"]["writer_version"] = writer_version

    # Existing metadata (if any) - pyarrow keys are always bytes
    schema_metadata = table.schema.metadata or {}

    def _set(key: bytes, value: dict):
        if key in schema_metadata:
            if not force_overwrite_metadata:
                raise ValueError(f'Conflicting key {key!r} already present in schema. '
                                 'Review table or use force_overwrite_metadata=True')
            else:
                log.info('%s key present - overwriting', key.decode())
        schema_metadata[key] = json.dumps(value, default=str).encode()

    log.debug('Writing table metadata')
    if metadata:
        _set(b'meta', metadata)

    table = table.replace_schema_metadata(schema_metadata)
    log.debug('Writing table to %s', path)

    pq.write_table(table, path, **kwargs)