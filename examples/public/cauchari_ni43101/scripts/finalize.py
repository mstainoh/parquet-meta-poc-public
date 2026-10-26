"""Write csv/modified/<stem>.csv and data_processed/parquet/<stem>.yaml (authoring `meta` block).

Reads _build/ intermediates, adds canonical `pozo_id` to the coordinate tables,
validates keys/FKs against the data and the YAML against check_authoring.
Usage: python -I finalize.py <dataset_dir>   (run with the repo .venv: needs meta_tools, yaml, pandas)
"""
import re
import sys
from pathlib import Path

import pandas as pd
import yaml

from meta_tools.check.authoring import check_authoring

root = Path(sys.argv[1])
clean = root / "_build"
out, ymeta = root / "csv" / "modified", root / "data_processed" / "parquet"
out.mkdir(parents=True, exist_ok=True)
ymeta.mkdir(parents=True, exist_ok=True)
SRC = "Source: NI 43-101 technical report on the Cauchari-Olaroz operation (effective Jan 8 2025)"
TRACE = {
    "tabla": "report table number the row was extracted from",
    "pag_impresa": "printed page of the report where the row is",
    "pag_pdf": "PDF page of the row (printed page + 16)",
    "nota": "free-text flag written at extraction (source typo, outlier, reconstructed row, cross-check result); empty = nothing to flag",
}


def rd(f):
    return pd.read_csv(clean / f, dtype=str, keep_default_na=False)


# canonical pozo_id for the coordinate tables, from xy_sources.csv ------------------------------
xy = rd("xy_sources.csv")
canon = {(r.tabla, r.id_raw): r.pozo_id for r in xy.itertuples()}
EXTRA_EDITS = []


def with_pozo_id(df, tabla_key, idcol):
    df = df.copy()
    df.insert(3, "pozo_id", [canon[(tabla_key, i)] for i in df[idcol]])
    for i, p in zip(df[idcol], df["pozo_id"]):
        if i != p:
            EXTRA_EDITS.append(dict(tabla=tabla_key, fila=i, columna="pozo_id", valor_raw=i, valor_clean=p, tipo="id_normalized",
                                    motivo="canonical id so the table joins with `wells` (zero-pad, appendix spelling variants, piezometer -> borehole)"))
    return df


T = {}  # stem -> dict(df, meta)

# --------------------------------------------------------------------------------------------------------
T["t10_1_rc_boreholes"] = dict(
    df=rd("t10_1.csv"),
    desc=f"RC (reverse circulation) boreholes PE-01..PE-22 drilled in 2009-2010 with the interval and length drilled. {SRC}, Table 10.1 (printed p.147, PDF p.163).",
    grain="one row per RC borehole",
    cav=("from_m is empty where the source prints '-' (it means the hole starts at surface, not 0 declared); only deepened twin holes declare a start. "
         "The source prints two column pairs per row; they were unfolded to one row per hole. Use to_m for hole depth and SUM(length_m) "
         "only for metres drilled. The table has no coordinates: see `wells` / section 15.3 and Appendix 1 for XY. "),
    ci={"well_id": "RC borehole id, PE-nn; joins `wells.pozo_id`", "from_m": "start of the drilled interval in m; empty = '-' in source",
        "to_m": "end of the drilled interval in m", "length_m": "metres drilled as printed (equals to_m - from_m in every row)"},
    uniq=["well_id"], fks=[("well_id", "wells", "pozo_id")], cross=["t10_3_rc_brine_chemistry", "t10_2_rc_brine_sample_counts", "wells"],
    scope="campaign_window")
T["t10_2_rc_brine_sample_counts"] = dict(
    df=rd("t10_2.csv"),
    desc=f"Counts of brine samples collected and submitted for laboratory analysis, by sample type. {SRC}, Table 10.2 (printed p.148, PDF p.164).",
    grain="one row per sample category as printed (includes subtotal and total rows)",
    cav="Rows mix categories and their totals (e.g. 'Total Field Samples'); do not sum the column across rows. The counts cover only the 2009-2010 programs (RC and DDH) and include holes "
        "with no row in the chemistry tables. Commas in the source are thousands separators.",
    ci={"description": "sample category as printed, including subtotal/total rows", "brine_samples": "number of brine samples"},
    uniq=["description"], fks=[], cross=["t10_3_rc_brine_chemistry"], scope="campaign_window")
