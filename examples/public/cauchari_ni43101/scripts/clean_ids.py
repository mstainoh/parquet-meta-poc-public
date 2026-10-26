"""Normalize well/piezometer identifiers across section 10 CSVs.

Reads csv/raw/*.csv, writes the intermediates _build/*.csv and _build/_edits.csv (one row per edit).
Usage: python -I clean_ids.py <cauchari_dir>
"""
import re
import sys
from pathlib import Path

import pandas as pd

root = Path(sys.argv[1])
raw, clean = root / "csv" / "raw", root / "_build"
clean.mkdir(exist_ok=True)
edits = []


def log(table, key, col, old, new, kind, reason):
    edits.append(dict(tabla=table, fila=key, columna=col, valor_raw=old, valor_clean=new, tipo=kind, motivo=reason))


def rd(name):
    return pd.read_csv(raw / name, dtype=str, keep_default_na=False)


def pad_id(s):
    """'DL-08'->'DL-008', 'DL-003 B'->'DL-003B', 'RC17S-13'->'RC17S-013'."""
    s = re.sub(r"\s+", "", s)
    m = re.fullmatch(r"([A-Z]+\d*[A-Z]?)-(\d+)([A-Z]?)", s)
    if not m:
        return s
    return f"{m.group(1)}-{int(m.group(2)):03d}{m.group(3)}"


def ddh_id(s):
    """'DDH-1'->'DDH-01', 'DDH-10B'->'DDH-10B'."""
    m = re.fullmatch(r"DDH-?(\d+)([A-Z]?)", s)
    return f"DDH-{int(m.group(1)):02d}{m.group(2)}" if m else s


def apply(df, table, src, dst, fn, kind, reason, keycol):
    """Add/overwrite column dst = fn(src) and log changes vs the source column."""
    new = df[src].map(fn)
    for k, o, n in zip(df[keycol], df[src], new):
        if o != n:
            log(table, k, dst, o, n, kind, reason)
    df[dst] = new
    return df


# --- 10.1 / 10.3: PE ids already canonical -----------------------------
for t, f in (("10.1", "t10_1.csv"), ("10.3", "t10_3.csv"), ("11.1", "t11_1.csv"), ("11.2", "t11_2.csv"), ("10.2", "t10_2.csv")):
    rd(f).to_csv(clean / f, index=False)

# --- 10.4 / 10.5: DDH ids to two digits ------------------------------------
t4 = rd("t10_4.csv")
t4["well_id_raw"] = t4["well_id"]
t4 = apply(t4, "10.4", "well_id_raw", "well_id", ddh_id, "id_normalized", "DDH-n -> DDH-nn (zero-pad, same convention as 10.5 and 15.3)", "well_id_raw")
t4.to_csv(clean / "t10_4.csv", index=False)
t5 = rd("t10_5.csv")
t5.to_csv(clean / "t10_5.csv", index=False)

# --- 10.6 piezometers ---------------------------------------------------------
t6 = rd("t10_6.csv")
t6["borehole_id"] = t6["dd_borehole_id"].map(pad_id)
for k, o, n in zip(t6["piezometer_name"], t6["dd_borehole_id"], t6["borehole_id"]):
    if o != n:
        log("10.6", k, "borehole_id", o, n, "id_normalized", "remove spaces, zero-pad number to 3 digits, glue B suffix")
status = t6["piezometer_name"].where(t6["piezometer_name"].isin(["Cemented", "Abandoned"]), "")
t6["status"] = status.str.lower()
for k, s in zip(t6["dd_borehole_id"], status):
    if s:
        log("10.6", k, "status", s, s.lower(), "column_misplaced", "status text sits in the piezometer-name column of the source; moved to `status`, piezometer_id left empty")
pz = t6["piezometer_name"].where(t6["status"] == "", "")
t6["piezometer_id"] = pz.map(pad_id)
for k, o, n in zip(t6["dd_borehole_id"], pz, t6["piezometer_id"]):
    if o != n:
        log("10.6", k, "piezometer_id", o, n, "id_normalized", "remove spaces, zero-pad number to 3 digits (DL-08 -> DL-008, DL-003 B -> DL-003B)")
