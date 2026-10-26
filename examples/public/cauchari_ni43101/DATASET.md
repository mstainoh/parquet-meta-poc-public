# Cauchari-Olaroz NI 43-101: drilling, piezometer and brine-chemistry tables

A small relational dataset of the tables published in a **public** NI 43-101 technical report on the
Cauchari-Olaroz lithium brine operation (Jujuy, Argentina). It covers wells, piezometers, coordinates,
collar elevations and brine chemistry, and is meant to be read by an agent that builds SQL queries
(e.g. DuckDB over the parquet files).

**Ground rules of the dataset**
- Every value comes from the report. Nothing was estimated, interpolated or georeferenced. Where the report has no
  value the cell is NULL.
- Every row keeps its source: `tabla` (report table), `pag_impresa` (printed page) and `pag_pdf` (PDF page = printed + 16).
- Number formats were normalized at extraction, per table (documented in `csv/raw/EXTRACTION_NOTES.md`). Edits on top
  of the extraction are few, explicit and logged in `csv/modified/_edits.csv` (id spelling, column moves, one typo
  fixed from another table of the same report). Everything else that looks wrong in the source is **kept as printed and
  reported as a finding**.
- Hypotheses (e.g. wells that share a drilling platform in Figure 10.2) are findings only. They never change a value.

## Source

| | |
|---|---|
| Document | NI 43-101 Technical Report, Cauchari-Olaroz operation (Lithium Americas (Argentina) Corp. / Minera Exar), "Operational Technical Report", effective date **8 January 2025** |
| File | `LAC-Report-NI-43-101-Jan-8-2025-Final_2_compressed.pdf` (448 PDF pages; printed page + 16 = PDF page) |
| Sections used | 10 Drilling and 11 Sample preparation, analyses and security, read in full (PDF 163-199); plus coordinate tables 15.3, 16.1, Appendix 1 Table 1 and Appendix 2 Table 4 |
| Extraction | pdfplumber by word coordinates, every page checked against its image (`pdftotext -layout` scrambles most of these tables) |
| Quality | `silver` (cleaned extraction of a published document; not re-measured data) |

Source data: the report is a public regulatory filing (NI 43-101 technical reports are filed on SEDAR+ and published
by the issuer), and its text carries no copyright notice or reproduction restriction. The tables belong to the report
and its authors; this dataset only re-publishes the tabulated values with their citation. **The repository's MIT license covers the code, scripts and metadata written here, not the
values taken from the report.** The PDF and its text are not included: get the report from the issuer's public
filings.

## Layout

| Path | Content |
|---|---|
| `csv/raw/` | Extraction from the PDF, one CSV per report table, untouched afterwards. Numbers are already normalized per table, `easting/northing` are assigned by magnitude next to the printed `x_raw/y_raw`, and `mg_li_recalc` is computed; printed text is kept in the `*_raw` columns. The row-level `nota` texts are kept as written at extraction (mixed Spanish/English). `pendientes_*.csv` = rows flagged as doubtful while extracting (they are also in the main CSV). `EXTRACTION_NOTES.md` = what was found and decided per table while extracting |
| `csv/modified/` | Clean tables (canonical ids, column fixes, canonical `pozo_id`) + the derived `wells` and `well_aliases`. `_edits.csv` = one row per edit on top of `csv/raw/` |
| `data_processed/parquet/<table>.parquet` | **The dataset.** Typed tables; the metadata is embedded in the parquet schema under the key `meta` (JSON): `keys` + `semantics` + `provenance` |
| `data_processed/parquet/<table>.yaml` | The `keys` + `semantics` of that table as readable YAML (authoring block of the metadata contract, the input of the parquet) |
| `data_processed/inspect/<table>.yaml` | **Findings** per table (`inspect` group of the contract, kept as a sidecar file): `severity` = `data_error` (can ruin a number) or `note` (context), the affected `columns`, and the evidence with page |
| `data_processed/mechanics/<source>/<table>.json` | Machine-computed facts per table (row count, dtypes, nulls, min/max, key and FK verification), written by `run_metadata_etl.py`; `<source>` = `cauchari_ni43101` |
| `data_processed/full_meta/` | The other outputs of `run_metadata_etl.py`: `schedules/<source>/` (keys + semantics + file_columns per table; `inspect` is null there because the ETL does not read the sidecars), `99_audit/<source>/` (full provenance), `index.txt`, `run_log.parquet` |
| `queries.md` | Five example questions with their SQL over these tables (DuckDB), each respecting the caveats above |
| `etl.sampledata.yaml` | Config of `scripts/run_metadata_etl.py` (repo) for this dataset |
| `scripts/` | Build scripts of this dataset (see "How the dataset was built") |

## How the dataset was built

1. **Extraction** (PDF → `csv/raw/`): each table was rebuilt with pdfplumber from word coordinates and checked against
   the rendered page; `pdftotext -layout` was used only to read prose and locate tables. Number formats were normalized
   per table (documented in `EXTRACTION_NOTES.md`); ambiguous rows went to `pendientes_*.csv` instead of being guessed.
   Done interactively, with no script: the reproducible chain starts at `csv/raw/`.
2. **Cleaning** (`csv/raw/` → `csv/modified/` + the `keys`/`semantics` YAML of each table).
3. **Findings**: an independent read of sections 10-11 against the tables wrote `data_processed/inspect/`; curated
   findings are added by script.
4. **Stamping**: each clean CSV becomes a parquet with its YAML and a common `provenance` embedded.
5. **Mechanical metadata**: the repo's metadata ETL re-checks the stamped metadata against the contract and scans the data.
6. **Docs**: the findings appendix of this file is regenerated.

### Script summary

Every script takes the dataset folder as its only argument (`python -I scripts/<script> <dataset_dir>`), except the ETL,
run from the repo root with `SAMPLEDATAPATH` set to this folder. Run them in this order.