T["t10_3_rc_brine_chemistry"] = dict(
    df=rd("t10_3.csv"),
    desc=f"Brine chemistry averaged over depth intervals of the RC boreholes PE-04..PE-22 (B, K, Li, Mg, SO4 and ratios). {SRC}, Table 10.3 (printed p.149-150, PDF p.165-166).",
    grain="one row per RC borehole and depth interval - an interval average, not an individual sample",
    cav=("Values are averages over the interval, not point samples. mg_li_orig is Mg/Li rounded to an integer as printed; use mg_li_recalc (mg_mg_l / li_mg_l, 2 decimals) for any calculation. "
         "Convention in source: comma = thousands in concentrations, point = decimal in ratios. length_m is smaller than to_m - from_m in some rows exactly as printed "
         "(unsampled metres, lost circulation while drilling); do not 'fix' it. Outliers are kept as printed and flagged in `nota` and in inspect." " Every row is already an average over an interval of very different length: weight by interval length when averaging, and do not pool Tables 10.3, 10.5 and 10.7 without considering campaign, sampling method and laboratory."),
    ci={"well_id": "RC borehole id; joins `t10_1_rc_boreholes` and `wells.pozo_id`", "from_m": "interval top, m (depth reference not stated in the source)", "to_m": "interval bottom, m (same reference as from_m)",
        "length_m": "interval length as printed (may be < to_m - from_m)", "b_mg_l": "boron, mg/L", "k_mg_l": "potassium, mg/L", "li_mg_l": "lithium, mg/L",
        "mg_mg_l": "magnesium, mg/L", "so4_mg_l": "sulfate, mg/L", "mg_li_orig": "Mg/Li as printed, rounded to integer", "k_li": "K/Li ratio as printed",
        "so4_li": "SO4/Li ratio as printed (recomputing from the concentrations differs by up to ~0.1%)", "mg_li_recalc": "Mg/Li computed from mg_mg_l / li_mg_l (not in the source)"},
    uniq=["well_id", "from_m", "to_m"], fks=[("well_id", "t10_1_rc_boreholes", "well_id"), ("well_id", "wells", "pozo_id")],
    cross=["t10_1_rc_boreholes", "wells"], scope="campaign_window")
T["t10_4_ddh_boreholes_2009_2010"] = dict(
    df=rd("t10_4.csv"),
    desc=f"Diamond drill holes (DDH) of the 2009-2010 program with drilled interval and length. {SRC}, Table 10.4 (printed p.151, PDF p.167).",
    grain="one row per DDH hole",
    cav=("well_id was normalized to two digits (DDH-1 -> DDH-01) to match Tables 10.5 and 15.3; the id as printed is kept in well_id_raw. The source writes 'DDH9A' without a hyphen. "
         "from_m is empty where the source prints '-'. Twins (suffix A-D) are separate holes of the same site. No coordinates here."),
    ci={"well_id": "canonical DDH id (DDH-nn[A]); joins `wells.pozo_id`", "well_id_raw": "id exactly as printed in this table",
        "from_m": "start of drilled interval in m; empty = '-' in source", "to_m": "end of drilled interval in m", "length_m": "metres drilled as printed"},
    uniq=["well_id"], fks=[("well_id", "wells", "pozo_id")], cross=["t10_5_ddh_brine_chemistry", "wells"], scope="campaign_window")
