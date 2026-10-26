"""
Readers for the surfaces where metadata lives (config yaml, today).
They validate nothing: they pull the dict from wherever it is and return
it as-is.
"""

from __future__ import annotations

from pathlib import Path

import yaml

__all__ = ["read_yaml", "find_meta_blocks"]


def read_yaml(path: str | Path, encoding='utf-8') -> dict:
    """Read a YAML file into a dict.

    Parameters
    ----------
    path : str or Path
        Location of the YAML file.
    encoding : str, default 'utf-8'
        Encoding used to read the file.

    Returns
    -------
    dict
        Parsed content, via `yaml.safe_load`.
    """
    return yaml.safe_load(Path(path).read_text(encoding=encoding))


def find_meta_blocks(data: dict, key: str = "meta") -> dict[str, dict]:
    """Recursively find every `key` block nested in `data`.

    Parameters
    ----------
    data : dict
        Parsed YAML to search.
    key : str, default "meta"
        Name of the block to look for.

    Returns
    -------
    dict[str, dict]
        Maps `'__file__'` to the block found at the root (if present), and
        the name of each containing dict to the block found inside it
        (e.g. `'edges'` for a block found at `tables.edges.meta`). Does not
        recurse into a dict once a block has already been found inside it.
        Names are not qualified: two containers with the same name at
        different depths overwrite each other.
    """
    blocks = {"__file__": data[key]} if data.get(key) is not None else {}
    for k, v in data.items():
        if k == key or not isinstance(v, dict):
            continue
        if v.get(key) is not None:
            blocks[k] = v[key]
        else:
            blocks.update(find_meta_blocks(v, key))
    return blocks
