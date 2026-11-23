"""Schritt 14: Amtliche Gebaeude-Footprints (ALKIS) je Campingplatz.

NUR Brandenburg + Sachsen: die ALKIS-vereinfacht-WFS (ave:GebaeudeBauwerk)
liefern Gebaeude-Umrisse + Nutzungstyp (funktion, z.B. 'Wohnhaus',
'Pumpstation', 'Empfangsgebäude') + Kataster-Stand (aktualit).
MV liefert keine Gebaeude ueber die freien Dienste (Sackgasse, geprueft).

Ergebnis je Platz: enrichment.buildings (JSON):
  {n, flaeche_m2, typen: {...}, gebaeude: [{flaeche_m2, funktion, aktualit}]}
Damit: 'was steht da' amtlich statt Bilderkennung; Zustand via Luftbilder.

Aufruf: python -m pipeline.s14_gebaeude brandenburg [--top=40]
"""
import json
import math
import re
import sys
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

from pyproj import Transformer

from . import common as C

AVE_NS = "http://repository.gdi-de.org/schemas/adv/produkt/alkis-vereinfacht/2.0"
GML_NS = "http://www.opengis.net/gml"
T_FWD = Transformer.from_crs("EPSG:4326", "EPSG:25833", always_xy=True)
T_INV = Transformer.from_crs("EPSG:25833", "EPSG:4326", always_xy=True)


def fetch_buildings(wfs_url, lat, lon, half=250, wfs_version="1.1.0", bbox_crs="25833"):
    """TH (geoproxy): nur WFS 2.0.0, BBOX immer EPSG:25832 x,y (Suffix egal),
    Ausgabe via SRSNAME=25833; ave-Namespace dort 1.0 statt 2.0."""
    x, y = T_FWD.transform(lon, lat)
    bx1, by1, bx2, by2 = x - half, y - half, x + half, y + half
    if bbox_crs != "25833":
        t = Transformer.from_crs("EPSG:25833", "EPSG:" + bbox_crs, always_xy=True)
        bx1, by1 = t.transform(bx1, by1)
        bx2, by2 = t.transform(bx2, by2)
    params = {
        "SERVICE": "WFS", "VERSION": wfs_version, "REQUEST": "GetFeature",
        "SRSNAME": "EPSG:25833",
    }
    if wfs_version == "2.0.0":
        params["TYPENAMES"] = "ave:GebaeudeBauwerk"
        params["COUNT"] = "400"
        params["BBOX"] = "%f,%f,%f,%f,urn:ogc:def:crs:EPSG::%s" % (bx1, by1, bx2, by2, bbox_crs)
    else:
        params["TYPENAME"] = "ave:GebaeudeBauwerk"
        params["MAXFEATURES"] = "400"
        params["BBOX"] = "%f,%f,%f,%f,EPSG:%s" % (bx1, by1, bx2, by2, bbox_crs)
    key = "geb_%s_%.4f_%.4f" % (re.sub(r"[^\w]", "", wfs_url)[-20:], lat, lon)
    xml = C.http_get(wfs_url, params=params, cache_key=key, max_age_h=24 * 180,
                     polite=0.4, retries=3, timeout=120)
    out = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return out
    from shapely.geometry import Polygon
    for gb in root.iter():
        if not (gb.tag.endswith("}GebaeudeBauwerk") and "alkis-vereinfacht" in gb.tag):
            continue
        ns = gb.tag.split("}")[0][1:]
        def t(tag, gb=gb, ns=ns):
            el = gb.find("{%s}%s" % (ns, tag))
            return (el.text or "").strip() if el is not None else ""
        d = {"funktion": t("funktion"), "gebnutzbez": t("gebnutzbez"),
             "aktualit": t("aktualit")}
        area = 0.0
        cx = cy = None
        for pos in gb.iter():
            if not pos.tag.endswith("}posList"):
                continue
            vals = [float(v) for v in pos.text.split()]
            coords = list(zip(vals[0::2], vals[1::2]))
            if len(coords) >= 3:
                try:
                    poly = Polygon(coords)
                    area += poly.area
                    cx, cy = poly.centroid.x, poly.centroid.y
                except Exception:
                    pass
        d["flaeche_m2"] = round(area, 1)
        if cx is not None:
            d["lon"], d["lat"] = T_INV.transform(cx, cy)
        out.append(d)
    return out


def dist_m(lat1, lon1, lat2, lon2):
    return C.haversine(lat1, lon1, lat2, lon2)


