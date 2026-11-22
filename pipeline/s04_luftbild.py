"""Schritt 04: Luftbilder (DOP20) pro Campingplatz + Befliegungsjahr.

- holt einen WMS-Ausschnitt (aktuelles amtliches Orthophoto, 20cm)
- fragt das Befliegungsjahr ab (mv_dop_info)
- speichert PNG unter OUTPUT/luftbilder/<id>.png

Aufruf:  python -m pipeline.s04_luftbild seenplatte [--size 1200]
"""
import json
import re
import sys
from datetime import datetime, timezone

from pyproj import Transformer
from shapely.geometry import shape, Point, box
from shapely.ops import transform

from . import common as C

WMS = None  # aus Region-Config
T_FWD = Transformer.from_crs("EPSG:4326", "EPSG:25833", always_xy=True)


def site_bbox_25833(site, pad=60):
    proj = C.make_projector(site["lat"], site["lon"])
    if site["geometry"]:
        g = shape(json.loads(site["geometry"]))
        minx, miny, maxx, maxy = g.bounds
        # Grad-Puffer grob in Meter umrechnen
        dlat = pad / 111320.0
        dlon = pad / (111320.0 * 0.6)
        minx, maxx = minx - dlon, maxx + dlon
        miny, maxy = miny - dlat, maxy + dlat
    else:
        dlat = 150 / 111320.0
        dlon = 150 / (111320.0 * 0.6)
        minx, maxx = site["lon"] - dlon, site["lon"] + dlon
        miny, maxy = site["lat"] - dlat, site["lat"] + dlat
    x1, y1 = T_FWD.transform(minx, miny)
    x2, y2 = T_FWD.transform(maxx, maxy)
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def get_dop(wms_url, layer, bbox, size=1000):
    x1, y1, x2, y2 = bbox
    # Seitenverhältnis beibehalten
    w = x2 - x1
    h = y2 - y1
    if w >= h:
        width, height = size, max(64, int(size * h / w))
    else:
        width, height = max(64, int(size * w / h)), size
    if "exportImage" in wms_url or "/ImageServer" in wms_url:
        # ST: ArcGIS ImageServer (DOP-WMS wegen Serverstoerung down)
        params = {
            "f": "image", "bbox": "%f,%f,%f,%f" % (x1, y1, x2, y2),
            "bboxSR": "25833", "imageSR": "25833",
            "size": "%d,%d" % (width, height), "format": "jpg",
        }
        url = wms_url.rstrip("/") + "/exportImage"
    else:
        params = {
            "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetMap",
            "LAYERS": layer, "STYLES": "", "SRS": "EPSG:25833",
            "BBOX": "%f,%f,%f,%f" % (x1, y1, x2, y2),
            "WIDTH": str(width), "HEIGHT": str(height), "FORMAT": "image/jpeg",
        }
        url = wms_url
    key = "dop_%s_%d_%d_%d_%d_%d" % (layer, x1, y1, x2, y2, size)
    return C.http_get(url, params=params, binary=True, cache_key=key,
                      max_age_h=24 * 180, polite=0.3, timeout=120)


