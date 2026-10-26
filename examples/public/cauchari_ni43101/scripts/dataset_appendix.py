"""Regenerate the "Appendix: all findings" section of DATASET.md from data_processed/inspect/*.yaml.

Everything after the appendix heading is replaced.
Usage: python -I dataset_appendix.py <dataset_dir>
"""
import sys
from pathlib import Path

import yaml

root = Path(sys.argv[1])
md = root / "DATASET.md"
HEAD = "## Appendix: all findings"
body = md.read_text(encoding="utf-8").split(HEAD)[0]
out = [HEAD, "", "Generated from `data_processed/inspect/*.yaml` by `scripts/dataset_appendix.py`.", ""]
for f in sorted((root / "data_processed" / "inspect").glob("*.yaml")):
    d = yaml.safe_load(f.read_text(encoding="utf-8"))
    out += [f"### `{f.stem}` (observed rows: {d['observed_row_count']})", ""]
    out += [f"- **{x['severity']}** [{', '.join(x['columns'])}]: {' '.join(x['note'].split())}" for x in d["findings"]]
    out.append("")
md.write_text(body + "\n".join(out), encoding="utf-8", newline="\n")