def filter_to_site(buildings, site):
    """Nachbarn raus: Gebaeude muessen im OSM-Polygon (+25m) bzw. <=120m
    vom Platzpunkt liegen."""
    from shapely.geometry import shape, Point
    g = None
    if site["geometry"]:
        try:
            g = shape(json.loads(site["geometry"])).buffer(0.00025)
        except Exception:
            g = None
    keep = []
    for b in buildings:
        if b.get("lat") is None:
            continue
        if g is not None:
            if g.contains(Point(b["lon"], b["lat"])):
                keep.append(b)
        elif dist_m(site["lat"], site["lon"], b["lat"], b["lon"]) <= 120:
            keep.append(b)
    return keep


def run(region_name, top=None):
    region = C.load_region(region_name)
    wfs = region.get("alkis_wfs")
    if not wfs or region.get("alkis_schema") != "ave":
        print("Gebaeude-WFS nicht verfuegbar fuer Region %s (nur BB/SN)." % region_name)
        return
    conn = C.init_db()
    q = """SELECT s.id, s.name, s.lat, s.lon, s.geometry FROM sites s
        JOIN enrichment e ON s.id=e.site_id WHERE s.region=?
        ORDER BY e.lead_score DESC NULLS LAST"""
    sites = conn.execute(q, (region_name,)).fetchall()
    if top:
        # Vereine IMMER mitnehmen (Vereinsheim-Pruefung fuer s17),
        # auch wenn sie nicht in den Top-N nach Score sind
        import re as _re
        verein_pat = _re.compile(r"verein|club|e\.?\s?v\.?\b", _re.I)
        picked = list(sites[:top])
        picked_ids = {s["id"] for s in picked}
        for s in sites[top:]:
            if s["name"] and verein_pat.search(s["name"]) and s["id"] not in picked_ids:
                picked.append(s)
        sites = picked
    print("Plaetze:", len(sites))
    conn.close()
    import threading
    from concurrent.futures import ThreadPoolExecutor
    counters = {"ok": 0, "done": 0}
    lock = threading.Lock()

    def work(site):
        try:
            gbs = fetch_buildings(wfs, site["lat"], site["lon"],
                                  wfs_version=region.get("alkis_wfs_version", "1.1.0"),
                                  bbox_crs=region.get("alkis_bbox_crs", "25833"))
        except Exception as e:
            with lock:
                counters["done"] += 1
                print("  !", site["name"][:40], str(e)[:70], flush=True)
            return
        gbs = filter_to_site(gbs, site)
        if not gbs:
            with lock:
                counters["done"] += 1
            return
        typen = {}
        for b in gbs:
            f = b["funktion"] or b["gebnutzbez"] or "unbekannt"
            typen[f] = typen.get(f, 0) + 1
        info = {"n": len(gbs),
                "flaeche_m2": round(sum(b["flaeche_m2"] for b in gbs)),
                "typen": dict(sorted(typen.items(), key=lambda kv: -kv[1])),
                "gebaeude": sorted(gbs, key=lambda b: -b["flaeche_m2"])[:60],
                "hinweis": "ALKIS-Gebaeude auf dem Platz (OSM-Polygon +25m bzw. "
                           "120m-Radius); 'aktualit' = Kataster-Stand, nicht Baujahr"}
        sid = site["id"]
        ij = json.dumps(info, ensure_ascii=False)
        ts = datetime.now(timezone.utc).isoformat()
        def _write(c, sid=sid, ij=ij, ts=ts):
            c.execute("UPDATE enrichment SET buildings=?, updated=? WHERE site_id=?",
                      (ij, ts, sid))
        C.db_write(_write)
        top3 = ", ".join("%s×%d" % (k[:30], v) for k, v in list(info["typen"].items())[:3])
        with lock:
            counters["ok"] += 1
            counters["done"] += 1
            print("  %2d/%d %-40s %3d Geb., %6d m² | %s" % (
                counters["done"], len(sites), site["name"][:40],
                info["n"], info["flaeche_m2"], top3), flush=True)

    workers = 4
    for a in sys.argv:
        if a.startswith("--workers"):
            workers = int(a.split("=")[1])
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, sites))
    else:
        for s in sites:
            work(s)
    print("Fertig: Plaetze mit Gebaeuden=%d" % counters["ok"], flush=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    top = None
    for a in sys.argv:
        if a.startswith("--top="):
            top = int(a.split("=")[1])
    run(args[0] if args else "brandenburg", top)