T["t10_5_ddh_brine_chemistry"] = dict(
    df=rd("t10_5.csv"),
    desc=f"Brine chemistry averaged over depth intervals for DDH-01, 04, 06, 08, 12 and 13 (B, K, Li, Mg, SO4, Mg/Li). {SRC}, Table 10.5 (printed p.152, PDF p.168).",
    grain="one row per DDH hole and depth interval - an interval average, not a point sample",
    cav=("THIS table writes a point as THOUSANDS separator in K, Mg and SO4 (4.847 = 4847) while Mg/Li is a true decimal (2.20); both were normalized to plain numbers "
         "(rule: d.ddd in K/Mg/SO4 -> thousands). length_m differs from to_m - from_m in some rows exactly as printed and the report does not explain it. The table has no K/Li or SO4/Li." " Every row is already an average over an interval of very different length: weight by interval length when averaging, and do not pool Tables 10.3, 10.5 and 10.7 without considering campaign, sampling method and laboratory."),
    ci={"well_id": "DDH id as printed (already two digits); joins `wells.pozo_id`", "from_m": "interval top, m", "to_m": "interval bottom, m", "length_m": "interval length as printed",
        "b_mg_l": "boron, mg/L", "k_mg_l": "potassium, mg/L (source uses '.' as thousands)", "li_mg_l": "lithium, mg/L", "mg_mg_l": "magnesium, mg/L",
        "so4_mg_l": "sulfate, mg/L (source uses '.' as thousands)", "mg_li_orig": "Mg/Li as printed (decimal)", "mg_li_recalc": "Mg/Li computed from mg_mg_l / li_mg_l"},
    uniq=["well_id", "from_m", "to_m"], fks=[("well_id", "t10_4_ddh_boreholes_2009_2010", "well_id"), ("well_id", "wells", "pozo_id")],
    cross=["t10_4_ddh_boreholes_2009_2010", "wells"], scope="campaign_window")
T["t10_6_piezometers"] = dict(
    df=rd("t10_6.csv"),
    desc=f"Piezometers installed in the 2017-2019 DDH/RC boreholes: screen interval, depth and coordinates (Gauss-Kruger zone 3 by magnitude; the table does not declare its CRS, EPSG:22183 is assumed - see DATASET.md). {SRC}, Table 10.6 (printed p.154-155, PDF p.170-171).",
    grain="one row per piezometer (several piezometers - SL/ML - can share one borehole)",
    cav=("Model borehole -> piezometer as N:1: borehole_id is the physical collar (use it to join `wells`); a collar id derived during extraction from the piezometer number mixed shallow and deep holes "
         "that are tens of metres apart, so it was dropped. dd_borehole_id/piezometer_name keep the raw text; borehole_id/piezometer_id are normalized "
         "(spaces removed, 3-digit numbers: DL-08 -> DL-008, 'DL-003 B' -> DL-003B). For DD18D-001..007 the source puts the state ('Cemented'/'Abandoned') in the piezometer column; "
         "it was moved to `status` and piezometer_id is empty, with no screen data. DD19D-PE09 comes split in two lines in the source and was rebuilt (diameter 2in read from the image). "
         "Platform text such as '3 13 14' is kept raw. By design SL and ML share one borehole and DL is a separate hole nearby; sites that break this are in inspect. Screen depths are m below top of well (mbtw). "),
    ci={"borehole_id": "normalized drill hole id (physical collar); joins `wells.pozo_id`", "piezometer_id": "normalized piezometer id (SL/ML/DL-nnn[B]); empty for cemented/abandoned holes",
        "status": "cemented / abandoned when the source says so in place of a piezometer name; empty otherwise", "dd_borehole_id": "borehole id as printed",
        "piezometer_name": "piezometer text as printed", "screen_diameter_in": "screen diameter in inches", "platform_raw": "drill platform text as printed (may list several)",
        "total_depth_m": "total depth in m", "screen_top_mbtw": "top of screen, m below top of well", "screen_base_mbtw": "base of screen, m below top of well",
        "x_coordinate_m": "easting, EPSG:22183 (X first in this table: NOT swapped)", "y_coordinate_m": "northing, EPSG:22183"},
    uniq=["borehole_id", "piezometer_id", "piezometer_name"], fks=[("borehole_id", "wells", "pozo_id")],
    cross=["t10_7_piezometer_brine_chemistry", "wells", "t15_3_steady_state_residuals"], scope="campaign_window")