| # | ETL scope | Script | Reads → writes | What it does |
|---|---|---|---|---|
| - | Extraction | (none, manual) | PDF → `csv/raw/` | Tables rebuilt from the PDF and checked against the page images; notes in `EXTRACTION_NOTES.md` |
| 1 | Cleaning | `clean_ids.py` | `csv/raw/` → `_build/` (temporary) | Unifies ids across tables (DDH-1 → DDH-01, DL-08 → DL-008), moves "Cemented"/"Abandoned" to `status`, flags the swapped X/Y of Table 10.8, fixes W-16 from Appendix 2; logs every change in `_edits.csv` |
| 2 | Cleaning | `registry.py` | `_build/` + coordinate tables → `_build/` | Builds `wells` (one row per hole: best-source X/Y, `lat`/`lon` reprojected with pyproj, Appendix 1 Z, `xy_conflicto` when sources disagree) and `well_aliases` (different ids within 5 m) |
| 3 | Cleaning + metadata | `finalize.py` | `_build/` → `csv/modified/*.csv`, `data_processed/parquet/*.yaml` | Adds the canonical `pozo_id` to the coordinate tables, writes the clean CSVs and each table's `keys` + `semantics` YAML; checks uniques and FKs against the data and the YAML with `check_authoring` |
| 4 | Findings | `add_findings.py` | → `data_processed/inspect/*.yaml` | Adds the curated findings (Figure 10.2 platforms, observations kept out of the caveats); idempotent, LF endings |
| 5 | Stamping | `to_parquet.py` | `csv/modified/` + YAML → `data_processed/parquet/*.parquet` | Types each column (text, integer, float, boolean), checks no value changed, writes the parquet with `meta_tools.write.to_parquet` (YAML + common `provenance`) |
| 6 | Mechanical metadata | `scripts/run_metadata_etl.py` (repo) with `etl.sampledata.yaml` | `data_processed/parquet/` → `mechanics/`, `full_meta/` | Reads the parquets, re-checks keys/semantics/provenance against the contract, scans each table (stats, uniques, not_nulls, FKs) and writes the mechanical JSON, schedules, audit, index and run log |
| 7 | Docs | `dataset_appendix.py` | `data_processed/inspect/` → `DATASET.md` | Regenerates the "Appendix: all findings" section |

Requirements: the repo's venv (`meta_tools`, pandas, pyarrow, yaml) plus `pyproj` for `registry.py`.

Rules followed throughout: no value is invented or estimated; a value is corrected only when another table of the same
report states it (one case, W-16); everything doubtful stays as printed and becomes a finding.

The metadata follows the contract `meta_contract.yaml` of the `parquet-meta-contract` project (5 groups: mechanical,
keys, semantics, provenance, inspect). For an agent: read `semantics.description`, `grain`, `caveats` and
`column_info` of a table, and its `inspect` findings, **before** querying it.

## Tables

| Table | Report table (PDF page) | Grain | Rows | Key | Joins |
|---|---|---|---|---|---|
| `wells` | derived | one hole id (incl. model-only and under-construction wells) | 172 | `pozo_id` | hub of the model |
| `well_aliases` | derived | pair of ids within 5 m | 9 | `pozo_a, pozo_b` | `wells` ×2 |
| `t10_1_rc_boreholes` | 10.1 (163) | RC hole PE-xx, 2009-2010 | 24 | `well_id` | `wells` |
| `t10_2_rc_brine_sample_counts` | 10.2 (164) | sample category (incl. totals) | 7 | `description` | - |
| `t10_3_rc_brine_chemistry` | 10.3 (165-166) | RC hole × depth interval (average) | 45 | `well_id, from_m, to_m` | `t10_1`, `wells` |
| `t10_4_ddh_boreholes_2009_2010` | 10.4 (167) | DDH hole | 29 | `well_id` | `wells` |
| `t10_5_ddh_brine_chemistry` | 10.5 (168) | DDH hole × depth interval (average) | 14 | `well_id, from_m, to_m` | `t10_4`, `wells` |
| `t10_6_piezometers` | 10.6 (170-171) | piezometer (N per borehole) | 49 | `borehole_id, piezometer_id, piezometer_name` | `wells` |
| `t10_7_piezometer_brine_chemistry` | 10.7 (174-176) | piezometer × depth interval (average) | 63 | `piezometer_id, from_m, to_m` | `t10_6`, `wells` |
| `t10_8_production_wells` | 10.8 (178-182) | production well | 38 | `pumping_well` | `wells` |
| `t10_8_production_well_intervals` | 10.8 (178-182) | production well × drilling interval | 111 | `pumping_well, interval_no` | `t10_8` |
| `t10_9_ddh_boreholes_2022_2024` | 10.9 (185) | DDH / rotary hole 2022-2024 | 8 | `borehole_id` | `wells` |
| `t11_1_pumping_test_sampling_frequency` | 11.1 (195) | time window of a pumping test | 8 | `time_interval` | - |
| `t11_2_geotechnical_analyses` | 11.2 (198) | geotechnical analysis | 7 | `analysis` | - |
| `t15_3_steady_state_residuals` | 15.3 (282-283) | monitoring point (observed vs model GW elevation) | 27 | `well_id` | `wells` via `pozo_id` |
| `tA1_1_exploration_well_locations` | App. 1 T1 (442-443) | well (XY, land-surface Z, screen) | 12 | `well_id` | `wells` via `pozo_id` |
| `tA2_4_production_well_model` | App. 2 T4 (446-447) | well of the reserve model (predictions) | 56 | `well_id` | `wells` via `pozo_id` |
| `t16_1_infill_wells_2024` | 16.1 (299) | infill well 2024 | 3 | `borehole_id` | `wells` via `pozo_id` |

Join model: `wells.pozo_id` is the canonical id of a physical hole and every table references it (declared
`foreign_keys`). Piezometers are N:1 on their borehole (`t10_6_piezometers.borehole_id`); the chemistry of
piezometers joins through `piezometer_id`. Tables that print a different spelling keep it (`well_id`, `id_raw`
columns) and carry the canonical `pozo_id` next to it.

## Coordinates (X, Y)

- CRS: **assumed** EPSG:22183 (Gauss-Krüger zone 3, POSGAR 94). No extracted table declares its CRS: zone 3 follows
  from the magnitude (easting ≈ 3.42e6, northing 7.34-7.41e6) and the Appendix 1 note mentions POSGAR 94; elsewhere the
  report also uses UTM 19S / WGS 84 (section 2.4). POSGAR 94 vs WGS 84 is sub-metre.
