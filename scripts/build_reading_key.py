#!/usr/bin/env python3
"""
Regenerates reading_key.yaml from meta_contract.yaml: every agent_rule,
grouped by field - the SQL agent's reading key, projected from the contract.

Standalone: depends only on the contract, not on tables or .env. Run by
hand whenever a field's agent_rule or value_descriptions changes; the
output is committed, not part of run_metadata_etl.py.

Usage: python scripts/build_reading_key.py

Config: none - no config file, no ``.env``.

Reads:
    - ``src/meta_tools/meta_contract.yaml`` (via `build_reading_key` / `load_contract`).
      Nothing else - no tables, no ``config/etl.yaml``.

Writes:
    - ``reading_key.yaml`` at the repo root. Always overwritten, no ``--dry-run``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from meta_tools.build import build_reading_key

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "reading_key.yaml"


def main() -> None:
    """Build the reading key from the contract and write it to
    ``reading_key.yaml`` at the repo root.

    Returns
    -------
    None
    """
    reading_key = build_reading_key()
    OUTPUT_PATH.write_text(
        yaml.safe_dump(reading_key, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"reading_key.yaml written: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