def get_flight_year(wms_url, bbox, info_layer="mv_dop_info"):
    x1, y1, x2, y2 = bbox
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    half = max(50, (x2 - x1) / 4)
    if info_layer.startswith("http"):
        # ST: info_layer ist eine MapServer-URL (DOP_Kacheluebersichten),
        # identify liefert 'Befliegungsdatum': '01.05.2026' (taggenau!)
        params = {
            "f": "json", "geometry": "%f,%f" % (cx, cy),
            "geometryType": "esriGeometryPoint", "sr": "25833",
            "layers": "all:0", "tolerance": "2",
            "mapExtent": "%f,%f,%f,%f" % (cx - half, cy - half, cx + half, cy + half),
            "imageDisplay": "400,400,96", "returnGeometry": "false",
        }
        key = "dopinfo_st_%d_%d" % (cx, cy)
        try:
            raw = C.http_get(info_layer.rstrip("/") + "/identify", params=params,
                             cache_key=key, max_age_h=24 * 180, polite=0.3, timeout=90)
            years = []
            for res in json.loads(raw).get("results", []):
                d = res.get("attributes", {}).get("Befliegungsdatum", "")
                years += [int(y) for y in re.findall(r"(20\d{2})", d)]
            return max(years) if years else None
        except Exception:
            return None
    # TH: text/plain liefert kaputtes $#$-Format -> text/xml (echtes GML)
    info_format = "text/xml" if info_layer.startswith("th_") else "text/plain"
    params = {
        "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetFeatureInfo",
        "LAYERS": info_layer, "QUERY_LAYERS": info_layer, "STYLES": "",
        "SRS": "EPSG:25833",
        "BBOX": "%f,%f,%f,%f" % (cx - half, cy - half, cx + half, cy + half),
        "WIDTH": "100", "HEIGHT": "100", "X": "50", "Y": "50",
        "INFO_FORMAT": info_format, "FEATURE_COUNT": "3",
    }
    key = "dopinfo_%s_%d_%d" % (info_layer, cx, cy)
    try:
        txt = C.http_get(wms_url, params=params, cache_key=key,
                         max_age_h=24 * 180, polite=0.3, timeout=90)
        years = []
        for line in txt.splitlines():
            if "Befliegungsjahr" in line:  # MV: "Befliegungsjahr = '2022'"
                y = line.split("=")[-1].strip().strip("'")
                if y.isdigit():
                    years.append(int(y))
            elif line.startswith("Datum:"):  # SN: "Datum: 04.04. + 20.04.2025"
                years += [int(y) for y in re.findall(r"(20\d{2})", line)]
        if not years and info_layer.startswith("th_"):
            # TH: GML-Feld <Erstellung>01.05.2024</Erstellung> (ggf. mit NS-Prefix)
            for m in re.finditer(r"<(?:\w+:)?Erstellung[^>]*>([^<]+)<", txt):
                years += [int(y) for y in re.findall(r"(20\d{2})", m.group(1))]
        return max(years) if years else None
    except Exception:
        return None


def run(region_name, size=1000, workers=1):
    region = C.load_region(region_name)
    wms_url = region.get("wms_dop")
    layer = region.get("wms_dop_layer", "mv_dop")
    if not wms_url:
        print("Keine DOP-Quelle fuer Region", region_name)
        return
    outdir = C.OUTPUT / "luftbilder"
    outdir.mkdir(parents=True, exist_ok=True)
    conn = C.init_db()
    sites = conn.execute("SELECT * FROM sites WHERE region=?", (region_name,)).fetchall()
    conn.close()
    print("Plaetze:", len(sites), "| workers=%d" % workers)
    import threading
    from concurrent.futures import ThreadPoolExecutor
    meta = {}
    counter = {"ok": 0, "err": 0, "done": 0}
    lock = threading.Lock()

    def work(site):
        sid_safe = site["id"].replace("/", "_")
        img_path = outdir / (sid_safe + ".jpg")
        bbox = site_bbox_25833(site)
        try:
            if not img_path.exists():
                data = get_dop(wms_url, layer, bbox, size)
                if data[:2] in (b"\xff\xd8", b"\x89P"):
                    img_path.write_bytes(data)
                else:
                    raise RuntimeError("keine Bilddaten: %s" % data[:100])
            year = None
            if region.get("dop_info_layer"):
                year = get_flight_year(wms_url, bbox, region["dop_info_layer"])
            entry = {"file": img_path.name, "year": year, "bbox25833": bbox}
            ok = True
        except Exception as ex:
            entry = {"error": str(ex)[:200]}
            ok = False
        with lock:
            meta[site["id"]] = entry
            counter["ok" if ok else "err"] += 1
            counter["done"] += 1
            if counter["done"] % 20 == 0:
                print("... %d/%d ok=%d err=%d" % (counter["done"], len(sites),
                      counter["ok"], counter["err"]), flush=True)

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, sites))
    else:
        for s in sites:
            work(s)
    (C.DATA / ("luftbild_meta_%s.json" % region_name)).write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Fertig: ok=%d err=%d, Meta in data/luftbild_meta_%s.json" % (
        counter["ok"], counter["err"], region_name), flush=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    size = 1000
    workers = 1
    for a in sys.argv:
        if a.startswith("--size"):
            size = int(a.split("=")[1])
        elif a.startswith("--workers"):
            workers = int(a.split("=")[1])
    run(args[0] if args else "seenplatte", size, workers)
