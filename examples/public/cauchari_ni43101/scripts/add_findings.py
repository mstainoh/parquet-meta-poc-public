"""Append curated findings to the inspect sidecars: the Figure 10.2 platform findings (visual reading,
nothing applied) and the observations moved out of the semantics caveats (observed numbers belong in inspect).
Idempotent: a finding whose note is already present is not added twice. Every sidecar is written with LF endings.
Usage: python add_findings.py <dataset_dir>   (repo .venv: yaml + meta_tools)
"""
import datetime as dt
import sys
from pathlib import Path

import pandas as pd
import yaml

from meta_tools.check.inspect import check_inspect

root = Path(sys.argv[1])
ins = root / "data_processed" / "inspect"
csvdir = root / "csv" / "modified"
FIG = "Figure 10.2 'Borehole Locations and Associated Drilling Platforms' (p.157/PDF 173; raster map, labels read visually)"
NEW = {
    "t10_6_piezometers": [dict(columns=["platform_raw", "piezometer_id", "borehole_id"], severity="note", note=(
        f"{FIG} labels each 2017 platform with its piezometers and, on some, a production well: 01 = DL-001, ML-001, SL-001, W-01; "
        "02 = DL-004B, ML-004, SL-004,B; 04 = DL-002B, ML-002, SL-002, W-02; 05 = DL-010, ML-010B, SL-010; 06 = DL-008, ML-008; "
        "07 = DL-005, ML-005, W-05; 08-15 = DL-007, ML-007, SL-007, W-07; 09 = DL-003 B, ML-003; 10 = DL-012, ML-012; 11-12 = DL/ML/SL-009; "
        "16 = DL-011, ML-011; 17-20 = DL/ML/SL-014; 18 = DL/ML/SL-013; 03-13-14 = DL-006B, ML-006, SL-006, W17-06. The numbers match platform_raw. "
        "Piezometers with the same number are co-located (SL/ML same XY, DL 8.6-69 m away). Hypothesis, NOT applied to any value: "
        "the W listed on a platform shares the pad with those piezometers (see t10_8_production_wells inspect for the coordinate check)."))],
    "t10_8_production_wells": [dict(columns=["pumping_well", "easting", "northing"], severity="note", note=(
        f"Coordinate check of the platform grouping of {FIG}, nothing changed: W17-06 is 21-32 m from DL-006B/ML-006 (platform 03-13-14) in every source. "
        "Appendix 2 puts W-02B 0-9 m from DL-002B/ML-002 (platform 04, labelled W-02) while this table puts it 149 m away - evidence for the "
        "Appendix 2 position of W-02B. W-1, W-5 and W-7 (this table and Appendix 2) are 3.7, 6.7 and 23-24 km from platforms 01, 07 and 08-15, "
        "where the figure labels W-01, W-05, W-07: either different wells with similar names or wrong coordinates, unresolved. "
        "0 m coincidences that agree with the figure: W18-05 = DD18D-005 (platform CS-28), W18-06 = DD18D-006 (platform CS-31); "
        "also W-30 = DD17D-003, W17-12 = DD17D-012, W-13 = DD18D-004 (not labelled together in the figure)."))],
    "t10_3_rc_brine_chemistry": [dict(columns=["well_id"], severity="note", note=(
        f"{FIG} groups some RC holes with PB pumping wells in one map label: PE-21 with PB-03A ('PB-03,A / PP-03B,C / PP-B-PB3 / PE-21 / PF-03A,B'), "
        "PE-20 with PB-01 ('DDH-10,B / PP-01A,B,C / PF-01A,B / PB-01 / PE-20'), PE-18 with PB-02 ('PE-18 / PP-PB2 / PB-02,A / PP-02A'). "
        "PB-01 and PB-03A have XY and Z in Appendix 1; PB-02 is in no extracted table. Hypothesis only: these PE may share the PB location. "
        "No coordinate was assigned - easting/northing of PE-18/20/21 stay NULL in `wells`."))],
    "t10_5_ddh_brine_chemistry": [dict(columns=["well_id"], severity="note", note=(
        f"{FIG}: the label 'PLATFORM PB-04' lists PB04, PP-04A,B and DDH-12,A. PB-04 has XY (Table 10.8, Appendix 1) and Z (Appendix 1). "
        "Hypothesis only: DDH-12 (chemistry in this table) may share the PB-04 location. Not applied: DDH-12 has no coordinates in `wells`."))],
    "wells": [dict(columns=["pozo_id", "easting", "northing"], severity="note", note=(
        f"The RC (PE) and DDH 2009-2010 holes without coordinates appear only as dots on {FIG}; no table gives their XY. "
        "The figure's grouped labels suggest PE-20, DDH-10 and DDH-10B with PB-01; PE-21 with PB-03A; DDH-12 and DDH-12A with PB-04; "
        "PE-18 with PB-02 (PB-02 has no XY anywhere). NOT applied: their easting/northing stay NULL. Georeferencing the figure was out of scope."))],
}

