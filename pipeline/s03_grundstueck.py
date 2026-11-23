"""Schritt 03: Flurstuecke (ALKIS) pro Campingplatz via GeoPortal.MV WMS.

GetFeatureInfo (GML) liefert Flurstueckskennzeichen, amtliche Flaeche,
Gemarkung und Polygon-Geometrie. Wir rastern jeden Platz und sammeln
alle Flurstuecke, die ihn ueberdecken.

Aufruf:  python -m pipeline.s03_grundstueck seenplatte
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

from pyproj import Transformer
from shapely.geometry import shape, Point, Polygon
from shapely.ops import transform

from . import common as C

WMS = "https://www.geodaten-mv.de/dienste/alkis_wms"
NS = {"adv": "http://www.adv-online.de/namespaces/adv/gid/7.1",
      "gml": "http://www.opengis.net/gml"}
AVE_NS = "http://repository.gdi-de.org/schemas/adv/produkt/alkis-vereinfacht/2.0"
T_FWD = Transformer.from_crs("EPSG:4326", "EPSG:25833", always_xy=True)
T_INV = Transformer.from_crs("EPSG:25833", "EPSG:4326", always_xy=True)


def fetch_parcels_ave(wfs_url, bbox, cache_key, wfs_version="1.1.0", bbox_crs="25833"):
    """ALKIS-vereinfacht-WFS (ave:Flurstueck) fuer BB/SN/TH: eine BBOX-Abfrage
    liefert alle Flurstuecke inkl. Geometrie + amtlicher Flaeche.
    TH (geoproxy): NUR WFS 2.0.0; BBOX wird IMMER als EPSG:25832 x,y
    interpretiert (CRS-Suffix egal!), Ausgabe-CRS via SRSNAME=25833.
    bbox kommt immer in 25833 und wird hier ggf. umgerechnet."""
    x1, y1, x2, y2 = bbox
    if bbox_crs != "25833":
        t = Transformer.from_crs("EPSG:25833", "EPSG:" + bbox_crs, always_xy=True)
        x1, y1 = t.transform(x1, y1)
        x2, y2 = t.transform(x2, y2)
    params = {
        "SERVICE": "WFS", "VERSION": wfs_version, "REQUEST": "GetFeature",
        "SRSNAME": "EPSG:25833",
        "BBOX": "%f,%f,%f,%f,EPSG:%s" % (x1, y1, x2, y2, bbox_crs),
    }
    if wfs_version == "2.0.0":
        params["TYPENAMES"] = "ave:Flurstueck"
        params["COUNT"] = "300"
        params["BBOX"] = "%f,%f,%f,%f,urn:ogc:def:crs:EPSG::%s" % (x1, y1, x2, y2, bbox_crs)
    else:
        params["TYPENAME"] = "ave:Flurstueck"
        params["MAXFEATURES"] = "300"
    xml = C.http_get(wfs_url, params=params, cache_key=cache_key,
                     max_age_h=24 * 90, polite=0.4, retries=3, timeout=120)
    out = []
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return out
    for fs in root.iter():
        # ave-Namespace variiert: BB/SN = .../2.0, TH = .../1.0
        if not (fs.tag.endswith("}Flurstueck") and "alkis-vereinfacht" in fs.tag):
            continue
        ns = fs.tag.split("}")[0][1:]
        def t(tag, fs=fs, ns=ns):
            el = fs.find("{%s}%s" % (ns, tag))
            return (el.text or "").strip() if el is not None else ""
        d = {"id": fs.get("{%s}id" % NS["gml"]) or t("oid"),
             "kennzeichen": t("flstkennz").strip("_"),
             "gemarkung": t("gemarkung"), "gemarkung_nr": t("gemaschl"),
             "land": t("land"), "zaehler": t("flstnrzae") or t("flurstnr"),
             "nenner": t("flstnrnen"),
             "gemeinde": t("gemeinde"), "kreis": t("kreis"),
             "entstehung": t("aktualit")}
        try:
            d["flaeche_m2"] = float(t("flaeche")) if t("flaeche") else None
        except ValueError:
            d["flaeche_m2"] = None
        polys = []
        for pos in fs.iter():
            if not pos.tag.endswith("}posList"):
                continue
            vals = [float(v) for v in pos.text.split()]
            coords = list(zip(vals[0::2], vals[1::2]))
            if len(coords) >= 3:
                polys.append([T_INV.transform(x, y) for x, y in coords])
        if polys:
            d["geometry"] = ({"type": "Polygon", "coordinates": polys[:1]}
                             if len(polys) == 1 else
                             {"type": "MultiPolygon", "coordinates": [[p] for p in polys]})
        out.append(d)
    return out


def gfi(x, y, half=40, layer="adv_alkis_flurstuecke", bbox=None, wms=None):
    """GetFeatureInfo an einem Punkt (EPSG:25833), liefert GML-Text.
    bbox: groessere BBOX fuer mehr Treffer (FEATURE_COUNT)."""
    if bbox is None:
        bbox = (x - half, y - half, x + half, y + half)
    x1, y1, x2, y2 = bbox
    # Punkt-Position in Pixel
    ix = int(100 * (x - x1) / (x2 - x1))
    iy = int(100 * (y2 - y) / (y2 - y1))
    params = {
        "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetFeatureInfo",
        "LAYERS": layer, "QUERY_LAYERS": layer, "STYLES": "",
        "SRS": "EPSG:25833",
        "BBOX": "%f,%f,%f,%f" % (x1, y1, x2, y2),
        "WIDTH": "100", "HEIGHT": "100", "X": str(ix), "Y": str(iy),
        "INFO_FORMAT": "application/vnd.ogc.gml", "FEATURE_COUNT": "50",
    }
    key = "gfi2_%s_%d_%d_%d_%d_%d_%d" % (layer, x1, y1, x2, y2, ix, iy)
    return C.http_get(wms or WMS, params=params, cache_key=key, max_age_h=24 * 90,
                      polite=0.4, retries=3, timeout=90)


def parse_parcels(gml_text):
    """AX_Flurstueck-Elemente aus GML ziehen."""
    out = []
    if "AX_Flurstueck" not in gml_text:
        return out
    try:
        root = ET.fromstring(gml_text)
    except ET.ParseError:
        return out
    for fs in root.iter("{%s}AX_Flurstueck" % NS["adv"]):
        d = {"id": fs.get("{%s}id" % NS["gml"])}
        gem = fs.find("adv:gemarkung", NS)
        if gem is not None:
            d["gemarkung_nr"] = gem.findtext("adv:gemarkungsnummer", "", NS)
            land = gem.findtext("adv:land", "", NS)
            d["land"] = land
        fn = fs.find("adv:flurstuecksnummer", NS)
        if fn is not None:
            d["zaehler"] = fn.findtext("adv:zaehler", "", NS)
            d["nenner"] = fn.findtext("adv:nenner", "", NS)
        d["kennzeichen"] = fs.findtext("adv:flurstueckskennzeichen", "", NS)
        area = fs.findtext("adv:amtlicheFlaeche", "", NS)
        m = re.match(r"([\d.]+)", area)
        d["flaeche_m2"] = float(m.group(1)) if m else None
        d["entstehung"] = fs.findtext("adv:zeitpunktDerEntstehung", "", NS)
        gemz = fs.find("adv:gemeindezugehoerigkeit", NS)
        if gemz is not None:
            d["gemeinde"] = gemz.findtext("adv:gemeinde", "", NS)
            d["kreis"] = gemz.findtext("adv:kreis", "", NS)
        # Geometrie
        polys = []
        for pos in fs.iter():
            if not pos.tag.endswith("}posList"):
                continue
            vals = [float(v) for v in pos.text.split()]
            coords = list(zip(vals[0::2], vals[1::2]))
            if len(coords) >= 3:
                ll = [T_INV.transform(x, y) for x, y in coords]
                polys.append(ll)
        if polys:
            d["geometry"] = {"type": "Polygon", "coordinates": polys[:1]}
            if len(polys) > 1:
                d["geometry"] = {"type": "MultiPolygon",
                                 "coordinates": [[p] for p in polys]}
        out.append(d)
    return out


def attribute_parcels(site, plist):
    """Welche Flurstuecke gehoeren zum Platz? (Nachbar-/Seeflurstuecke raus.)
    Polygon-Platz: >5 % Ueberlappung mit OSM-Umriss. Punkt-Platz: Punkt im
    Flurstueck oder >25 % Ueberlappung mit 100-m-Umkreis. Beide Geometrien
    buffer(0) gegen Topologiefehler. Ergebnis: (gesamtflaeche|None);
    setzt p['zum_platz'] je Flurstueck."""
    from shapely.geometry import Point as _Pt
    g_site_ll = shape(json.loads(site["geometry"])) if site["geometry"] else None
    if g_site_ll is not None and not g_site_ll.is_valid:
        g_site_ll = g_site_ll.buffer(0)
    pt = _Pt(site["lon"], site["lat"])
    g_ref_ll = g_site_ll if g_site_ll is not None else pt.buffer(0.0009)  # ~100 m
    overlap_area = 0.0
    for p in plist:
        p["zum_platz"] = False
        f = p.get("flaeche_m2") or 0
        if not p.get("geometry"):
            # ohne Geometrie (MV-GFI): nur plausible Groessen zaehlen
            if 0 < f <= 100000:
                p["zum_platz"] = True
                overlap_area += f
            continue
        try:
            gp = shape(p["geometry"])
            if not gp.is_valid:
                gp = gp.buffer(0)
            inter = gp.intersection(g_ref_ll)
            share = inter.area / gp.area if gp.area else 0
            if g_site_ll is not None:
                belong = share > 0.05
            else:
                belong = gp.contains(pt) or share > 0.25
            if belong:
                p["zum_platz"] = True
                overlap_area += f
        except Exception:
            if 0 < f <= 300000:
                p["zum_platz"] = True
                overlap_area += f
    # ohne verwertbare Ueberlappung: keine Gesamtflaeche behaupten
    # (Riesen-Seeflurstuecke sind kein Camping-Grundstueck)
    return overlap_area if overlap_area > 0 else None


def sample_points(g_site, spacing=70):
    """Rasterpunkte innerhalb des Platzes + Schwerpunkt."""
    minx, miny, maxx, maxy = g_site.bounds
    pts = [(g_site.centroid.x, g_site.centroid.y)]
    nx = max(1, int((maxx - minx) / spacing) + 1)
    ny = max(1, int((maxy - miny) / spacing) + 1)
    nx, ny = min(nx, 8), min(ny, 8)
    for i in range(nx):
        for j in range(ny):
            x = minx + (i + 0.5) * (maxx - minx) / nx
            y = miny + (j + 0.5) * (maxy - miny) / ny
            if g_site.contains(Point(x, y)):
                pts.append((x, y))
    return pts


def run(region_name, workers=1):
    region = C.load_region(region_name)
    conn = C.init_db()
    sites = conn.execute(
        "SELECT * FROM sites WHERE region=?", (region_name,)).fetchall()
    done = {r["site_id"] for r in conn.execute(
        "SELECT site_id FROM enrichment WHERE parcels IS NOT NULL")}
    # bei Refresh/Retry: als leer markierte Plaetze erneut versuchen
    # (Kataster-Abdeckung waechst; '[]' = leer geprueft, NULL = nie versucht)
    if os.environ.get("CAMPING_REFRESH") or os.environ.get("CAMPING_RETRY_EMPTY"):
        done -= {r["site_id"] for r in conn.execute(
            "SELECT site_id FROM enrichment WHERE parcels='[]'")}
    sites = [s for s in sites if s["id"] not in done]
    conn.close()
    print("Plaetze ohne Flurstuecke:", len(sites), "(bereits erfasst:", len(done), ")")
    import threading
    from concurrent.futures import ThreadPoolExecutor
    counters = {"ok": 0, "empty": 0, "err": 0, "done": 0}
    lock = threading.Lock()

    def work(site):
        proj = C.make_projector(site["lat"], site["lon"])
        if site["geometry"]:
            g_site = transform(lambda x, y, z=None: proj(x, y),
                               shape(json.loads(site["geometry"])))
            if not g_site.is_valid:
                g_site = g_site.buffer(0)
        else:
            g_site = transform(lambda x, y, z=None: proj(x, y),
                               Point(site["lon"], site["lat"])).buffer(70)
        pts = sample_points(g_site)
        # zusaetzlich: eine grosse BBOX-Abfrage ueber den ganzen Platz
        inv = Transformer.from_crs(
            "+proj=aeqd +lat_0=%f +lon_0=%f +units=m +datum=WGS84" % (site["lat"], site["lon"]),
            "EPSG:4326", always_xy=True)
        minx, miny, maxx, maxy = g_site.bounds
        lon1, lat1 = inv.transform(minx, miny)
        lon2, lat2 = inv.transform(maxx, maxy)
        bx1, by1 = T_FWD.transform(lon1, lat1)
        bx2, by2 = T_FWD.transform(lon2, lat2)
        big_bbox = (min(bx1, bx2), min(by1, by2), max(bx1, bx2), max(by1, by2))
        cx, cy = (big_bbox[0] + big_bbox[2]) / 2, (big_bbox[1] + big_bbox[3]) / 2
        parcels = {}
        if region.get("alkis_schema") == "ave":
            # BB/SN/TH: eine WFS-BBOX-Abfrage ueber den ganzen Platz (+80m Puffer)
            padded = (big_bbox[0] - 80, big_bbox[1] - 80,
                      big_bbox[2] + 80, big_bbox[3] + 80)
            try:
                plist0 = fetch_parcels_ave(
                    region["alkis_wfs"], padded,
                    "alkisave_%s_%.4f_%.4f" % (region_name, site["lat"], site["lon"]),
                    wfs_version=region.get("alkis_wfs_version", "1.1.0"),
                    bbox_crs=region.get("alkis_bbox_crs", "25833"))
                g_site_ll = shape(json.loads(site["geometry"])) if site["geometry"] else None
                for p in plist0:
                    key = p.get("kennzeichen") or p.get("id")
                    if not key or key in parcels:
                        continue
                    if p.get("geometry") and g_site_ll is not None:
                        try:
                            if not shape(p["geometry"]).intersects(g_site_ll.buffer(0.0008)):
                                continue
                        except Exception:
                            pass
                    parcels[key] = p
            except Exception:
                with lock:
                    counters["err"] += 1
        else:
            # MV: WMS-GetFeatureInfo (GML), grosse BBOX + Rasterpunkte
            try:
                gml = gfi(cx, cy, bbox=big_bbox)
                for p in parse_parcels(gml):
                    key = p.get("kennzeichen") or p.get("id")
                    if key and key not in parcels:
                        # nur Flurstuecke, die den Platz wirklich beruehren
                        if p.get("geometry"):
                            gp = shape(p["geometry"])
                            g_site_ll = shape(json.loads(site["geometry"])) if site["geometry"] else None
                            if g_site_ll is None or gp.intersects(g_site_ll.buffer(0.0005)):
                                parcels[key] = p
                        else:
                            parcels[key] = p
            except Exception:
                with lock:
                    counters["err"] += 1
            for (px, py) in pts:
                # lokale AEQD -> zurueck nach lat/lon -> 25833
                inv = Transformer.from_crs(
                    "+proj=aeqd +lat_0=%f +lon_0=%f +units=m +datum=WGS84" % (site["lat"], site["lon"]),
                    "EPSG:4326", always_xy=True)
                lon, lat = inv.transform(px, py)
                x, y = T_FWD.transform(lon, lat)
                try:
                    gml = gfi(x, y)
                except Exception as ex:
                    with lock:
                        counters["err"] += 1
                    continue
                for p in parse_parcels(gml):
                    key = p.get("kennzeichen") or p.get("id")
                    if key and key not in parcels:
                        parcels[key] = p
        if parcels:
            plist = list(parcels.values())
            total_area = attribute_parcels(site, plist)
            sid = site["id"]
            ts = datetime.now(timezone.utc).isoformat()
            pj = json.dumps(plist, ensure_ascii=False)
            if total_area is None:
                # nichts Verwertbares -> Flurstuecke speichern, aber keine
                # Gesamtflaeche behaupten (zaehlt als 'leer geprueft')
                def _write_none(c, sid=sid, pj=pj):
                    c.execute("""UPDATE enrichment SET parcels=?, parcel_area_m2=NULL
                        WHERE site_id=?""", (pj, sid))
                C.db_write(_write_none)
                with lock:
                    counters["empty"] += 1
            else:
                def _write(c, pj=pj, total_area=total_area, ts=ts, sid=sid):
                    c.execute("""UPDATE enrichment SET parcels=?, parcel_area_m2=?,
                        updated=? WHERE site_id=?""", (pj, total_area, ts, sid))
                C.db_write(_write)
                with lock:
                    counters["ok"] += 1
        else:
            # leer: als 'leer geprueft' markieren (kein Endlos-Retry bei
            # jedem Lauf; --retry-leere / CAMPING_REFRESH holt sie zurueck)
            sid = site["id"]
            def _write_empty(c, sid=sid):
                c.execute("UPDATE enrichment SET parcels='[]' WHERE site_id=?", (sid,))
            C.db_write(_write_empty)
            with lock:
                counters["empty"] += 1
        with lock:
            counters["done"] += 1
            if counters["done"] % 10 == 0:
                print("... %d/%d (ok=%d leer=%d fehler=%d)" %
                      (counters["done"], len(sites), counters["ok"],
                       counters["empty"], counters["err"]), flush=True)

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, sites))
    else:
        for s in sites:
            work(s)
    print("Fertig: mit Flurstuecken=%d, ohne=%d, Einzelfehler=%d" % (
        counters["ok"], counters["empty"], counters["err"]), flush=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    workers = 1
    for a in sys.argv:
        if a.startswith("--workers"):
            workers = int(a.split("=")[1])
    run(args[0] if args else "seenplatte", workers)
