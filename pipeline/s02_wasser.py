"""Schritt 02: Wasserlage-Analyse pro Campingplatz.

- holt Gewaesser (Seen, Fluesse), Stege, Marinas, Schutzgebiete per Overpass
- berechnet Abstand zum Wasser, Uferlaenge am Grundstueck, Wasser-Score
- Flagge Motorboot-Verbot (CEMT / OSM motorboat-Tags auf Seen)

Aufruf:  python -m pipeline.s02_wasser seenplatte
"""
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone

from shapely.geometry import shape, Point, mapping
from shapely.ops import transform, nearest_points

from . import common as C
from .s01_grundliste import OVERPASS_ENDPOINTS, element_geometry

WATER_QUERY = """
[out:json][timeout:300];
(
  way["natural"="water"]({s},{w},{n},{e});
  relation["natural"="water"]({s},{w},{n},{e});
  way["waterway"="riverbank"]({s},{w},{n},{e});
  relation["waterway"="riverbank"]({s},{w},{n},{e});
  way["waterway"="river"]["width"!~"."]({s},{w},{n},{e});
  way["man_made"="pier"]({s},{w},{n},{e});
  nwr["leisure"="marina"]({s},{w},{n},{e});
  nwr["boundary"="protected_area"]({s},{w},{n},{e});
  relation["boundary"="protected_area"]({s},{w},{n},{e});
);
out tags center geom;
"""


def _cached_post(query, cache_key, timeout):
    """Overpass-POST mit Datei-Cache (180 Tage) – Nachlaeufe in Sekunden."""
    import hashlib
    import time as _t
    cpath = C.CACHE / (cache_key + ".txt")
    mpath = C.CACHE / (cache_key + ".meta")
    if cpath.exists() and mpath.exists():
        try:
            meta = json.loads(mpath.read_text(encoding="utf-8"))
            if _t.time() - meta["ts"] < 180 * 24 * 3600:
                data = json.loads(cpath.read_text(encoding="utf-8"))
                if "elements" in data:
                    return data
        except Exception:
            pass
    last = None
    for ep in OVERPASS_ENDPOINTS:
        for attempt in range(3):
            try:
                txt = C.http_post(ep, data={"data": query}, timeout=timeout,
                                  headers={"User-Agent": "Campingplatzfinder/0.1"})
                data = json.loads(txt)
                if "elements" in data:
                    cpath.write_text(txt, encoding="utf-8")
                    mpath.write_text(json.dumps({"ts": _t.time()}), encoding="utf-8")
                    return data
                last = "no elements"
            except Exception as ex:
                last = str(ex)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("Overpass failed: %s" % last)


def fetch_water(bbox):
    s, w, n, e = bbox
    q = WATER_QUERY.format(s=s, w=w, n=n, e=e)
    key = "water_%s" % hashlib.sha1(q.encode()).hexdigest()[:16]
    return _cached_post(q, key, 320)


def river_centerlines(bbox):
    """Fluss-Mittellinien separat (fuer Abstand zu schmalen Fluessen)."""
    s, w, n, e = bbox
    q = ('[out:json][timeout:180];way["waterway"="river"](%f,%f,%f,%f);'
         'out tags geom;' % (s, w, n, e))
    key = "rivers_%s" % hashlib.sha1(q.encode()).hexdigest()[:16]
    try:
        return _cached_post(q, key, 200)["elements"]
    except Exception:
        return []