T["t10_7_piezometer_brine_chemistry"] = dict(
    df=rd("t10_7.csv"),
    desc=f"Brine chemistry averaged over depth intervals for the 2017-2019 piezometer boreholes (Li, K, Mg, H3BO3, SO4, Mg/Li). {SRC}, Table 10.7 (printed p.158-160, PDF p.174-176).",
    grain="one row per piezometer and depth interval - an interval average, not a point sample",
    cav=("The source's first column is titled 'DD Borehole ID' but holds PIEZOMETER names; it was renamed piezometer_name and normalized to piezometer_id, "
         "and borehole_id was added by lookup in Table 10.6. The header typos 'Lenth' (length_m) and 'Plataform' are source typos. "
         "Concentrations are mg/L; boron is reported as H3BO3. mg_li_orig is as printed (1 decimal), mg_li_recalc is computed. "
         "The intervals are bailer profiles of the hole, not the piezometer screen. The DD19D-001 rows continue the DL-001 profile but belong to a different borehole (DD19D-001). To compare boron with b_mg_l of Tables 10.3/10.5 convert first: B = H3BO3 x 0.1748." " Every row is already an average over an interval of very different length: weight by interval length when averaging, and do not pool Tables 10.3, 10.5 and 10.7 without considering campaign, sampling method and laboratory."),
    ci={"piezometer_name": "name as printed (e.g. DL-003B)", "piezometer_id": "normalized piezometer id; joins `t10_6_piezometers.piezometer_id`",
        "borehole_id": "drill hole of the piezometer, from Table 10.6; joins `wells.pozo_id`", "interval_raw": "interval text as printed", "from_m": "interval top, m",
        "to_m": "interval bottom, m", "length_m": "interval length (equals to_m - from_m)", "li_mg_l": "lithium, mg/L", "k_mg_l": "potassium, mg/L",
        "mg_mg_l": "magnesium, mg/L", "h3bo3_mg_l": "boric acid H3BO3, mg/L (not elemental boron)", "so4_mg_l": "sulfate, mg/L",
        "mg_li_orig": "Mg/Li as printed", "mg_li_recalc": "Mg/Li computed from mg_mg_l / li_mg_l"},
    uniq=["piezometer_id", "from_m", "to_m"], fks=[("piezometer_id", "t10_6_piezometers", "piezometer_id"), ("borehole_id", "wells", "pozo_id")],
    cross=["t10_6_piezometers", "wells"], scope="campaign_window")
T["t10_8_production_wells"] = dict(
    df=rd("t10_8.csv"),
    desc=f"Production wells: year, depth, coordinates, drilling method and casing/screen construction. {SRC}, Table 10.8 (printed p.162-167, PDF p.178-182).",
    grain="one row per production well",
    cav=("X AND Y ARE SWAPPED in the source for all rows (column X holds the northing). easting/northing were assigned by magnitude (x_raw/y_raw keep the printed values) - "
         "use easting/northing, never x_raw/y_raw. W-16 easting was corrected from 3227420 to 3427420 following Appendix 2 Table 4 (same northing). "
         "Several wells disagree with Appendix 1 or Appendix 2 coordinates: see `wells.xy_conflicto` and inspect. Depth and coordinate errors found "
         "against other tables are in inspect, not corrected. Multi-line cells (drilling_diameter_inches, casing and screen lengths) are raw text with ' | ' between lines, not numbers; the bit diameters per interval are parsed in the intervals table. "
         "WR-10 spans a page break (kept as one row). "),
    ci={"pumping_well": "well id as printed; joins `wells.pozo_id`", "year": "year drilled", "total_depth_m": "total depth, m", "x_raw": "'X' column as printed - actually NORTHING",
        "y_raw": "'Y' column as printed - actually EASTING", "easting": "easting in EPSG:22183 (from y_raw, W-16 corrected)", "northing": "northing in EPSG:22183 (from x_raw)",
        "drilling_method": "drilling method as printed", "drilling_diameter_inches": "raw multi-line text of bit diameters and ranges",
        "total_length_casing_inserted_m": "raw text of casing sizes and lengths", "total_length_screen_casing_inserted_m": "raw text of screen sizes and lengths; each length is the sum of several screen sections alternating with solid casing",
        "solid_casing": "solid casing material", "screen_casing": "screen casing material", "xy_swapped": "true when x/y were swapped by this cleaning (all rows)"},
    uniq=["pumping_well"], fks=[("pumping_well", "wells", "pozo_id")], cross=["t10_8_production_well_intervals", "tA2_4_production_well_model", "wells"],
    scope="static")
