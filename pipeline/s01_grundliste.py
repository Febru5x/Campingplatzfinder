"""Schritt 01: Grundliste aller Campingplaetze einer Region aus OpenStreetMap.

Aufruf:  python -m pipeline.s01_grundliste seenplatte
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import common as C

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

QUERY_TMPL = """
[out:json][timeout:180];
(
  nwr["tourism"="camp_site"]({s},{w},{n},{e});
  nwr["tourism"="caravan_site"]({s},{w},{n},{e});
);
out tags center geom;
"""


def fetch_overpass(bbox):
    s, w, n, e = bbox
    q = QUERY_TMPL.format(s=s, w=w, n=n, e=e)
    last = None
    for ep in OVERPASS_ENDPOINTS:
        for attempt in range(3):
            try:
                txt = C.http_post(ep, data={"data": q}, timeout=200,
                                  headers={"User-Agent": "Campingplatzfinder/0.1"})
                data = json.loads(txt)
                if "elements" in data:
                    return data
                last = "no elements in response"
            except Exception as ex:
                last = str(ex)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("Overpass failed: %s" % last)


def element_geometry(el):
    """GeoJSON-Geometrie aus Overpass 'out geom'."""
    if el["type"] == "way" and "geometry" in el:
        coords = [[p["lon"], p["lat"]] for p in el["geometry"]]
        if coords and coords[0] == coords[-1] and len(coords) >= 4:
            return {"type": "Polygon", "coordinates": [coords]}
    if el["type"] == "relation" and "members" in el:
        rings = []
        for m in el["members"]:
            if m.get("role") == "outer" and "geometry" in m:
                coords = [[p["lon"], p["lat"]] for p in m["geometry"]]
                if coords and coords[0] == coords[-1] and len(coords) >= 4:
                    rings.append([coords])
        if rings:
            return {"type": "MultiPolygon", "coordinates": rings}
    return None


def polygon_area_m2(geom, lat0, lon0):
    if not geom:
        return None
    from shapely.geometry import shape
    from shapely.ops import transform
    proj = C.make_projector(lat0, lon0)
    g = transform(lambda x, y, z=None: proj(x, y), shape(geom))
    return g.area


def run(region_name):
    region = C.load_region(region_name)
    conn = C.init_db()
    # bevorzugt gecachte Testantwort nutzen (regionsspezifisch!), sonst live holen.
    # Bei CAMPING_REFRESH=1 (Update-Lauf) wird der Testcache ignoriert.
    testfile = Path(os.environ.get("TEMP", ".")) / "opencode" / ("overpass_test_%s.json" % region_name)
    if testfile.exists() and not os.environ.get("CAMPING_REFRESH"):
        data = json.loads(testfile.read_text(encoding="utf-8"))
        print("Nutze gecachte Overpass-Antwort:", testfile)
    else:
        data = fetch_overpass(region["bbox"])
    els = data["elements"]
    print("Overpass: %d Elemente" % len(els))
    n_new = n_upd = 0
    for el in els:
        tags = el.get("tags", {})
        if el["type"] == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            ctr = el.get("center") or {}
            lat, lon = ctr.get("lat"), ctr.get("lon")
        geom = element_geometry(el)
        if lat is None:
            # 'out geom' liefert kein center -> Schwerpunkt aus Geometrie
            if geom:
                from shapely.geometry import shape
                c = shape(geom).centroid
                lat, lon = c.y, c.x
            elif el["type"] == "way" and el.get("geometry"):
                pts = el["geometry"]
                lat = sum(p["lat"] for p in pts) / len(pts)
                lon = sum(p["lon"] for p in pts) / len(pts)
        if lat is None:
            continue
        sid = "%s/%s" % (el["type"], el["id"])
        area = polygon_area_m2(geom, lat, lon) if geom else None
        row = (
            sid, el["type"], el["id"],
            tags.get("name") or tags.get("operator") or "(unbenannt)",
            tags.get("tourism"),
            lat, lon,
            json.dumps(geom) if geom else None,
            area,
            tags.get("website") or tags.get("contact:website"),
            tags.get("phone") or tags.get("contact:phone"),
            tags.get("email") or tags.get("contact:email"),
            tags.get("operator"),
            tags.get("stars"),
            tags.get("capacity") or tags.get("capacity:pitches"),
            json.dumps(tags, ensure_ascii=False),
            region_name, "osm",
        )
        exists = conn.execute("SELECT id FROM sites WHERE id=?", (sid,)).fetchone()
        conn.execute("""
            INSERT INTO sites (id, osm_type, osm_id, name, category, lat, lon,
                geometry, area_m2, website, phone, email, operator, stars,
                capacity, raw_tags, region, source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, lat=excluded.lat, lon=excluded.lon,
                geometry=excluded.geometry, area_m2=excluded.area_m2,
                website=COALESCE(excluded.website, sites.website),
                phone=COALESCE(excluded.phone, sites.phone),
                email=COALESCE(excluded.email, sites.email),
                operator=COALESCE(excluded.operator, sites.operator),
                raw_tags=excluded.raw_tags
        """, row)
        conn.execute(
            "INSERT OR IGNORE INTO enrichment (site_id, updated) VALUES (?,?)",
            (sid, datetime.now(timezone.utc).isoformat()))
        if exists:
            n_upd += 1
        else:
            n_new += 1
    conn.commit()
    total = conn.execute("SELECT COUNT(*) c FROM sites WHERE region=?",
                         (region_name,)).fetchone()["c"]
    with_web = conn.execute(
        "SELECT COUNT(*) c FROM sites WHERE region=? AND website IS NOT NULL",
        (region_name,)).fetchone()["c"]
    print("Neu: %d, aktualisiert: %d, gesamt in Region: %d (mit Website: %d)"
          % (n_new, n_upd, total, with_web))
    conn.close()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "seenplatte")
