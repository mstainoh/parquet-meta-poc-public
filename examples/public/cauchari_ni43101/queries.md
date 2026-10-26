# Example queries

Natural-language prompts and their SQL translation over the public Cauchari-Olaroz NI 43-101
dataset (`DATASET.md`). Each parquet of `data_processed/parquet/` is registered by the viewer
as a view named after its file stem (`wells`, `t10_7_piezometer_brine_chemistry`, ...), so the
SQL uses those names as they are. Every query was run with DuckDB over the parquet files; the
notes say which caveat or finding of the metadata it respects.

---

## 1. Chemistry — boron and lithium per campaign, on the same basis

**Prompt:** "Compare boron and lithium between the three brine chemistry tables"

```sql
WITH chem AS (
    SELECT '10.3 RC 2009-2010' AS source_table, well_id AS hole_id,
           to_m - from_m AS len_m, li_mg_l, b_mg_l
    FROM t10_3_rc_brine_chemistry
    UNION ALL
    SELECT '10.5 DDH 2010', well_id, to_m - from_m, li_mg_l, b_mg_l
    FROM t10_5_ddh_brine_chemistry
    UNION ALL
    SELECT '10.7 piezometers 2017-2019', borehole_id, to_m - from_m, li_mg_l,
           h3bo3_mg_l * 0.1748                      -- boric acid -> elemental B
    FROM t10_7_piezometer_brine_chemistry
)
SELECT source_table,
       COUNT(DISTINCT hole_id)                               AS n_holes,
       COUNT(*)                                              AS n_intervals,
       SUM(len_m)                                            AS metres,
       ROUND(SUM(li_mg_l * len_m) / SUM(len_m), 0)           AS li_wavg_mg_l,
       ROUND(SUM(b_mg_l * len_m) / SUM(len_m), 0)            AS b_wavg_mg_l,
       ROUND(MIN(b_mg_l), 0)                                 AS b_min_mg_l,
       ROUND(MAX(b_mg_l), 0)                                 AS b_max_mg_l,
       ROUND(SUM(b_mg_l * len_m) / SUM(li_mg_l * len_m), 2)  AS b_li_ratio
FROM chem
GROUP BY source_table
ORDER BY source_table;
```

**Note:** Table 10.7 reports boric acid, so it is converted to B (`H3BO3 × 0.1748`) before
it sits next to `b_mg_l` of 10.3/10.5; compared raw it overstates boron by ~5.7×. Every row
is already an interval average of very different length, so the averages are weighted by
`to_m - from_m` (not `length_m`, which is shorter than the interval in some 10.3 rows). One
row per table on purpose: the three differ in campaign, sampling method and lab and are not
pooled. The 10.3 rows printed under PE-14 belong to PE-14A (`data_error`), which does not
change a table-level figure but would change a per-hole one.

---

## 2. Coordinates and elevation — screen elevations of the wells with a collar Z

**Prompt:** "Give me the screen top and bottom elevation (masl) of every well with a known
collar elevation, with coordinates for the map"

```sql
SELECT w.pozo_id, w.programa, w.easting, w.northing, w.lat, w.lon, w.xy_conflicto, w.fuente_xy,
       w.z_collar,
       w.z_collar - a.screen_top_m_bls     AS screen_top_masl,
       w.z_collar - a.screen_bottom_m_bls  AS screen_bottom_masl,
       m.screen_top_masl                   AS model_screen_top_masl,
       m.screen_bottom_masl                AS model_screen_bottom_masl,
       (w.fuente_xy = 'A1.T1' OR NOT w.xy_conflicto) AS xyz_same_point
FROM tA1_1_exploration_well_locations a
JOIN wells w ON w.pozo_id = a.pozo_id
LEFT JOIN tA2_4_production_well_model m ON m.pozo_id = a.pozo_id
WHERE w.z_collar IS NOT NULL
ORDER BY w.pozo_id;
```

**Note:** `z_collar` exists only for the Appendix 1 wells (land surface), so a depth is turned
into an elevation only there; the Appendix 1 screen depths are m below land surface, the same
reference as `z_collar`. X/Y come from `wells` (EPSG:22183, assumed). `xyz_same_point = false`
flags W-04A: its XY is taken from Table 10.8, 816 m away from the Appendix 1 point that the Z
belongs to. The Appendix 2 model screen is shown as a cross-check, not as a substitute
(`top_model_masl` is the model cell, not the collar).

---

## 3. Piezometers — length-weighted Li profile per piezometer, on the map

**Prompt:** "Which piezometer boreholes have the richest brine? Average Li and Mg/Li per
profile, with coordinates"