T["t10_8_production_well_intervals"] = dict(
    df=rd("t10_8_intervals.csv"),
    desc=f"Drilling intervals (bit diameter and depth range) of the production wells, parsed from the multi-line cell of Table 10.8. {SRC}, Table 10.8 (PDF p.178-182).",
    grain="one row per production well and drilling interval",
    cav=("Derived by splitting the 'drilling diameter' cell of Table 10.8; the casing and screen cells were NOT aligned to intervals. In some wells the last interval does not end at total_depth_m "
         "of the main table, and a few intervals do not start where the previous one ends (see inspect of the main table). "),
    ci={"pumping_well": "well id; joins `t10_8_production_wells`", "interval_no": "order of the interval inside the cell, from 1", "drilling_diameter_raw": "text of the interval as printed",
        "bit_diameter_inches": "bit diameter in inches as decimal", "from_m": "start depth, m", "to_m": "end depth, m"},
    uniq=["pumping_well", "interval_no"], fks=[("pumping_well", "t10_8_production_wells", "pumping_well")], cross=["t10_8_production_wells"], scope="static")
T["t10_9_ddh_boreholes_2022_2024"] = dict(
    df=rd("t10_9.csv"),
    desc=f"DD19D boreholes of the 2022-2024 program with piezometer screen and coordinates. {SRC}, Table 10.9 (printed p.169, PDF p.185).",
    grain="one row per borehole",
    cav=("The source uses a DECIMAL COMMA (41,07) and was normalized. IDs are DD19D-xx (not DDH19D). The BIS marker sits in different columns: DD19D-06 has piezometer 'DD19D-06 BIS' "
         "and DD19D-26 BIS has piezometer 'DD19D-26'. The program is in Cauchari Sur, outside the certified resource area; the rotary wells were not sampled for chemistry (pumping tests ongoing at report date). DD19D-13 prints screen_base (537) greater than total_depth (465): kept as printed. X/Y are in the right order here. "),
    ci={"borehole_id": "drill hole id; joins `wells.pozo_id`", "piezometer_name": "piezometer name when different from the hole (empty otherwise)",
        "screen_diameter_inches": "diameter text as printed; for the rotary wells '8\", 12\"' is the two casing sizes of the telescopic design, not one screen diameter", "type": "hole type as printed", "plataform": "platform text as printed (source spelling)",
        "total_depth_m": "total depth, m", "screen_top_mbtw": "top of screen, m below top of well", "screen_base_mbtw": "base of screen, m below top of well",
        "x_raw": "X as printed (easting)", "y_raw": "Y as printed (northing)", "easting": "easting EPSG:22183", "northing": "northing EPSG:22183"},
    uniq=["borehole_id"], fks=[("borehole_id", "wells", "pozo_id")], cross=["wells"], scope="campaign_window")
T["t11_1_pumping_test_sampling_frequency"] = dict(
    df=rd("t11_1.csv"),
    desc=f"Measurement frequency to follow during a pumping test by time interval. {SRC}, Table 11.1 (printed p.179, PDF p.195).",
    grain="one row per time interval of the test",
    cav="Text table. Despite the header, the schedule applies to the MEASUREMENTS of dynamic water level, flow and turbidity during a pumping test (and to recovery readings), not to brine samples.",
    ci={"time_interval": "time window since the start of the test, as printed", "sampling_frequency": "how often to measure in that window, as printed"},
    uniq=["time_interval"], fks=[], cross=[], scope="static")
T["t11_2_geotechnical_analyses"] = dict(
    df=rd("t11_2.csv"),
    desc=f"Geotechnical property analyses run on the core and the procedure (standard) used for each. {SRC}, Table 11.2 (printed p.182, PDF p.198).",
    grain="one row per analysis",
    cav="Text table (method catalogue, no results). ",
    ci={"analysis": "property analysed", "procedure": "standard or procedure used"},
    uniq=["analysis"], fks=[], cross=[], scope="static")