def run(region_name):
    region = C.load_region(region_name)
    bbox = region["bbox"]
    lat0 = (bbox[0] + bbox[2]) / 2
    lon0 = (bbox[1] + bbox[3]) / 2
    proj = C.make_projector(lat0, lon0)

    def prj(geom):
        return transform(lambda x, y, z=None: proj(x, y), geom)

    conn = C.init_db()
    sites = conn.execute(
        "SELECT * FROM sites WHERE region=?", (region_name,)).fetchall()
    print("Plaetze:", len(sites))

    data = fetch_water(bbox)
    print("Wasser-Elemente:", len(data["elements"]))

    lakes, piers, marinas, protected = [], [], [], []
    for el in data["elements"]:
        tags = el.get("tags", {})
        geom = element_geometry(el)
        if el["type"] == "node":
            pt = Point(el["lon"], el["lat"])
            g = prj(pt)
        elif geom:
            try:
                g = prj(shape(geom))
            except Exception:
                continue
            if not g.is_valid:
                g = g.buffer(0)
        else:
            continue
        name = tags.get("name", "")
        if tags.get("natural") == "water" or tags.get("waterway") == "riverbank":
            if g.geom_type in ("Polygon", "MultiPolygon") and g.area > 2000:
                lakes.append({
                    "geom": g, "name": name,
                    "type": tags.get("water", "water"),
                    "motorboat": tags.get("motorboat", ""),
                    "boat": tags.get("boat", ""),
                    "area": g.area,
                })
        elif tags.get("man_made") == "pier":
            piers.append(g)
        elif tags.get("leisure") == "marina":
            marinas.append(g)
        elif tags.get("boundary") == "protected_area":
            if g.geom_type in ("Polygon", "MultiPolygon"):
                protected.append({"geom": g, "name": name,
                                  "class": tags.get("protect_class", ""),
                                  "title": tags.get("protection_title", "")})
    print("Gewaesser:", len(lakes), "Stege:", len(piers),
          "Marinas:", len(marinas), "Schutzgebiete:", len(protected))

    rivers = []
    for el in river_centerlines(bbox):
        if "geometry" in el:
            from shapely.geometry import LineString
            coords = [(p["lon"], p["lat"]) for p in el["geometry"]]
            if len(coords) >= 2:
                g = prj(LineString(coords))
                rivers.append({"geom": g, "name": el.get("tags", {}).get("name", ""),
                               "motorboat": el.get("tags", {}).get("motorboat", "")})
    print("Fluesse:", len(rivers))

    n_done = 0
    for site in sites:
        if site["geometry"]:
            g_site = prj(shape(json.loads(site["geometry"])))
            if not g_site.is_valid:
                g_site = g_site.buffer(0)
            ref = g_site
        else:
            ref = prj(Point(site["lon"], site["lat"])).buffer(60)  # ~typ. Platzradius

        best = None
        for w in lakes + rivers:
            d = ref.distance(w["geom"])
            if best is None or d < best["dist"]:
                best = {"dist": d, "w": w}
        dist = best["dist"] if best else None
        wname = best["w"]["name"] if best else None
        wtype = best["w"].get("type", "river") if best else None
        motor = ""
        if best:
            motor = best["w"].get("motorboat", "") or ""

        # Uferlaenge: Schnitt der Grundstuecksgrenze mit Gewaesser-Puffer 15m
        shoreline = 0.0
        if site["geometry"]:
            boundary = g_site.boundary
            for w in lakes:
                if ref.distance(w["geom"]) < 25:
                    inter = boundary.intersection(w["geom"].buffer(15))
                    if inter is not None and not inter.is_empty:
                        shoreline += inter.length
            # Wasserflaeche innerhalb des Platzes (eigener Teich/Bucht)
            for w in lakes:
                if g_site.intersects(w["geom"]):
                    inner = g_site.intersection(w["geom"])
                    # degenerierte Schnitte (Point/Line/leer) haben keine boundary
                    if inner is not None and inner.area > 100 and inner.boundary is not None:
                        shoreline += inner.boundary.length * 0.5
        # Steg innerhalb / nah am Platz?
        has_pier = any(ref.distance(p) < 40 for p in piers)
        marina_d = min((ref.distance(m) for m in marinas), default=None)

        prot = []
        for p in protected:
            if ref.distance(p["geom"]) < 100:
                prot.append("%s (Klasse %s)" % (p["name"] or p["title"], p["class"]))

        # Wasser-Score 0..100
        score = 0.0
        if dist is not None:
            if dist <= 5:
                score = 60
            elif dist <= 50:
                score = 50
            elif dist <= 150:
                score = 35
            elif dist <= 400:
                score = 20
            elif dist <= 1000:
                score = 10
            if shoreline > 30:
                score += 20
            if has_pier:
                score += 10
            if marina_d is not None and marina_d < 300:
                score += 5
            if best and best["w"].get("area", 0) > 500000:  # grosser See
                score += 5
        score = min(score, 100)

        motor_flag = ("verboten/nein" if motor in ("no", "private") and motor == "no"
                      else ("eingeschraenkt" if motor in ("permit", "private", "destination")
                            else ("erlaubt" if motor == "yes" else "unbekannt")))

        conn.execute("""UPDATE enrichment SET
            water_distance_m=?, water_name=?, water_type=?, shoreline_m=?,
            has_pier=?, marina_distance_m=?, protected_area=?, motorboat_flag=?,
            water_score=?, updated=? WHERE site_id=?""",
            (round(dist, 1) if dist is not None else None, wname, wtype,
             round(shoreline, 1), int(has_pier),
             round(marina_d, 1) if marina_d is not None else None,
             "; ".join(prot) if prot else None, motor_flag,
             score, datetime.now(timezone.utc).isoformat(), site["id"]))
        n_done += 1
        if n_done % 50 == 0:
            conn.commit()
            print("...", n_done)
    conn.commit()
    rows = conn.execute("""SELECT COUNT(*) c FROM enrichment e JOIN sites s ON s.id=e.site_id
        WHERE s.region=? AND e.water_distance_m<=50""", (region_name,)).fetchone()
    print("Fertig. Plaetze direkt am Wasser (<=50m):", rows["c"])
    conn.close()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "seenplatte")