CURATED = {
    "t10_3_rc_brine_chemistry": [
        dict(columns=["well_id", "mg_mg_l", "mg_li_orig"], severity="note", note=(
            "PE-10 interval 60-152 m prints Mg = 174 mg/L with Mg/Li = 0, far below every other interval (Mg in the thousands). "
            "Kept as printed and flagged in `nota`: likely a source typo, not confirmed by any other table.")),
        dict(columns=["well_id", "from_m", "to_m"], severity="note", note=(
            "The first 5 rows of PDF p.166 carry no borehole label in the source (the table continues from p.165, where the last "
            "label is PE-17). They were assigned to PE-17 by continuation, since the next label is PE-18.")),
    ],
    "t10_5_ddh_brine_chemistry": [
        dict(columns=["well_id", "mg_mg_l"], severity="note", note=(
            "DDH-12 interval 65-70 m prints Mg as '927' with no thousands separator, while the rest of the column uses a point as "
            "thousands separator (e.g. 4.847). It was read as 927 mg/L by magnitude; it may be a truncated value.")),
    ],
    "t10_7_piezometer_brine_chemistry": [
        dict(columns=["piezometer_id", "mg_mg_l", "li_mg_l"], severity="note", note=(
            "DL-001 intervals 300-400 and 400-450 m repeat exactly the same Mg (1230.1 mg/L) with different Li: possible copy "
            "error in the source. Kept as printed.")),
    ],
    "t10_8_production_wells": [
        dict(columns=["pumping_well", "easting", "northing"], severity="data_error", note=(
            "W-7 and W-10 print identical coordinates in this table. Appendix 2 Table 4 places W-7 about 1.3 km away from that "
            "point, so the W-7 row most likely repeats W-10's coordinates. `wells` keeps this table's value for W-7 "
            "(xy_conflicto = true); prefer Appendix 2 for W-7.")),
    ],
    "tA2_4_production_well_model": [
        dict(columns=["pozo_id", "screen_top_masl", "screen_bottom_masl"], severity="data_error", note=(
            "PB-04: the model screen (3902.67 to 3589.13 masl) does not match Appendix 1, whose land surface and screen "
            "depths give 3887.67 to 3649.67 masl. The model screen bottom sits about 358 m below top_model_masl, deeper than "
            "the 305 m total depth of the well. For the other wells shared with Appendix 1 the two agree within a few metres "
            "(PB-03A bottom differs by about 6.6 m). Prefer Appendix 1 for PB-04 screen elevations.")),
    ],
    "t15_3_steady_state_residuals": [
        dict(columns=["well_id", "northing_m", "observed_gw_elev_masl"], severity="note", note=(
            "DDH-17 has northing 7343262, about 13 km south of the southernmost other hole of the dataset (DD19D-15) and 20 km "
            "south of the next Table 15.3 point (PE-08), and its observed level is above the others. Footnote *: reported as "
            "flowing well; the model uses a censoring target. Kept and flagged.")),
    ],
}
for k, v in CURATED.items():
    NEW[k] = NEW.get(k, []) + v

w = yaml.safe_load(open(ins / "wells.yaml", encoding="utf-8"))
# programa was rebuilt from the source table after the audit: drop the finding it fixed, restate the production count
w["findings"] = [f for f in w["findings"] if not f["note"].startswith("programa = DDH_2019_2024")]
for f in w["findings"]:
    if f["note"].startswith("Text p.161/PDF 177 says 43 production wells"):
        f["note"] = ("Text p.161/PDF 177 says 43 production wells were drilled since 2011; Table 10.8 details 38 "
                     "(programa = PRODUCCION_10_8) and the 5 others are not identified in the report (the Pozo 44-46 numbering of Table 16.1 "
                     "fits 43). programa = MODELO_APENDICE_2 holds wells that appear only in the Appendix 2 reserve-model table; "
                     "whether they exist physically is not stated.")
NEW["wells"] = w["findings"] + [f for f in NEW["wells"] if f["note"] not in {x["note"] for x in w["findings"]}]


def rep(d, s):
    return d.represent_scalar("tag:yaml.org,2002:str", s, style=">" if len(s) > 90 else None)


yaml.add_representer(str, rep)
for stem, findings in NEW.items():
    p = ins / f"{stem}.yaml"
    doc = yaml.safe_load(open(p, encoding="utf-8")) if p.exists() else dict(
        schema_version=1, observed_at=dt.date.today(), observed_row_count=0, observed_by="claude", findings=[])
    if stem == "wells":
        doc["findings"] = findings
    else:
        have = {f["note"] for f in doc["findings"]}
        doc["findings"] += [f for f in findings if f["note"] not in have]
    doc["observed_row_count"] = len(pd.read_csv(csvdir / f"{stem}.csv"))
    cols = set(pd.read_csv(csvdir / f"{stem}.csv", nrows=0).columns)
    assert all(set(f["columns"]) <= cols for f in doc["findings"]), stem
    assert check_inspect(doc) is True, stem
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        yaml.dump(doc, fh, allow_unicode=True, sort_keys=False, width=110)
    print(stem, len(doc["findings"]))

for p in ins.glob("*.yaml"):  # sidecars not touched above: LF endings only
    b = p.read_bytes()
    if b"\r\n" in b:
        p.write_bytes(b.replace(b"\r\n", b"\n"))