T["t15_3_steady_state_residuals"] = dict(
    df=with_pozo_id(rd("t15_3.csv"), "15.3", "well_id"),
    desc=f"Steady-state model calibration: observed vs computed groundwater elevation at 27 monitoring locations, with XY. {SRC}, Table 15.3 (printed p.266-267, PDF p.282-283).",
    grain="one row per monitoring location",
    cav=("Elevations are masl (groundwater ELEVATION), not depth to water. DDH-17 is a flowing well far south of the other points (footnote *): its observed value "
         "is a censored model target; kept and flagged. SL-xx are piezometers: pozo_id maps them to their borehole. "
         "Levels are of 2018, pre-development conditions, mostly in shallow wells, and are not corrected for brine density. CAU* rows come from a third party (Adv. Lithium, 2018), not from the project. well_id is the id as printed (SL-13 has 2 digits in the source). The 'Adv. Lithium, 2018' source cells are offset vertically from their rows in the PDF; assigned one-to-one in order. "),
    ci={"well_id": "id as printed", "pozo_id": "canonical id; joins `wells.pozo_id` (SL-xxx -> its borehole, DDH-n -> DDH-nn)", "x_raw": "X as printed (easting)", "y_raw": "Y as printed (northing)",
        "easting_m": "easting EPSG:22183", "northing_m": "northing EPSG:22183", "observed_gw_elev_masl": "observed groundwater elevation, masl",
        "computed_gw_elev_masl": "model groundwater elevation, masl", "residual_m": "observed - computed, m", "residual_raw": "residual text as printed (with asterisk)", "source": "who measured it"},
    uniq=["well_id"], fks=[("pozo_id", "wells", "pozo_id")], cross=["wells"], scope="static")
T["tA1_1_exploration_well_locations"] = dict(
    df=with_pozo_id(rd("tA1_1.csv"), "A1.T1", "well_id"),
    desc=f"Location and construction of exploration/production wells: coordinates, land surface elevation, depth, screen and hydrostratigraphic unit. {SRC}, Appendix 1 Table 1 (printed p.426-427, PDF p.442-443).",
    grain="one row per well",
    cav=("land_surface_elev_masl is the only collar elevation (z_collar) available in the extracted set. The report's note: coordinates of wells built after 2011 come from the DEM; "
         "those built in 2010-2011 from differential GPS (POSGAR 94). fuente_z_raw applies that note by year_constructed (the selection by year is ours; the note speaks of coordinates). "
         "Id spelling differs from Appendix 2 (PB-3A/PB-03A, PB4/PB-04, W04-A/W-04A): use pozo_id. 'PB-I' keeps the letter I of the source. CW-62 has elevation 'NA' (empty). "
         "Multi-unit hsu_raw cells are not split. Depths are m below land surface. "),
    ci={"well_id": "id as printed", "pozo_id": "canonical id; joins `wells.pozo_id`", "x_raw": "X as printed (easting)", "y_raw": "Y as printed (northing)", "easting_m": "easting EPSG:22183",
        "northing_m": "northing EPSG:22183", "land_surface_elev_masl": "land surface (collar) elevation, masl; empty for NA", "land_surface_elev_raw": "elevation text as printed",
        "year_constructed": "year the well was built", "total_depth_m": "total depth, m below land surface", "screen_top_m_bls": "screen top, m below land surface",
        "screen_bottom_m_bls": "screen bottom, m below land surface", "hsu_raw": "hydrostratigraphic unit text as printed", "fuente_z_raw": "report note on how coordinates/elevation were obtained, chosen by year_constructed"},
    uniq=["well_id"], fks=[("pozo_id", "wells", "pozo_id")], cross=["wells", "tA2_4_production_well_model"], scope="static")
T["tA2_4_production_well_model"] = dict(
    df=with_pozo_id(rd("tA2.csv"), "A2.T4", "well_id"),
    desc=f"Production wells of the reserve model (OS4 case): XY, top of model, screen, pumping, predicted drawdown and lithium by year. {SRC}, Appendix 2 Table 4 (printed p.430-431, PDF p.446-447).",
    grain="one row per production well in the reserve model",
    cav=("top_model_masl is the top of the MODEL cell, not the collar elevation (close to, but not always equal to, the Appendix 1 land surface). Pumping, drawdown and Li columns are model PREDICTIONS "
         "(years 1/10/20/30/40), not measurements. Id spelling differs from Appendix 1 (WR-3 -> WR-03 in pozo_id). Coordinates are printed as integers. "),
    ci={"well_id": "id as printed", "pozo_id": "canonical id; joins `wells.pozo_id`", "tabla_apendice": "table number inside Appendix 2", "x_raw": "X as printed (easting)",
        "y_raw": "Y as printed (northing)", "easting_m": "easting EPSG:22183", "northing_m": "northing EPSG:22183", "top_model_masl": "top of the model at the well, masl (not collar)",
        "screen_top_masl": "screen top, masl", "screen_bottom_masl": "screen bottom, masl", "start_year": "first pumping year as a MODEL year index (1-40), not a calendar year", "end_year": "last pumping year, model year index (1-40)",
        "pumping_year1_lps": "pumping rate in model year 1, L/s (0 when the well starts in year 2)", "pumping_years2_40_lps": "pumping rate years 2-40, L/s",
        "drawdown_year1_m": "predicted drawdown at year 1, m", "li_year1_mgl": "predicted Li at year 1, mg/L (same pattern for years 10/20/30/40)"},
    uniq=["well_id"], fks=[("pozo_id", "wells", "pozo_id")], cross=["t10_8_production_wells", "wells"], scope="static")
