"""Build the well registry (pozo) from _build/ + csv/raw coordinate tables.

Outputs in _build/: xy_sources.csv (every coordinate observation), pozo.csv,
alias_pozo.csv, pozos_sin_xy.csv. `wells` gets lat/lon reprojected from easting/northing
(EPSG:22183 -> EPSG:4326, pyproj).
Usage: python -I registry.py <cauchari_dir>   (needs pandas and pyproj)
"""
import math
import re
import sys
from pathlib import Path

import pandas as pd
from pyproj import Transformer

TO_WGS84 = Transformer.from_crs("EPSG:22183", "EPSG:4326", always_xy=True)

root = Path(sys.argv[1])
raw, clean = root / "csv" / "raw", root / "_build"


def rd(p):
    return pd.read_csv(p, dtype=str, keep_default_na=False)


def num(s):
    return float(s) if s not in ("", None) else math.nan


def ddh(s):
    m = re.fullmatch(r"DDH-?(\d+)([A-Z]?)", s)
    return f"DDH-{int(m.group(1)):02d}{m.group(2)}" if m else s


def pad(s):
    s = re.sub(r"\s+", "", s)
    m = re.fullmatch(r"([A-Z]+\d*[A-Z]?)-(\d+)([A-Z]?)", s)
    return f"{m.group(1)}-{int(m.group(2)):03d}{m.group(3)}" if m else s


A_MAP = {"PB-3A": "PB-03A", "PB4": "PB-04", "PB-6A": "PB-06A", "W04-A": "W-04A", "PB-01": "PB-01", "WR-3": "WR-03"}

t6 = rd(clean / "t10_6.csv")
pz2bh = dict(zip(t6.loc[t6.piezometer_id != "", "piezometer_id"], t6.loc[t6.piezometer_id != "", "borehole_id"]))

obs = []  # id_raw, id_canon, tabla, pag_pdf, easting, northing, z


def add(tabla, idr, idc, pag, e, n, z=""):
    obs.append(dict(tabla=tabla, id_raw=idr, pozo_id=idc, pag_pdf=pag, easting=e, northing=n, z_collar=z))


for r in t6.itertuples():
    add("10.6", r.piezometer_name, r.borehole_id, r.pag_pdf, num(r.x_coordinate_m), num(r.y_coordinate_m))
for r in rd(clean / "t10_8.csv").itertuples():
    add("10.8", r.pumping_well, r.pumping_well, r.pag_pdf, num(r.easting), num(r.northing))
for r in rd(clean / "t10_9.csv").itertuples():
    add("10.9", r.borehole_id, r.borehole_id, r.pag_pdf, num(r.easting), num(r.northing))
for r in rd(raw / "t15_3.csv").itertuples():
    i = r.well_id
    c = ddh(i) if i.startswith("DDH") else pz2bh.get(pad(i), pad(i)) if i[:2] in ("SL", "ML", "DL") else i
    add("15.3", i, c, r.pag_pdf, num(r.easting_m), num(r.northing_m))
for r in rd(raw / "tA1_1.csv").itertuples():
    add("A1.T1", r.well_id, A_MAP.get(r.well_id, r.well_id), r.pag_pdf, num(r.easting_m), num(r.northing_m), num(r.land_surface_elev_masl))
for r in rd(raw / "tA2.csv").itertuples():
    add("A2.T4", r.well_id, A_MAP.get(r.well_id, r.well_id), r.pag_pdf, num(r.easting_m), num(r.northing_m), num(r.top_model_masl))
for r in rd(raw / "t16_1.csv").itertuples():
    add("16.1", r.borehole_id, r.borehole_id.upper().replace("POZO ", "POZO-"), r.pag_pdf, num(r.easting_m), num(r.northing_m))
obs = pd.DataFrame(obs)
obs.to_csv(clean / "xy_sources.csv", index=False)

# Wells that exist in section 10 even without coordinates ----------------------------------------
ids = {}  # pozo_id -> programa