```sql
WITH profile AS (
    SELECT c.piezometer_id,
           COUNT(*)                                                       AS n_intervals,
           MIN(c.from_m)                                                  AS profile_top_m,
           MAX(c.to_m)                                                    AS profile_bottom_m,
           SUM(c.li_mg_l * (c.to_m - c.from_m)) / SUM(c.to_m - c.from_m)  AS li_wavg_mg_l,
           SUM(c.mg_mg_l * (c.to_m - c.from_m))
             / SUM(c.li_mg_l * (c.to_m - c.from_m))                       AS mg_li_wavg
    FROM t10_7_piezometer_brine_chemistry c
    GROUP BY c.piezometer_id
)
SELECT p.piezometer_id, z.borehole_id, p.n_intervals,
       p.profile_top_m, p.profile_bottom_m,
       ROUND(p.li_wavg_mg_l, 0) AS li_wavg_mg_l,
       ROUND(p.mg_li_wavg, 2)   AS mg_li_wavg,
       w.easting, w.northing, w.lat, w.lon, w.xy_conflicto
FROM profile p
JOIN t10_6_piezometers z ON z.piezometer_id = p.piezometer_id
LEFT JOIN wells w        ON w.pozo_id = z.borehole_id
ORDER BY li_wavg_mg_l DESC;
```

**Note:** join path piezometer → borehole → `wells` (`t10_6_piezometers.borehole_id` is the
physical collar; `piezometer_id` is unique there, so the first join does not fan out). Mg/Li is
the ratio of the weighted sums, not an average of row ratios. The intervals are bailer profiles
of the hole, **not** the piezometer screen: do not read the result as "screen chemistry". The
DD19D-001 row continues the DL-001 profile in another borehole, so DL-001 appears split. DL-014
shows `xy_conflicto = false` but its XY is a suspected copy of SL-014's (`data_error` in
`t10_6_piezometers`).

---

## 4. Production wells — how many, by program

**Prompt:** "How many production wells are there?"

```sql
SELECT programa,
       CASE programa
           WHEN 'PRODUCCION_10_8'   THEN 'drilled, detailed in Table 10.8'
           WHEN 'PRODUCCION_2024'   THEN 'infill 2024, under construction'
           WHEN 'MODELO_APENDICE_2' THEN 'reserve model only, not confirmed'
           WHEN 'APENDICE_1'        THEN 'Appendix 1 only, not confirmed'
       END                                              AS status,
       COUNT(*)                                         AS n_wells,
       SUM(CASE WHEN xy_conflicto THEN 1 ELSE 0 END)    AS n_xy_conflict,
       COUNT(z_collar)                                  AS n_with_z_collar
FROM wells
WHERE programa LIKE 'PRODUCCION%'
   OR programa IN ('MODELO_APENDICE_2', 'APENDICE_1')
GROUP BY programa
ORDER BY n_wells DESC;
```

**Note:** there is no single answer and the query does not give one: the report says 43
drilled since 2011 (section 10.8) and 39 brine extraction wells built 2018-2024 (16.3), while
Table 10.8 details 38. `programa LIKE 'PRODUCCION%'` gives 41 (38 + 3 infill wells under
construction); `MODELO_APENDICE_2` and `APENDICE_1` are listed apart because they are not
confirmed production wells. `COUNT(*)` of `t10_8_production_wells` is not "wells drilled"
(`data_error`).

---

## 5. Source QA — calibration residuals of the groundwater model, by data source

**Prompt:** "How well does the steady-state model fit the observed groundwater levels? Split
by who measured them"

```sql
SELECT source,
       COUNT(*)                                      AS n_points,
       ROUND(AVG(residual_m), 2)                     AS mean_residual_m,
       ROUND(AVG(ABS(residual_m)), 2)                AS mean_abs_residual_m,
       ROUND(SQRT(AVG(residual_m * residual_m)), 2)  AS rmse_m,
       MIN(residual_m)                               AS min_residual_m,
       MAX(residual_m)                               AS max_residual_m
FROM t15_3_steady_state_residuals
WHERE residual_raw NOT LIKE '%*%'
GROUP BY source
ORDER BY source;
```

**Note:** rows whose printed residual carries the `*` footnote are left out: that is DDH-17, a
flowing well ~13 km south of the rest whose observed value is a censored model target, not a
measurement. The CAU* points are third-party data (2018), so they are kept as a separate group.
Values are groundwater **elevations** (masl) of 2018, pre-development, not corrected for brine
density; `residual_m` = observed − computed, so a negative mean means the model is too high.