T["t16_1_infill_wells_2024"] = dict(
    df=with_pozo_id(rd("t16_1.csv"), "16.1", "borehole_id"),
    desc=f"Infill production wells 44, 45 and 46 (2024) with platform, contractor, stage and coordinates. {SRC}, Table 16.1 (printed p.283, PDF p.299).",
    grain="one row per infill well",
    cav="Stage is a snapshot at report date. The table says location 'Olaroz'. Wells 44-46 are not in Appendix 2. ",
    ci={"borehole_id": "well label as printed ('Pozo 44')", "pozo_id": "canonical id POZO-nn; joins `wells.pozo_id`", "platform": "drill platform id", "stage": "construction stage as printed",
        "x_raw": "X as printed (easting)", "y_raw": "Y as printed (northing)", "easting_m": "easting EPSG:22183", "northing_m": "northing EPSG:22183"},
    uniq=["borehole_id"], fks=[("pozo_id", "wells", "pozo_id")], cross=["wells"], scope="current_state")
T["wells"] = dict(
    df=rd("pozo.csv"),
    desc=("Registry of every physical hole named in the extracted tables (RC, DDH, piezometer boreholes, production, infill) with its best coordinates and collar elevation. "
          "DERIVED table: built by this cleaning from sections 10, 15.3, 16.1 and Appendices 1-2 of the NI 43-101 report."),
    grain="one row per hole id named in the extracted tables (pozo_id), including reserve-model wells of Appendix 2 and wells under construction; the piezometers of a hole are in `t10_6_piezometers`",
    cav=("Many RC (PE) and DDH holes of 2009-2010 have NO coordinates anywhere in the report: easting/northing are empty and must stay NULL (do not estimate). "
         "fuente_xy is the first source found in the priority 10.6, 10.8, 10.9, 15.3, A1.T1, A2.T4, 16.1; fuentes_xy lists all. dispersion_xy_m is the largest distance between the sources; "
         "xy_conflicto = true when it is above 10 m (the report contradicts itself: check before using). z_collar comes only from Appendix 1 (land surface); the other tables have no collar elevation. "
         "Holes at the same place with different ids are listed in `well_aliases`, they are NOT merged."),
    ci={"pozo_id": "canonical hole id used by every other table", "programa": "report table that first names the hole: RC_2009_2010 (T10.1), DDH_2009_2010 (T10.4/10.5), DDH_2017_2019 (T10.6, includes DD18D and DD19D-001/PE09), DDH_ROTARY_2022_2024 (T10.9: DDH and rotary holes), PRODUCCION_10_8 (T10.8), PRODUCCION_2024 (T16.1), APENDICE_1, MODELO_APENDICE_2 (only in the reserve model table), SOLO_TABLA_15_3",
        "easting": "easting, EPSG:22183 (POSGAR 94 / Argentina 3); NULL = not in the report", "northing": "northing, EPSG:22183; NULL = not in the report",
        "lat": "latitude, decimal degrees WGS 84 (EPSG:4326), 6 decimals. Not in the report: reprojected by this cleaning from easting/northing with pyproj (PROJ), EPSG:22183 -> EPSG:4326, POSGAR 94 taken as WGS 84 (sub-metre difference). Inherits every caveat of easting/northing (assumed CRS, xy_conflicto); NULL where easting is NULL",
        "lon": "longitude, decimal degrees WGS 84 (EPSG:4326); same conversion and caveats as lat", "crs": "assumed CRS of easting/northing: no extracted table declares it; Gauss-Kruger zone 3 follows from the magnitude and Appendix 1 mentions POSGAR 94 (the report also uses UTM 19S / WGS 84 elsewhere)",
        "fuente_xy": "report table the coordinates were taken from", "fuentes_xy": "all report tables with coordinates for this hole, separated by |",
        "dispersion_xy_m": "largest distance in m between the coordinates of the different sources", "xy_conflicto": "true when dispersion_xy_m > 10; false also when there is only one source (not cross-checked) - see fuentes_xy",
        "z_collar": "land surface elevation, masl, from Appendix 1 at the Appendix 1 position (GPS for wells built 2010-2011, DEM for later ones); NULL if unknown. When fuente_xy is not A1.T1 and xy_conflicto is true, easting/northing and z_collar are not from the same point", "fuente_z": "source table of z_collar"},
    uniq=["pozo_id"], fks=[], cross=["well_aliases", "t10_6_piezometers"], scope="static")