- `wells.lat/lon` (WGS 84, EPSG:4326, for maps such as the viewer's) are not in the report: they are reprojected from
  `easting/northing` with pyproj (EPSG:22183 → EPSG:4326). They inherit every caveat of easting/northing; NULL where
  easting is NULL.
- `wells.easting/northing` take the first source in the order 10.6, 10.8, 10.9, 15.3, App. 1, App. 2, 16.1;
  `fuentes_xy` lists all sources and `dispersion_xy_m` the largest disagreement. `xy_conflicto = true` (> 10 m) on
  8 holes where the report contradicts itself: W-04A (816 m), W-7 (1,293 m), W-4, WR-28, W-02B, W-31, WR-21 and
  RC17S-014. None was resolved.
- **Table 10.8 prints X and Y swapped in all rows**: use `easting/northing`, never `x_raw/y_raw`.
- **43 holes have no coordinates anywhere in the report** and stay NULL:
  - RC 2009-2010 (21 of 24): PE-01, 02, 03, 04, 05, 06, 07, 09, 10, 12, 13, 14, 14A, 16, 17, 17A, 18, 19, 20, 21, 22.
    Only PE-08, PE-11 and PE-15 have XY (Table 15.3).
  - DDH 2009-2010 (22 of 29): DDH-01, 03, 04, 06, 06A, 08, 08A, 09A, 10, 10A, 10B, 11, 12, 12A, 13, 13A-D, 14, 16, 18.
    Only DDH-02, 04A, 05, 07, 09, 15, 17 have XY (Table 15.3).
  - All 2017-2024 holes, piezometers and production wells have XY.
- DDH-17 sits ~13 km south of the southernmost other hole (DD19D-15) and ~20 km south of the next Table 15.3 point
  (PE-08); it is a flowing well, flagged in Table 15.3.

## Elevation (Z)

- The only collar elevation in the report is the land surface of **Appendix 1** (`wells.z_collar`, 11 wells: PB-01,
  PB-03A, PB-04, PB-06A, PB-I, W17-06, W18-05, W18-06, W-04A, W11-06, W18-23; CW-62 is "NA"). Per the Appendix 1 note,
  positions of wells built in 2010-2011 come from differential GPS and later ones from a DEM, so the Z precision differs.
- `z_collar` belongs to the Appendix 1 position. For **W-04A** `wells` takes XY from Table 10.8, 816 m away from the
  Appendix 1 point: its XY and Z are not from the same place (`xy_conflicto = true`).
- Appendix 2 `top_model_masl` is the top of the model cell, **not** the collar: it equals the Appendix 1 land surface
  for the W wells and differs by up to 0.56 m for the PB wells. Its `screen_top/bottom_masl` give screen elevations.
- Table 15.3 gives groundwater **elevation** (masl), not depth to water: 2018 levels (pre-development), mostly shallow
  wells, not corrected for brine density; the CAU* rows are third-party data (Adv. Lithium, 2018).
- No piezometer, RC or DDH hole with chemistry has a collar elevation. Depth of a sample can be turned into an
  elevation only where `z_collar` exists; otherwise it must stay NULL.
- Screen depths of 10.6/10.9 are **mbtw** (metres below top of well, i.e. top of casing); the depth reference of
  `total_depth_m` and of the chemistry intervals is not stated.

## Chemistry

Three tables, all **averages over depth intervals**, not individual samples:

| Table | Holes | Analytes (mg/L) | Notes |
|---|---|---|---|
| `t10_3_rc_brine_chemistry` | 14 RC holes (PE-04..PE-22), 45 intervals | B, K, Li, Mg, SO4, ratios | air-lift samples from the RC cyclone while drilling |
| `t10_5_ddh_brine_chemistry` | 6 DDH holes, 14 intervals | B, K, Li, Mg, SO4, Mg/Li | observation wells in DDH holes, low-flow pump then bailer (2010) |
| `t10_7_piezometer_brine_chemistry` | 18 piezometers / boreholes, 63 intervals | Li, K, Mg, **H3BO3**, SO4, Mg/Li | bailer profiles of the hole; intervals are **not** the piezometer screen |

- Boron: 10.3/10.5 give elemental B; 10.7 gives boric acid. **B = H3BO3 × 0.1748** before comparing.
- `mg_li_orig` is the printed ratio (integer in 10.3); `mg_li_recalc` = Mg/Li recomputed from the concentrations.
- Number formats were normalized per table: 10.3 comma thousands; **10.5 point as thousands** in K, Mg, SO4
  (4.847 = 4847); 10.9 decimal comma.
- `length_m` vs `to_m - from_m`: in 10.3 it is smaller in some rows (unsampled metres, lost circulation, text p.147);
  in 10.5 it differs in some rows in both directions and the report does not explain it; in 10.7 it is always equal.
- **Averaging**: every row is already an average over an interval of very different length (1 to 250 m). Weight by
  interval length (`to_m - from_m`) when averaging per hole. Do not pool the three tables blindly: they differ in
  campaign (2009-2010 vs 2017-2019), sampling method and lab.
- Rows that sit in the wrong hole: the three "PE-14" intervals of 10.3 fit PE-14A, and the deep DDH-06 intervals of 10.5
  fit DDH-06A (`data_error`). The `DD19D-001` rows of 10.7 continue the DL-001 profile but belong to another borehole,
  so a GROUP BY borehole splits that profile.
- Labs: ASA (ICP, gravimetric SO4) or the internal, uncertified Exar lab (AA, titration). **No row says which lab**
  analysed it; brine QA/QC is in section 12 (not audited here).
- Chemistry with coordinates: all 18 piezometer boreholes; only PE-15 among the RC holes; none of the DDH holes.
- The 2022-2024 program (Table 10.9) is in Cauchari Sur, outside the certified resource area, and its rotary wells were
  not sampled for chemistry.

## Edits applied (`_edits.csv`, 55 rows)

- **Ids**: DDH-n → DDH-nn; piezometers zero-padded and without spaces (`DL-08` → `DL-008`, `DL-003 B` → `DL-003B`,
  `RC17S-13` → `RC17S-013`); canonical `pozo_id` added to 15.3, App. 1, App. 2 and 16.1 (`PB-3A` → `PB-03A`,
  `W04-A` → `W-04A`, `WR-3` → `WR-03`, `SL-xxx` → its borehole, `Pozo 44` → `POZO-44`).
- **X/Y swapped** in Table 10.8 (all 38 rows): `easting/northing` were assigned at extraction; the cleaning adds the `xy_swapped` flag.
- **One value corrected**: W-16 easting 3227420 → 3427420, as printed in Appendix 2 Table 4 with the same northing (its `nota` is updated too).
- **Columns**: 10.7 first column renamed `piezometer_name` (the source header says "DD Borehole ID" but holds
  piezometers); 10.6 derived `collar_id` dropped; "Cemented" / "Abandoned" moved from the piezometer column to `status`.
- **Added**: `borehole_id`, `piezometer_id`, `status`, `xy_swapped`, `pozo_id` (`mg_li_recalc` comes from the extraction).

## Findings

55 findings in 14 tables, **10 `data_error`**. Full text in `data_processed/inspect/` and in the appendix below.

`data_error` (can change a number):
1. `t10_3`: the 3 intervals labelled PE-14 (147-228 m) are below PE-14's 144 m depth; they fit its twin PE-14A
   (144-228 m).
2. `t10_5`: DDH-06 intervals 118-136 and 140-190 m are below DDH-06's 129 m depth; they fit DDH-06A (338.5 m), or
   10.4 swapped 6 and 6A.
3. `t10_6`: site 014 breaks the text's layout (SL and ML share a borehole, the deep hole is 15 m away): SL-014 has
   DL-014's exact XY while ML-014 is 21 m away.
4. `t10_6`: screen diameters contradict the text (SL should be 1", ML/DL 2"-2.5"): SL-009, SL-010 (2"), SL-004B
   (2.5"), DL-012 (3").
5. `t10_8`: the text says 43 production wells were drilled since 2011; the table details 38.
6. `t10_8`: `total_depth_m` of PB-03A, PB-04 and PB-06A looks shifted one row (Appendix 1 and the last drilling
   interval give 201, 305, 194 m): a depth query for PB-04 or PB-06A is off by ~105 m.
7. `t10_8`: W-7 prints exactly W-10's coordinates; Appendix 2 puts W-7 about 1.3 km away (prefer Appendix 2).
8. `t10_9`: the text says 3 HQ diamond holes to 600 m; the table has 2 DDH (415 and 88 m).
9. `tA2_4`: the Appendix 2 model screen of PB-04 disagrees with Appendix 1 and its bottom lies below the well's
   total depth; prefer Appendix 1 for PB-04 screen elevations.
10. `t10_9`: the text says the 6 rotary wells reached 700 m; the table gives 465-706.8 m, and DD19D-13 prints a screen
   base (537 m) below its total depth (465 m).

Main `note`s:
- **Figure 10.2 platforms (hypothesis, not applied)**: each 2017 drill platform groups the DL/ML/SL piezometers of one
  number and, on some, a production well (01 W-01, 04 W-02, 07 W-05, 08-15 W-07, 03-13-14 W17-06). Coordinates confirm
  it for W17-06 (21-32 m) and for W-02B per Appendix 2 (0-9 m; Table 10.8 puts it 149 m away), and contradict it for
  W-1, W-5, W-7 (3.7-24 km). The figure also groups PE-20 / DDH-10, 10B with PB-01, PE-21 with PB-03A, DDH-12, 12A
  with PB-04 and PE-18 with PB-02. No coordinate was assigned from it.
- Twins (PE-14/14A, DDH-06/06A) are separate holes of one site and are not in `well_aliases`.
- **Counting production wells**: section 10.8 says 43 drilled since 2011 and section 16.3 says 39 brine extraction wells
  were built 2018-2024; Table 10.8 details 38. `programa LIKE 'PRODUCCION%'` gives 41 (38 + 3 infill wells under
  construction). `MODELO_APENDICE_2` (reserve-model table only) and `APENDICE_1` holes are not confirmed production wells.
- Sample counts of Table 10.2 cover only 2009-2010 and include PE-03, excluded from 10.3 (flowing artesian, fresh water).
- Undisturbed core counts disagree inside the report (832 tested vs 1,244 collected and 865 RBRC).

## Not in this dataset

- Tables 9.2, 9.4, 12.1, 12.2, 12.5, 14.2, 14.3, 15.5, 16.2 (pumped volume per well and year), Appendix 1 Table 2
  (hydraulic test results per well), Appendix 1 Table 3 (Sy), 4.1 (mineral claims) and 4.3/4.4 (permits) were not
  extracted.
- Section 12 (brine QA/QC) was not audited.
- Figures were not digitized or georeferenced. Figures of interest, with PDF page: 10.2 borehole locations and drilling
  platforms (173), 10.4 pumping wells location (183), 10.5-10.12 lithological profiles of DD19D-05, 06, 07, 08, 11,
  13, 15, 26 BIS (186-189), 10.13 2022-2024 drill hole locations (190), 14.3 well location map (239), 14.9-14.13
  hydrostratigraphic sections (249-253), 14.14-14.16 lithium fence sections (257-259), 15.7 simulated production
  wellfield (289).

## Appendix: all findings

Generated from `data_processed/inspect/*.yaml` by `scripts/dataset_appendix.py`.

### `t10_1_rc_boreholes` (observed rows: 24)

- **note** [well_id, to_m, length_m]: Text p.147/PDF 163 confirms the table: "Twenty-four RC boreholes (PE-01 through PE-22, plus two twin holes) ... total drilling of 4,176 m. Borehole depths range from 28 m (PE-01) to 371 m (PE-10)". The text's "depth" is to_m, not length_m: for PE-07 (78.9-249) and PE-14A (144-228) length_m is metres drilled, not hole depth. Use to_m for depth questions and SUM(length_m) only for metres drilled.
- **note** [well_id, from_m, to_m]: PE-14A is the twin of PE-14 and was drilled from 144 m (the bottom of PE-14) to 228 m, i.e. it is the deepening of the same site. The Table 10.3 chemistry printed under "PE-14" (147-179, 179-192, 192-228 m) lies entirely below PE-14's 144 m and inside PE-14A's 144-228 m (see the t10_3_rc_brine_chemistry sidecar). Joining chemistry to this table by well_id attaches those intervals to the wrong hole.
- **note** [well_id]: Text p.147-148/PDF 163-164: 1,487 brine samples were collected from 15 of the 24 RC holes; Table 10.3 shows 14 of them because PE-3 (PE-03) "a flowing artesian well" receiving freshwater from the alluvial cone on the eastern margin of the Olaroz salar was left out. So 9 holes have no brine chemistry: PE-01, 02, 05, 08, 11, 12, 16, 17A and one of PE-14/PE-14A. Brine and chip samples were taken from the cyclone at one-metre intervals; field K (portable XRF, irregular), EC, pH and temperature were measured but are in no table. Air-lift flows (6 holes) and daily static water levels measured inside the drill string are not tabulated either. No drilling additives were used (ODEX / open-hole RC, then tri-cone bits), Major Drilling with a Schramm T685W rig.

### `t10_2_rc_brine_sample_counts` (observed rows: 7)

- **note** [description, brine_samples]: Text p.147/PDF 163: the 1,487 RC field samples come from 15 RC holes, but only 14 holes have chemistry in Table 10.3 (PE-03 excluded, flowing artesian with freshwater, text p.148/PDF 164). The count therefore includes samples with no row in t10_3_rc_brine_chemistry. Also, SUM(length_m) of Table 10.3 is 1,643 m, more than the 1,487 samples, so the averaged intervals are not "one sample per metre". Do not derive sample counts from interval lengths or the other way round.
- **note** [description, brine_samples]: The QC rows (260 field duplicates, 263 blanks, 253 standards; 2,390 incl. QC) cover only the 2009-2010 RC + DDH programs. Sections 10-11 give no sample or QC counts for the 2017-2019 piezometer program (Table 10.7) or the pumping tests. Section 11.5 (text p.178/PDF 194) says brine QA/QC is covered in Section 12, which was not audited here. Duplicates are about 16% of field samples.

### `t10_3_rc_brine_chemistry` (observed rows: 45)

- **data_error** [well_id, from_m, to_m]: The 3 rows labelled PE-14 (147-179, 179-192, 192-228 m; label checked on the image of PDF 165) lie below the total depth of PE-14, which is 144 m in Table 10.1 (text p.147/PDF 163). They fall exactly inside the twin hole PE-14A, drilled 144-228 m. They are almost certainly PE-14A chemistry printed under the PE-14 label. A query by well_id (e.g. "chemistry of PE-14A" or "deepest sample of PE-14") returns the wrong hole. The rows were kept as printed.
- **note** [length_m, from_m, to_m]: Text p.147/PDF 163: "chip and brine samples are collected from the cyclone at one-metre intervals. Occasionally, lost circulation resulted in the inability to collect samples from some intervals." This backs the caveat that length_m < to_m - from_m means unsampled gaps. But SUM(length_m) = 1,643 m against the 1,487 RC samples of Table 10.2 (from 15 holes, PE-03 included). So length_m is not a count of 1 m samples. Treat it as a printed length, not as a weight in sample counts.
- **note** [b_mg_l, k_mg_l, li_mg_l, mg_mg_l, so4_mg_l]: Sampling and lab context (sections 10.1 and 11). The brines are air-lift samples from the RC cyclone taken while drilling, not depth-isolated pumped samples; no drilling additives were used. Per section 11.5-11.6.1 (text p.178-180/PDF 194-196), brine samples went to two labs. Alex Stewart Argentina (ASA, ISO 9001/14001) used ICP after 100:1 dilution for Na, K, Li, Ca, Mg and B, and gravimetry for SO4. The internal Exar lab (not certified) used AA for Li, Na and K, titration for Ca, Mg and Cl, and gravimetry for SO4. The table does not say which lab produced which interval, and the 2009-2010 procedures are deferred to the 2017 Feasibility Study. QA/QC is deferred to Section 12. Field K by portable XRF is not in this table.
- **note** [well_id]: Text p.148/PDF 164: averages cover "14 of the 15 sampled RC boreholes". PE-3 (PE-03) was sampled but excluded because it is a flowing artesian well that receives freshwater from the alluvial cone on the eastern margin of the Olaroz salar. An absent PE-03 here means excluded, not unsampled.
- **note** [well_id]: Figure 10.2 'Borehole Locations and Associated Drilling Platforms' (p.157/PDF 173; raster map, labels read visually) groups some RC holes with PB pumping wells in one map label: PE-21 with PB-03A ('PB-03,A / PP-03B,C / PP-B-PB3 / PE-21 / PF-03A,B'), PE-20 with PB-01 ('DDH-10,B / PP-01A,B,C / PF-01A,B / PB-01 / PE-20'), PE-18 with PB-02 ('PE-18 / PP-PB2 / PB-02,A / PP-02A'). PB-01 and PB-03A have XY and Z in Appendix 1; PB-02 is in no extracted table. Hypothesis only: these PE may share the PB location. No coordinate was assigned - easting/northing of PE-18/20/21 stay NULL in `wells`.
- **note** [well_id, mg_mg_l, mg_li_orig]: PE-10 interval 60-152 m prints Mg = 174 mg/L with Mg/Li = 0, far below every other interval (Mg in the thousands). Kept as printed and flagged in `nota`: likely a source typo, not confirmed by any other table.
- **note** [well_id, from_m, to_m]: The first 5 rows of PDF p.166 carry no borehole label in the source (the table continues from p.165, where the last label is PE-17). They were assigned to PE-17 by continuation, since the next label is PE-18.

### `t10_4_ddh_boreholes_2009_2010` (observed rows: 29)

- **note** [to_m, well_id]: Text p.151/PDF 167: "Borehole depths range from 79 m (DDH-2) to 449.5 m (DDH-7)". The table (checked on the page image) has shallower holes: DDH-13A, 13B, 13C and 13D at 20.5 m and DDH-10B at 36.8 m. The text range is wrong, or it ignores the short twins. csv/raw/EXTRACTION_NOTES.md (batch 10.1/10.2/10.4) says the range "coincide con el texto", which is not correct. MIN(to_m) = 20.5 is right for the data; do not quote 79 m as the minimum.
- **note** [well_id]: Text p.151: "Twenty-nine boreholes (DDH-1 through DDH-18, plus twin holes)": 18 main holes + 11 twins (4A, 6A, 8A, 9A, 10A, 10B, 12A, 13A-D) = 29, which matches the rows. Twins are separate holes at the same site. DDH-06 is 129 m deep while its twin DDH-06A is 338.5 m. Table 10.5 prints DDH-06 chemistry down to 190 m (see the t10_5_ddh_brine_chemistry sidecar), so that chemistry probably comes from DDH-06A. Major Drilling, Major-50 rig, triple-tube PQ/HQ core.
- **note** [well_id]: The undisturbed core sample counts in the text disagree. Text p.151/PDF 167 says "A total of 832 undisturbed samples were tested". Section 11.3 (text p.176/PDF 192) says 1,244 undisturbed samples were collected from DDH-1 through DDH-18, with RBRC on 865, particle size on 58 and dry bulk density on 36. 865 RBRC is more than 832 tested. Neither figure is in any table.

### `t10_5_ddh_brine_chemistry` (observed rows: 14)

- **data_error** [well_id, from_m, to_m]: DDH-06 intervals 118-136 and 140-190 m go below DDH-06's total depth of 129 m in Table 10.4 (text p.151/PDF 167, checked on the page image). The twin DDH-06A is 338.5 m deep. These rows (and maybe 100-115) probably belong to DDH-06A, or Table 10.4 swapped the depths of DDH-6/DDH-6A (it lists 6A before 6). Either way a join to t10_4 by well_id gives sample depths below the hole bottom. The rows were kept as printed.
- **note** [length_m, from_m, to_m]: Text p.152/PDF 168: the brine came from observation wells built in selected DD holes (Schedule 80 2-inch PVC with 1 mm slotted screen), sampled March-August 2010. Samples were "initially collected with a low-flow pump. However, later samples were collected with a bailer". The method changes within the table and is not identified per row. Unlike Table 10.3, nothing in the text explains why length_m differs from to_m - from_m. The 2 rows with length_m > to_m - from_m (DDH-01 70-105, DDH-06 140-190) stay unexplained. Table 10.2 gives 127 DDH field samples for these 14 intervals.
- **note** [b_mg_l, k_mg_l, li_mg_l, mg_mg_l, so4_mg_l]: Labs and methods are the same as for Table 10.3 (section 11.6.1, text p.180/PDF 196): ASA (ICP for K, Li, Mg, B; gravimetric SO4) or the uncertified internal Exar lab (AA for Li and K, titration for Mg). Which lab produced which row is not stated. QA/QC is in Section 12 (not audited).
- **note** [well_id]: Figure 10.2 'Borehole Locations and Associated Drilling Platforms' (p.157/PDF 173; raster map, labels read visually): the label 'PLATFORM PB-04' lists PB04, PP-04A,B and DDH-12,A. PB-04 has XY (Table 10.8, Appendix 1) and Z (Appendix 1). Hypothesis only: DDH-12 (chemistry in this table) may share the PB-04 location. Not applied: DDH-12 has no coordinates in `wells`.
- **note** [well_id, mg_mg_l]: DDH-12 interval 65-70 m prints Mg as '927' with no thousands separator, while the rest of the column uses a point as thousands separator (e.g. 4.847). It was read as 927 mg/L by magnitude; it may be a truncated value.

### `t10_6_piezometers` (observed rows: 49)

- **data_error** [x_coordinate_m, y_coordinate_m, borehole_id, piezometer_id]: Text p.152/PDF 168: "Shallow and intermediate depth boreholes were completed in the same borehole ... The deeper borehole was drilled 15 m away from the shallow and intermediate well locations". The 14th site breaks both rules (values checked on the image of PDF 171). SL-014 (RC17S-014) has the exact coordinates of DL-014 (DD17D-014), 3426361/7387640, which is 0 m from the deep hole. ML-014, in the same borehole RC17S-014, sits 21 m away at 3426381/7387647. ML-014 is the one that fits the 15 m rule. So SL-014's XY, which Table 15.3 repeats, or DL-014's XY is probably a copy error. The text points to SL-014 and/or DL-014 as suspect, not ML-014.
- **note** [x_coordinate_m, y_coordinate_m, piezometer_id]: The "15 m away" of the text (p.152) is nominal. The measured deep-to-shallow offsets per site are 8.6 (002), 14-15 (003), 8.6-19.2 (004), 69.3 (005), 25.8 (006), 12.7 (007), 19.0 (008), 18.4 (009), 19.2 (010), 20.6 (011), 12.2 (012), 13.0 (013), 16.6 (001) and 0 (014, see the finding above). Site 005 (DL-005 vs ML-005, 69 m) is far off the stated design and worth checking.
- **data_error** [screen_diameter_in, piezometer_id]: Text p.152/PDF 168: "The shallowest wells use 1" diameter PVC casing ... The intermediate and deep wells were cased using Schedule 80, 2-inch or 2.5-inch diameter, PVC casing". The table (checked on the image) contradicts it for SL-009 (2"), SL-010 (2"), SL-004B (2.5") and DL-012 (3"). A filter such as "1-inch shallow piezometers" or "diameter IN (2, 2.5)" gives a different set depending on whether you trust the text or the table.
- **note** [total_depth_m, piezometer_id]: Text p.152: the 2017-2019 programs drilled "50 m, 200 m and 450 to 600 m deep" wells per platform (SL / ML / DL). These are nominal depths. The table has SL-014 at 26.7 m (screen base = total depth). ML-008 is 160, ML-002 189.1 and ML-005 192. DL-003 and DL-004 are 650, DL-003B 648, DL-005 604.55, DL-014 431.35 and DL-008 447. The DD18D holes are 300 m (DD18D-003 13 m, abandoned) and DD19D-001 is 632 m. Use total_depth_m, not the SL/ML/DL class, for depth.
- **note** [platform_raw]: Meaning of "Plataform": text p.152-153/PDF 168-169 says the programs drilled the 50/200/450-600 m wells "from the same drilling platform". Figure 10.2 is "Borehole Locations and Associated Drilling Platforms". So platform_raw is the drill-pad number(s) of Figure 10.2 grouping SL/ML/DL of one site. Multi-values such as "3 13 14" are pad numbers as drawn there. The figure is a map, not extracted, and the text does not explain the multiple numbers. The DD18D codes (CN-10, CN-14, CN-19, CN-02, CS-28, CS-31, P-17) follow another scheme; several of those holes share XY with production wells (well_aliases). "PE-09" for DD19D-PE09 means it was drilled on the pad of RC hole PE-09.
- **note** [contractor, borehole_id]: Text p.153/PDF 169 names only Major Drilling and Ideal Drilling for this program, and section 11.3 (p.176/PDF 192) says diamond drilling was by Major Drilling and Ideal Drilling. Section 11.2 (p.175/PDF 191) names Hidrotec (with Wichi Toledo) as the ROTARY contractor for pumping wells. DD19D-001 and DD19D-PE09 list Hidrotec, which the text does not account for. Text p.153 also says deep holes were HQ triple-tube cored and shallow/medium holes rotary tricone 5 7/8". RC17D-003 (DL-003B) and RC17D-004B (DL-004B) are deep holes with an RC prefix, so their drilling method is unclear.
- **note** [screen_top_mbtw, screen_base_mbtw, total_depth_m]: Table note p.155/PDF 171: "mbtw = metres below top of well", i.e. measured from the top of casing, not ground level. total_depth_m and the Table 10.7 interval depths have no stated reference, and no stick-up is given. Expect offsets of the order of the casing stick-up when comparing screen depths with total depth or chemistry depths. 33 RBRC samples were taken from DD19D-PE09 in 2019 (text p.175 and p.181), the only geotechnical data for this program. RBRC was not measured in 2017-2018.
- **note** [platform_raw, piezometer_id, borehole_id]: Figure 10.2 'Borehole Locations and Associated Drilling Platforms' (p.157/PDF 173; raster map, labels read visually) labels each 2017 platform with its piezometers and, on some, a production well: 01 = DL-001, ML-001, SL-001, W-01; 02 = DL-004B, ML-004, SL-004,B; 04 = DL-002B, ML-002, SL-002, W-02; 05 = DL-010, ML-010B, SL-010; 06 = DL-008, ML-008; 07 = DL-005, ML-005, W-05; 08-15 = DL-007, ML-007, SL-007, W-07; 09 = DL-003 B, ML-003; 10 = DL-012, ML-012; 11-12 = DL/ML/SL-009; 16 = DL-011, ML-011; 17-20 = DL/ML/SL-014; 18 = DL/ML/SL-013; 03-13-14 = DL-006B, ML-006, SL-006, W17-06. The numbers match platform_raw. Piezometers with the same number are co-located (SL/ML same XY, DL 8.6-69 m away). Hypothesis, NOT applied to any value: the W listed on a platform shares the pad with those piezometers (see t10_8_production_wells inspect for the coordinate check).

### `t10_7_piezometer_brine_chemistry` (observed rows: 63)

- **note** [h3bo3_mg_l]: Boron is reported as boric acid (H3BO3), whereas Tables 10.3 and 10.5 report elemental B. Section 11.6.1 (text p.180/PDF 196) lists boron among the ICP elements at ASA; the internal Exar lab method list has no boron. To compare with b_mg_l of t10_3/t10_5, convert B = H3BO3 x 10.81/61.83 (x 0.1748). Here that gives B of about 431-2,058 mg/L, against 655-1,398 (10.3) and 610-872 (10.5). Comparing h3bo3_mg_l with b_mg_l directly overstates boron by a factor of 5.7.
- **note** [from_m, to_m, piezometer_name, borehole_id]: The intervals are not the piezometer screen. Every DL series starts at 0 m, while the DL screens in Table 10.6 start at 197-343 m. DL-011 (0-200) and DL-013 (0-260) lie entirely above their screens (235.8-444 and 279.18-443). DD19D-001 (450-632) has no piezometer or screen at all. Text p.152/PDF 168 lists "brine samples using a bailer" among the drilling objectives, and section 11.5.1 (p.178/PDF 194) describes bailer samples "at 20 m intervals". These are borehole depth profiles (likely sampled during drilling) averaged over 15-250 m. Do not read them as the brine that the named piezometer's screen produces, and do not join them to 10.6 screens to infer "screen chemistry".
- **note** [li_mg_l, k_mg_l, mg_mg_l, h3bo3_mg_l, so4_mg_l]: Lab and method are not identified per row (section 11.5/11.6.1, text p.178-180). The 2017-2019 brine went to ASA in Jujuy (ICP after 100:1 dilution; gravimetric SO4) or to the internal Exar lab (AA for Li and K; titration for Mg; gravimetric SO4). The Exar lab "is not a certified laboratory"; the text says "The Company" was ISO 9001 certified in 2023, expired in 2024 (p.181). Samples were not filtered (p.178). Mg by titration and Mg by ICP can differ, so treat Mg/Li comparisons across rows and tables with care. No QC counts are given for this program in sections 10-11 (QA/QC deferred to Section 12, not audited).
- **note** [piezometer_id, mg_mg_l, li_mg_l]: DL-001 intervals 300-400 and 400-450 m repeat exactly the same Mg (1230.1 mg/L) with different Li: possible copy error in the source. Kept as printed.

### `t10_8_production_wells` (observed rows: 38)

- **data_error** [pumping_well, year]: Text p.161/PDF 177: "Since 2011, a total of 43 production wells have been drilled on the Property". The table has 38 wells (2011-2023), so COUNT(*) here is not the number of production wells drilled: 5 wells are not detailed anywhere in Table 10.8. Table 16.1 numbers the 2024 infill wells "Pozo 44-46", which fits 43 earlier wells. The text does not name the missing 5. Candidates outside 10.8 are the Appendix 2 Table 4 W-ids (W-20..W-30, W-32, W-3, W09-01, W17-12, WR-24, R64/R66/R67), but that is a reserve-model list, not a list of drilled wells.
- **data_error** [pumping_well, total_depth_m]: total_depth_m of the three 2011 PB wells looks shifted one row: this table prints PB-03A 204, PB-04 201, PB-06A 305 m (PDF 178), while Appendix 1 Table 1 (PDF 442) gives PB-03A 201, PB-04 305, PB-06A 194 m (and PB-01 204), and the last drilling interval of this same table ends at 205, 305 and 194 m. A depth query for PB-04 or PB-06A is off by ~105 m; prefer Appendix 1 (tA1_1_exploration_well_locations) or the last interval in t10_8_production_well_intervals. Other wells whose last drilling interval disagrees with total_depth_m (e.g. W-14: 607.7 vs 494 m; WR-10: 355 vs 445 m) are not resolved by any other table.
- **note** [pumping_well, year, total_length_casing_inserted_m, total_length_screen_casing_inserted_m]: Text p.161: "The production well field uses three wells drilled in 2011, these wells had a smaller diameter (8 inches)". This matches PB-03A, PB-04 and PB-06A (2011, 8" casing). The 2018/2019 and later wells are deeper and telescopic, with larger casing in "the upper 200/250 m" and smaller below. Appendix 1 lists PB-01 (2010) and PB-I (2011, 51 m), which are not production wells of this table.
- **note** [screen_casing]: Text p.161: "The production wells use stainless steel screen". The three 2011 PB wells print Galvanized Steel, so the text's generalisation is wrong for them and the table value is the one to use.
- **note** [total_length_screen_casing_inserted_m, total_length_casing_inserted_m]: Text p.161: screen sections are "inserted facing the productive horizons" with a minimum length of two metres, solid casing faces halite/clay layers, and "the solid and screen casing alternate through the aquifer". The screen length per diameter is therefore a SUM of several sections, not a continuous interval. Do not derive screen top/bottom depths from it (Appendix 2 Table 4 gives screen top/bottom in masl for the model).
- **note** [pumping_well, easting, northing]: Coordinate check of the platform grouping of Figure 10.2 'Borehole Locations and Associated Drilling Platforms' (p.157/PDF 173; raster map, labels read visually), nothing changed: W17-06 is 21-32 m from DL-006B/ML-006 (platform 03-13-14) in every source. Appendix 2 puts W-02B 0-9 m from DL-002B/ML-002 (platform 04, labelled W-02) while this table puts it 149 m away - evidence for the Appendix 2 position of W-02B. W-1, W-5 and W-7 (this table and Appendix 2) are 3.7, 6.7 and 23-24 km from platforms 01, 07 and 08-15, where the figure labels W-01, W-05, W-07: either different wells with similar names or wrong coordinates, unresolved. 0 m coincidences that agree with the figure: W18-05 = DD18D-005 (platform CS-28), W18-06 = DD18D-006 (platform CS-31); also W-30 = DD17D-003, W17-12 = DD17D-012, W-13 = DD18D-004 (not labelled together in the figure).
- **data_error** [pumping_well, easting, northing]: W-7 and W-10 print identical coordinates in this table. Appendix 2 Table 4 places W-7 about 1.3 km away from that point, so the W-7 row most likely repeats W-10's coordinates. `wells` keeps this table's value for W-7 (xy_conflicto = true); prefer Appendix 2 for W-7.

### `t10_9_ddh_boreholes_2022_2024` (observed rows: 8)

- **data_error** [borehole_id, type, total_depth_m]: Text p.168/PDF 184: "three HQ diameter diamond drill holes were advanced, to a maximum depth of 600 m". The table has only 2 rows of type DDH: DD19D-05 (415 m) and DD19D-06 (88 m). Neither comes near 600 m. One diamond hole of this program is missing from the table (no id in the text), so COUNT of DDH here gives 2 instead of 3.
- **data_error** [total_depth_m, screen_base_mbtw, borehole_id]: Text p.168: "6 wells were drilled with the construction characteristics of production wells. These wells reached a depth of 700 m, are cased in 12" for the first 250 m and then in 8" at the bottom." The count of 6 Rotary rows matches, but their depths are 465-706.8 m and only DD19D-11 is about 700 m. For DD19D-13, screen_base 537 > total_depth 465 (already in nota). The text's ~700 m suggests the printed total depth, not the screen base, is the wrong value (inference). Treat MAX/AVG(total_depth_m) of the rotary wells with care.
- **note** [screen_diameter_inches, type]: For the Rotary rows, "8", 12"" is the two casing sizes of the telescopic design (12" to 250 m, 8" below; text p.168), not one screen diameter. The screen tops (66-96 m) sit in the 12" section. These wells carry DD19D-ids although they are pumping-test wells, not diamond holes.
- **note** [contractor, type]: Section 11.2 (text p.175/PDF 191): rotary drilling for pumping wells was by Hidrotec and Wichi Toledo, and "samples were not taken during rotary drilling for chemical analysis". At the report date pumping tests on these 6 wells were "currently being carried out" (p.168). So there is no chemistry for them in any table. The DDH contractor Conosur is not mentioned in section 11.3, which names only Major Drilling and Ideal Drilling for diamond drilling.
- **note** [screen_top_mbtw, screen_base_mbtw]: csv/raw/EXTRACTION_NOTES.md left "mbtw" uninterpreted for this table. Its definition is in the note of Table 10.6 (p.155/PDF 171): "mbtw = metres below top of well", measured from the top of casing, not ground.

### `t11_1_pumping_test_sampling_frequency` (observed rows: 8)

- **note** [sampling_frequency, time_interval]: Despite the header "Frequency of Sampling", the text (p.179-180/PDF 195-196) applies this schedule to the MEASUREMENTS of dynamic water level, flow (m3/h) and turbidity, during development and the constant-rate test, and to the recovery readings (water-level tape) until 95% recovery. It does not apply to brine samples. Brine in the constant-rate test is sampled at 10 min, 30 min, 60 min and 2 h, then every 4 hours to the end. time_interval is elapsed time since the pumping (or recovery) began.
- **note** [time_interval]: Test sequence per text p.179-180: development for 3-7 days (until solids < 0.1 ml in an Imhoff cone), then a short 2-4 h test for the maximum rate, then an 8-12 h step test at 25/50/75/100% of the maximum, then a constant-rate test of at least 7 days. Nearby wells' drawdown and recovery are also measured. This applies to the 2017-2019 pumping test program.

### `t11_2_geotechnical_analyses` (observed rows: 7)

- **note** [analysis, procedure]: Scope per sections 11.3 and 11.8.1 (text p.176 and p.181): these procedures were run by D.B. Stephens & Associates (Albuquerque, USA) on undisturbed core from DDH-1 through DDH-18 (2009-2011). The text gives counts: 1,244 undisturbed samples collected, RBRC on 865, particle size on 58, dry bulk density on 36. Text p.151 instead says "832 undisturbed samples were tested", fewer than the 865 RBRC. There were also 33 RBRC samples from DD19D-PE09 in 2019, lab not stated. No results are tabulated.
- **note** [analysis]: Text p.182-183/PDF 198-199: dry bulk density, moisture content and total porosity "are not used in the Mineral Resource and Reserve Estimates". Specific gravity was measured on only 4 samples (2.47-2.75 g/cm3), judged skewed by salt, and an assumed particle density of 2.65 g/cm3 was used for all others. RBRC (suction 0.2-0.3 bar for 18-24 h, oven at 110 C) is the specific yield input. Particle size results were classified by USDA. The on-site Exar porosity lab (total porosity by gas pycnometer) is not in this table, was not used for estimates and was no longer operational in 2024.

### `t15_3_steady_state_residuals` (observed rows: 27)

- **note** [well_id, northing_m, observed_gw_elev_masl]: DDH-17 has northing 7343262, about 13 km south of the southernmost other hole of the dataset (DD19D-15) and 20 km south of the next Table 15.3 point (PE-08), and its observed level is above the others. Footnote *: reported as flowing well; the model uses a censoring target. Kept and flagged.

### `tA2_4_production_well_model` (observed rows: 56)

- **data_error** [pozo_id, screen_top_masl, screen_bottom_masl]: PB-04: the model screen (3902.67 to 3589.13 masl) does not match Appendix 1, whose land surface and screen depths give 3887.67 to 3649.67 masl. The model screen bottom sits about 358 m below top_model_masl, deeper than the 305 m total depth of the well. For the other wells shared with Appendix 1 the two agree within a few metres (PB-03A bottom differs by about 6.6 m). Prefer Appendix 1 for PB-04 screen elevations.

### `wells` (observed rows: 172)

- **note** [programa, pozo_id]: Text p.161/PDF 177 says 43 production wells were drilled since 2011; Table 10.8 details 38 (programa = PRODUCCION_10_8) and the 5 others are not identified in the report (the Pozo 44-46 numbering of Table 16.1 fits 43). programa = MODELO_APENDICE_2 holds wells that appear only in the Appendix 2 reserve-model table; whether they exist physically is not stated.
- **note** [easting, northing, xy_conflicto]: RC17S-014 / DD17D-014. Text p.152 says shallow and intermediate piezometers share one borehole and the deep hole is 15 m away. In 10.6, SL-014 (and Table 15.3) has exactly DL-014's XY (0 m apart), while ML-014 is 21 m away. The registry takes ML-014's XY for RC17S-014, which is the option that fits the text. DD17D-014's XY (copied from 10.6) may be the duplicated one; it is flagged xy_conflicto = false even though it is identical to SL-014's.
- **note** [pozo_id]: Twin pairs at the same site are not in well_aliases: PE-14/PE-14A (PE-14A drilled 144-228 m below PE-14's 144 m; Table 10.1) and DDH-06/DDH-06A. Each pair's chemistry appears under the shallow twin's id while its depths only fit the deep twin (t10_3, t10_5 sidecars). The other twins (DDH-04A, 08A, 09A, 10A, 10B, 12A, 13A-D, PE-17A) have no such conflict in the audited tables. DD19D-PE09 was drilled on platform "PE-09" (Table 10.6), so its XY (3419473/7374367) is a hint of PE-09's location, which has no coordinates. This is an inference only and was not filled in.
- **note** [pozo_id]: Holes or wells mentioned in sections 10-11 and absent from every table: one of the "three HQ diameter diamond drill holes" of the 2022-2024 southern program (p.168; only DD19D-05/06 are DDH in Table 10.9), and 5 of the 43 production wells (p.161). Neither has an id in the text. Spelling variants in the text map to existing ids: "PE-3" = PE-03 (p.148), "DDH19D-001" = DD19D-001 (p.153), "DD19D_PE09" = DD19D-PE09 (p.181), "DDH-1 through DDH18" = DDH-01..DDH-18 (p.176).
- **note** [pozo_id, easting, northing]: The RC (PE) and DDH 2009-2010 holes without coordinates appear only as dots on Figure 10.2 'Borehole Locations and Associated Drilling Platforms' (p.157/PDF 173; raster map, labels read visually); no table gives their XY. The figure's grouped labels suggest PE-20, DDH-10 and DDH-10B with PB-01; PE-21 with PB-03A; DDH-12 and DDH-12A with PB-04; PE-18 with PB-02 (PB-02 has no XY anywhere). NOT applied: their easting/northing stay NULL. Georeferencing the figure was out of scope.