t6 = t6.drop(columns=["collar_id"])
log("10.6", "*", "collar_id", "(number of piezometer)", "(dropped)", "column_dropped",
    "collar_id grouped S and D piezometers by number, but their boreholes differ (DL displaced 8.6-69 m); borehole_id is the physical collar key")
cols = [c for c in t6.columns if c not in ("borehole_id", "piezometer_id", "status")]
t6 = t6[cols[:3] + ["borehole_id", "piezometer_id", "status"] + cols[3:]]
t6.to_csv(clean / "t10_6.csv", index=False)

# --- 10.7 chemistry: column holds piezometer names, not boreholes ---------
t7 = rd("t10_7.csv")
t7 = t7.rename(columns={"dd_borehole_id": "piezometer_name"})
log("10.7", "*", "dd_borehole_id", "dd_borehole_id", "piezometer_name", "column_renamed", "source header says 'DD Borehole ID' but values are piezometer names (join key to 10.6)")
t7["piezometer_id"] = t7["piezometer_name"].map(pad_id)
for k, o, n in zip(t7["piezometer_name"], t7["piezometer_name"], t7["piezometer_id"]):
    if o != n:
        log("10.7", k, "piezometer_id", o, n, "id_normalized", "zero-pad number to 3 digits / remove spaces (DL-003B ok, DL-008 etc.)")
lookup = t6[t6["piezometer_id"] != ""].drop_duplicates("piezometer_id").set_index("piezometer_id")["borehole_id"]
t7["borehole_id"] = t7["piezometer_id"].map(lookup).fillna("")
miss = sorted(set(t7.loc[t7["borehole_id"] == "", "piezometer_id"]))
t7.to_csv(clean / "t10_7.csv", index=False)

# --- 10.8 production wells --------------------------------------------------------------------------
t8 = rd("t10_8.csv")
t8["tabla"] = "10.8"
log("10.8", "*", "tabla", "t10_8", "10.8", "label_fixed", "table label normalized (also in 10.8 intervals and 10.9)")
t8["xy_swapped"] = "true"
log("10.8", "*", "x_raw/y_raw", "x_raw=north, y_raw=east", "easting/northing", "xy_swapped", "all 38 rows have X and Y inverted in the source table; easting/northing assigned by magnitude")
m = t8["pumping_well"] == "W-16"
old = t8.loc[m, "easting"].iloc[0]
t8.loc[m, "easting"] = "3427420"
old_nota = t8.loc[m, "nota"].iloc[0]
t8.loc[m, "nota"] = old_nota.replace("valor tal cual en origen, no corregido (posible typo)",
                                     "corregido 3227420->3427420 segun Apendice 2 Tabla 4 (pag PDF 446), northing coincide")
log("10.8", "W-16", "nota", "...no corregido (posible typo)...", "...corregido 3227420->3427420...", "note_updated", "extraction note rewritten after the correction")
log("10.8", "W-16", "easting", old, "3427420", "value_corrected", "source typo; Appendix 2 Table 4 (PDF 446) lists W-16 at 3427420 with the same northing 7394024")
t8.to_csv(clean / "t10_8.csv", index=False)
ti = rd("t10_8_intervals.csv")
ti["tabla"] = "10.8"
ti.to_csv(clean / "t10_8_intervals.csv", index=False)

# --- 10.9 ----------------------------------------------------------------------------------------------
t9 = rd("t10_9.csv")
t9["tabla"] = "10.9"
t9.to_csv(clean / "t10_9.csv", index=False)

import shutil
for f in ("t15_3.csv", "tA1_1.csv", "tA2.csv", "t16_1.csv"):
    shutil.copy(raw / f, clean / f)  # coordinate tables: no edit here, canonical pozo_id is added in finalize.py
pd.DataFrame(edits).to_csv(clean / "_edits.csv", index=False)
print("edits:", len(edits))
print("10.7 piezometers without borehole in 10.6:", miss)
print(pd.DataFrame(edits).groupby(["tabla", "tipo"]).size())