T["well_aliases"] = dict(
    df=rd("alias_pozo.csv"),
    desc="Pairs of different hole ids whose coordinates coincide within 5 m (same site, possibly the same hole or a re-use of the platform). DERIVED from the coordinates of the report tables.",
    grain="one row per pair of ids (pozo_a < pozo_b)",
    cav=("Coordinate coincidence is a hint, NOT proof of identity: a twin hole next to another also matches. The ids are not merged in `wells`. Pairs where both holes are from Table 10.6 (shallow/deep twins of one site) are excluded. "
         "W-7 and W-10 appear because the source repeats coordinates (suspected copy error), not because they are the same well."),
    ci={"pozo_a": "first id (alphabetical)", "pozo_b": "second id", "dist_m": "distance between the coordinates, m", "prog_a": "program of pozo_a", "prog_b": "program of pozo_b",
        "relacion": "kind of link; always mismo_sitio_por_coordenada"},
    uniq=["pozo_a", "pozo_b"], fks=[("pozo_a", "wells", "pozo_id"), ("pozo_b", "wells", "pozo_id")], cross=["wells"], scope="static")

# ----------------------------------------------------------------------------------------------------------------------------
wells_ids = set(T["wells"]["df"]["pozo_id"])
problems = []


def str_rep(dumper, s):
    return dumper.represent_scalar("tag:yaml.org,2002:str", s, style=">" if len(s) > 90 else None)


yaml.add_representer(str, str_rep)

for stem, t in T.items():
    df = t["df"]
    missing = [c for c in t["uniq"] + [k for k, *_ in t["fks"]] if c not in df.columns]
    if missing:
        problems.append((stem, "missing column", missing))
        continue
    dup = df.duplicated(subset=t["uniq"]).sum()
    if dup:
        problems.append((stem, "uniques violated", int(dup)))
    for s, tt, tc in t["fks"]:
        tdf = wells_ids if tt == "wells" else set(T[tt]["df"][tc])
        bad = sorted(set(df.loc[df[s] != "", s]) - tdf)
        if bad:
            problems.append((stem, f"FK {s}->{tt} orphans", bad[:8]))
    notnull = [c for c in t["uniq"] if (df[c] != "").all()]
    ci = dict(TRACE) if "tabla" in df.columns else {}
    ci = {k: v for k, v in ci.items() if k in df.columns}
    ci.update({k: v for k, v in t["ci"].items() if k in df.columns})
    bad_ci = [k for k in t["ci"] if k not in df.columns]
    if bad_ci:
        problems.append((stem, "column_info for unknown columns", bad_ci))
    meta = {"keys": {"uniques": t["uniq"], "not_nulls": notnull,
                     "foreign_keys": [dict(source_col=s, target_table=tt, target_col=tc) for s, tt, tc in t["fks"]]},
            "semantics": {"description": t["desc"], "grain": t["grain"], "caveats": t["cav"].strip(), "temporal_scope": t["scope"],
                          "cross_tables": t["cross"], "column_info": ci}}
    res = check_authoring(meta)
    if not res:
        problems.append((stem, "check_authoring", res))
    with open(ymeta / f"{stem}.yaml", "w", encoding="utf-8", newline="\n") as fh:
        yaml.dump({"meta": meta}, fh, allow_unicode=True, sort_keys=False, width=100)
    df.to_csv(out / f"{stem}.csv", index=False)

edits = pd.concat([rd("_edits.csv"), pd.DataFrame(EXTRA_EDITS)], ignore_index=True)
edits.to_csv(out / "_edits.csv", index=False)
print("tables:", len(T), "edits:", len(edits))
for p in problems:
    print("PROBLEM", p)