# programa = the report table that first names the hole (no classification by id prefix)
PROG_BY_TABLE = [("t10_1.csv", "well_id", "RC_2009_2010"), ("t10_4.csv", "well_id", "DDH_2009_2010"),
                 ("t10_5.csv", "well_id", "DDH_2009_2010"), ("t10_6.csv", "borehole_id", "DDH_2017_2019"),
                 ("t10_9.csv", "borehole_id", "DDH_ROTARY_2022_2024"), ("t10_8.csv", "pumping_well", "PRODUCCION_10_8")]
for f, col, p in PROG_BY_TABLE:
    for i in rd(clean / f)[col]:
        ids.setdefault(i, p)
OBS_PROG = [("16.1", "PRODUCCION_2024"), ("A1.T1", "APENDICE_1"), ("A2.T4", "MODELO_APENDICE_2"), ("15.3", "SOLO_TABLA_15_3")]
for t, p in OBS_PROG:
    for i in obs.loc[obs.tabla == t, "pozo_id"]:
        ids.setdefault(i, p)

rows = []
for i, p in sorted(ids.items()):
    o = obs[(obs.pozo_id == i) & obs.easting.notna()]
    if len(o):
        e, n = o.easting.iloc[0], o.northing.iloc[0]
        spread = max(math.hypot(a - e, b - n) for a, b in zip(o.easting, o.northing))
        z = obs[(obs.pozo_id == i) & (obs.tabla == "A1.T1")].z_collar
        zv = z.iloc[0] if len(z) and not math.isnan(z.iloc[0]) else ""
        rows.append(dict(pozo_id=i, programa=p, easting=e, northing=n, crs="EPSG:22183", fuente_xy=o.tabla.iloc[0],
                         fuentes_xy="|".join(sorted(set(o.tabla))), dispersion_xy_m=round(spread, 1), z_collar=zv,
                         fuente_z="A1.T1" if zv != "" else ""))
    else:
        rows.append(dict(pozo_id=i, programa=p, easting="", northing="", crs="", fuente_xy="", fuentes_xy="", dispersion_xy_m="", z_collar="", fuente_z=""))
pozo = pd.DataFrame(rows)
pozo["xy_conflicto"] = [("true" if d != "" and d > 10 else "false") if e != "" else "" for d, e in zip(pozo.dispersion_xy_m, pozo.easting)]
lonlat = [TO_WGS84.transform(e, n) if e != "" else ("", "") for e, n in zip(pozo.easting, pozo.northing)]
pozo.insert(pozo.columns.get_loc("northing") + 1, "lat", [round(la, 6) if la != "" else "" for _, la in lonlat])
pozo.insert(pozo.columns.get_loc("lat") + 1, "lon", [round(lo, 6) if lo != "" else "" for lo, _ in lonlat])
pozo.to_csv(clean / "pozo.csv", index=False)

# Alias candidates: different ids, same place (<=5 m), across different wells ---------------
c = pozo[pozo.easting != ""].copy()
c["easting"], c["northing"] = c.easting.astype(float), c.northing.astype(float)
al = []
for a in c.itertuples():
    for b in c.itertuples():
        if a.pozo_id < b.pozo_id:
            d = math.hypot(a.easting - b.easting, a.northing - b.northing)
            if d <= 5 and not (a.programa == b.programa == "DDH_2017_2019"):
                al.append(dict(pozo_a=a.pozo_id, pozo_b=b.pozo_id, dist_m=round(d, 1), prog_a=a.programa, prog_b=b.programa))
adf = pd.DataFrame(al)
adf["relacion"] = "mismo_sitio_por_coordenada"
adf.to_csv(clean / "alias_pozo.csv", index=False)
print(pd.DataFrame(al).to_string())

sin = pozo[pozo.easting == ""]
print("\npozos totales:", len(pozo), "sin XY:", len(sin))
print(sin.groupby("programa").pozo_id.apply(list).to_string())
print(pozo.groupby("programa").apply(lambda g: f"{(g.easting!='').sum()}/{len(g)} con XY").to_string())
