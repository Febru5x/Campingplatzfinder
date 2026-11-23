"""Schritt 18: Gewaesser-Flaechen (amtlich vergleichbar, OSM-Geometrie).

Misst die Flaeche des naechstgelegenen Gewaessers je Platz in Hektar und
gibt eine einheitliche Quelle an (OSM-Gewaesserflaeche + Typ-Tag).
Ergebnis: enrichment.water_area_ha, water_class_src.
Danach s17 neu laufen lassen (nutzt die Flaechen fuer die Hausboot-Eignung).

Aufruf:  python -m pipeline.s18_gewaesserflaeche <region|alle>
"""
import json
import sys

from shapely.geometry import shape, Point
from shapely.ops import transform

from . import common as C
from .s02_wasser import fetch_water, river_centerlines
from .s01_grundliste import element_geometry

REGIONS = ["seenplatte", "brandenburg", "sachsen", "sachsen_anhalt", "thueringen"]


def run(region_name):
    regions = REGIONS if region_name in ("alle", "all") else [region_name]
    for reg in regions:
        region = C.load_region(reg)
        bbox = region["bbox"]
        lat0 = (bbox[0] + bbox[2]) / 2
        lon0 = (bbox[1] + bbox[3]) / 2
        proj = C.make_projector(lat0, lon0)

        def prj(g):
            return transform(lambda x, y, z=None: proj(x, y), g)

        data = fetch_water(bbox)  # Datei-Cache: Nachlauf in Sekunden
        waters = []
        for el in data["elements"]:
            tags = el.get("tags", {})
            if not (tags.get("natural") == "water" or tags.get("waterway") == "riverbank"):
                continue
            geom = element_geometry(el)
            if not geom:
                continue
            try:
                g = prj(shape(geom))
            except Exception:
                continue
            if g.geom_type not in ("Polygon", "MultiPolygon"):
                continue
            if not g.is_valid:
                g = g.buffer(0)
            if g.area < 500:
                continue
            waters.append({"geom": g, "name": tags.get("name", ""),
                           "type": tags.get("water") or tags.get("waterway") or "water"})
        print("%s: %d Gewaesser-Flaechen" % (reg, len(waters)))
        # Raeumlicher Index: nearest-Abfrage statt O(n*m)-Distanzschleife
        from shapely.strtree import STRtree
        tree = STRtree([w["geom"] for w in waters])
        conn = C.init_db()
        sites = conn.execute("SELECT * FROM sites WHERE region=?", (reg,)).fetchall()
        n = 0
        for site in sites:
            if site["geometry"]:
                try:
                    ref = prj(shape(json.loads(site["geometry"])))
                except Exception:
                    ref = prj(Point(site["lon"], site["lat"])).buffer(60)
            else:
                ref = prj(Point(site["lon"], site["lat"])).buffer(60)
            best = None
            try:
                idx = tree.nearest(ref)
                if isinstance(idx, (list, tuple)):
                    idx = idx[0]
                w = waters[int(idx)]
                best = (ref.distance(w["geom"]), w)
            except Exception:
                # Fallback (aeltere Shapely): expandierende BBOX-Suche
                r = 500.0
                while best is None and r <= 64000:
                    for i in tree.query(ref.buffer(r)):
                        w = waters[int(i)]
                        d = ref.distance(w["geom"])
                        if best is None or d < best[0]:
                            best = (d, w)
                    r *= 4
            if best is None:
                conn.execute("""UPDATE enrichment SET water_area_ha=NULL,
                    water_class_src=NULL WHERE site_id=?""", (site["id"],))
                continue
            d, w = best
            ha = round(w["geom"].area / 10000.0, 2)
            src = "OSM-Flaeche %.1f ha (%s)" % (ha, w["type"])
            conn.execute("""UPDATE enrichment SET water_area_ha=?, water_class_src=?
                WHERE site_id=?""", (ha, src, site["id"]))
            n += 1
        conn.commit()
        conn.close()
        print("%s: %d Plaetze mit Gewaesserflaeche" % (reg, n))


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "alle")