"""Schritt 12: Bestandsalter schätzen – historische Luftbilder + Wayback Machine.

Quellen (alle frei):
  1. GeoPortal.MV DOP 1991 (s/w) und DOP 1953 – Vergleich mit aktuellem DOP20
     -> Bilder je Platz als Vergleichsstreifen (manuelle Sichtung Top-Leads).
  2. Wayback Machine (archive.org) der Platz-Website:
     - erstes Archivjahr (Platz-Alter / Online-Historie)
     - Mietunterkünfte (Mobilheim/Bungalow/...) im ältesten Snapshot
       -> "Bestand mind. X Jahre alt" = Erneuerungs-Opportunity.

Aufruf: python -m pipeline.s12_bestandsalter seenplatte [--top=30] [--no-images]
"""
import io
import json
import math
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

from . import common as C

DOP_SERVICES = {
    1953: ("https://www.geodaten-mv.de/dienste/dop1953_wms", "mv_dop1953"),
    1991: ("https://www.geodaten-mv.de/dienste/dop1991_wms", "mv_dop1991"),
}

ESRI_CONFIG = "https://s3-us-west-2.amazonaws.com/config.maptiles.arcgis.com/waybackconfig.json"
ESRI_YEARS = [2014, 2016, 2018, 2020, 2022, 2024]
_esri_cache = None


def esri_releases():
    """Je Zieljahr das letzte Wayback-Release (itemURL + Metadaten-Layer)."""
    global _esri_cache
    if _esri_cache is not None:
        return _esri_cache
    out = {}
    try:
        raw = C.http_get(ESRI_CONFIG, cache_key="esri_wayback_config",
                         max_age_h=24 * 30, timeout=90)
        j = json.loads(raw)
        by_year = {}
        for v in j.values():
            m = re.search(r"Wayback (\d{4})-(\d{2})-(\d{2})", v.get("itemTitle", ""))
            if m:
                by_year.setdefault(int(m.group(1)), []).append(
                    (m.group(0), v["itemURL"], v.get("metadataLayerUrl")))
        for y in ESRI_YEARS:
            if y in by_year:
                out[y] = sorted(by_year[y])[-1]
    except Exception:
        pass
    _esri_cache = out
    return out


def _tiles_for(lat, lon, z, half_m=250):
    """Tile-Indizes (WebMercator), die den Platz +/- half_m abdecken."""
    def tx(lon_, z_):
        return (lon_ + 180) / 360 * 2 ** z_
    def ty(lat_, z_):
        r = math.radians(lat_)
        return (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * 2 ** z_
    dlat = half_m / 111320
    dlon = half_m / (111320 * math.cos(math.radians(lat)))
    x0, x1 = int(tx(lon - dlon, z)), int(tx(lon + dlon, z))
    y0, y1 = int(ty(lat + dlat, z)), int(ty(lat - dlat, z))
    return x0, x1, y0, y1


def esri_capture_date(meta_url, lat, lon, year):
    """Echtes Aufnahmedatum (SRC_DATE) am Platz aus Esri-Metadaten."""
    if not meta_url:
        return None
    try:
        x = lon * 20037508.34 / 180
        y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180) * 20037508.34 / 180
        for layer in (4, 5, 6, 7):  # 30cm .. 2.4m Aufloesung
            params = {"f": "json",
                      "geometry": json.dumps({"xmin": x - 800, "ymin": y - 800,
                                              "xmax": x + 800, "ymax": y + 800,
                                              "spatialReference": {"wkid": 3857}}),
                      "geometryType": "esriGeometryEnvelope", "inSR": "3857",
                      "spatialRel": "esriSpatialRelIntersects",
                      "outFields": "SRC_DATE", "returnGeometry": "false"}
            raw = C.http_get(meta_url + "/%d/query" % layer, params=params,
                             cache_key="esri_meta_%d_%d_%.4f_%.4f" % (year, layer, lat, lon),
                             max_age_h=24 * 90, polite=0.3, timeout=60)
            feats = json.loads(raw).get("features", [])
            dates = sorted({f["attributes"]["SRC_DATE"] for f in feats
                            if f.get("attributes", {}).get("SRC_DATE")})
            if dates:
                d = str(dates[-1])
                return "%s-%s-%s" % (d[:4], d[4:6], d[6:8])
    except Exception:
        pass
    return None


def esri_hist_image(lat, lon, year, site_id, releases):
    """Wayback-Luftbild als Tile-Mosaik (z16, ~500m Ausschnitt)."""
    rel = releases.get(year)
    if not rel:
        return None, None
    from PIL import Image
    _, item_url, meta_url = rel
    z = 16
    x0, x1, y0, y1 = _tiles_for(lat, lon, z)
    parts = {}
    for xt in range(x0, x1 + 1):
        for yt in range(y0, y1 + 1):
            u = item_url.replace("{level}", str(z)).replace("{row}", str(yt)).replace("{col}", str(xt))
            try:
                data = C.http_get(u, binary=True,
                                  cache_key="esri_tile_%d_%d_%d_%d" % (year, z, yt, xt),
                                  max_age_h=24 * 365, polite=0.2, timeout=60)
                if data[:2] == b"\xff\xd8":
                    parts[(xt, yt)] = Image.open(io.BytesIO(data))
            except Exception:
                pass
    if not parts:
        return None, None
    w = (x1 - x0 + 1) * 256
    h = (y1 - y0 + 1) * 256
    canvas = Image.new("RGB", (w, h), (240, 240, 240))
    for (xt, yt), im in parts.items():
        canvas.paste(im, ((xt - x0) * 256, (yt - y0) * 256))
    out = C.OUTPUT / "luftbilder_hist"
    out.mkdir(exist_ok=True)
    path = out / ("%s_esri%d.jpg" % (site_id.replace("/", "_"), year))
    canvas.save(path, quality=85)
    cap = esri_capture_date(meta_url, lat, lon, year)
    return "luftbilder_hist/%s" % path.name, cap


def hist_image(lat, lon, year, site_id, service, half_m=250):
    """Historisches Luftbild (JPEG) um den Platz, EPSG:25833."""
    from pyproj import Transformer
    T = Transformer.from_crs("EPSG:4326", "EPSG:25833", always_xy=True)
    x, y = T.transform(lon, lat)
    url, layer = service
    params = {
        "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetMap",
        "LAYERS": layer, "STYLES": "", "SRS": "EPSG:25833",
        "BBOX": "%f,%f,%f,%f" % (x - half_m, y - half_m, x + half_m, y + half_m),
        "WIDTH": "700", "HEIGHT": "700", "FORMAT": "image/jpeg",
    }
    key = "dop%d_%s" % (year, site_id.replace("/", "_"))
    try:
        data = C.http_get(url, params=params, binary=True, cache_key=key,
                          max_age_h=24 * 365, polite=0.5, timeout=120)
        if data[:2] == b"\xff\xd8":
            out = C.OUTPUT / "luftbilder_hist"
            out.mkdir(exist_ok=True)
            path = out / ("%s_%d.jpg" % (site_id.replace("/", "_"), year))
            path.write_bytes(data)
            return "luftbilder_hist/%s" % path.name
    except Exception:
        pass
    return None


def wayback_history(website, site_id):
    """Archiv-Snapshots der Website: Jahre + Unterkünfte im ältesten Snapshot."""
    host = urlparse(website if "//" in website else "http://" + website).netloc
    host = host.replace("www.", "")
    if not host:
        return {}
    out = {}
    try:
        params = {"url": host, "output": "json", "limit": "60",
                  "collapse": "timestamp:4", "filter": "statuscode:200"}
        raw = C.http_get("http://web.archive.org/cdx/search/cdx", params=params,
                         cache_key="wb_cdx_" + host.replace(".", "_"),
                         max_age_h=24 * 90, polite=1.0, timeout=90)
        rows = json.loads(raw)
        if len(rows) > 1:
            snaps = rows[1:]
            years = sorted({r[1][:4] for r in snaps})
            out["archiv_jahre"] = years
            out["erstes_archiv"] = years[0]
            # aeltester Snapshot: Unterkunfts-Typen?
            first = snaps[0]
            wurl = "http://web.archive.org/web/%sid_/%s" % (first[1], first[2])
            try:
                html = C.http_get(wurl, cache_key="wb_page_%s_%s" % (
                    host.replace(".", "_"), first[1]), max_age_h=24 * 365,
                    polite=1.0, timeout=90)
                text = re.sub(r"<[^>]+>", " ", html)
                types = []
                for label, pat in (("Mobilheim", r"mobilheim|mobile\s*home"),
                                   ("Bungalow", r"bungalow"),
                                   ("Ferienhaus", r"ferienh(?:au|ä)s(?:er|user)?"),
                                   ("Ferienwohnung", r"ferienwohnung"),
                                   ("Hütte", r"h(?:ü|ue)tte"),
                                   ("Wohnwagen mietbar", r"mietwohnwagen|wohnwagen\s+miet")):
                    if re.search(pat, text, re.I):
                        types.append(label)
                if types:
                    out["bestand_seit"] = int(years[0])
                    out["bestand_typen_alt"] = types
            except Exception:
                pass
            # mittlerer Snapshot (~10 Jahre her) fuer Vergleich
            now = datetime.now().year
            mid = [r for r in snaps if int(r[1][:4]) <= now - 8]
            if mid:
                m = mid[len(mid) // 2]
                wurl2 = "http://web.archive.org/web/%sid_/%s" % (m[1], m[2])
                try:
                    html2 = C.http_get(wurl2, cache_key="wb_page_%s_%s" % (
                        host.replace(".", "_"), m[1]), max_age_h=24 * 365,
                        polite=1.0, timeout=90)
                    text2 = re.sub(r"<[^>]+>", " ", html2)
                    types2 = [t for t, pat in (
                        ("Mobilheim", r"mobilheim|mobile\s*home"),
                        ("Bungalow", r"bungalow"),
                        ("Ferienhaus", r"ferienh(?:au|ä)s(?:er|user)?"))
                        if re.search(pat, text2, re.I)]
                    if types2:
                        out["bestand_%s" % m[1][:4]] = types2
                except Exception:
                    pass
    except Exception:
        pass
    return out


def age_verdict(wb):
    if not wb.get("bestand_seit"):
        return None
    now = datetime.now().year
    age = now - wb["bestand_seit"]
    types = ", ".join(wb.get("bestand_typen_alt", []))
    return "%s bereits %d im Website-Archiv (mind. %d Jahre alt) – Erneuerungs-Kandidat" % (
        types, wb["bestand_seit"], age)


def run(region_name, top=None, images=True):
    region = C.load_region(region_name)
    hist_services = region.get("hist_dop", {})
    if not hist_services and region.get("state") == "Mecklenburg-Vorpommern":
        hist_services = {str(y): v for y, v in DOP_SERVICES.items()}
    conn = C.init_db()
    sites = conn.execute("""SELECT s.id, s.name, s.lat, s.lon, s.website,
        e.rentals, e.lead_score FROM sites s JOIN enrichment e ON s.id=e.site_id
        WHERE s.region=? ORDER BY e.lead_score DESC NULLS LAST""",
        (region_name,)).fetchall()
    if top:
        sites = sites[:top]
    print("Plätze:", len(sites))
    releases = esri_releases() if images else {}
    print("Esri-Wayback-Releases:", ", ".join(str(y) for y in sorted(releases)))
    conn.close()
    import threading
    from concurrent.futures import ThreadPoolExecutor
    counters = {"img": 0, "wb": 0, "done": 0}
    lock = threading.Lock()

    def work(site):
        sid = site["id"]
        info = {}
        n_img = n_wb = 0
        if images:
            imgs = {}
            for year, service in sorted(hist_services.items()):
                rel = hist_image(site["lat"], site["lon"], int(year), sid, service)
                if rel:
                    imgs[str(year)] = rel
            caps = {}
            for year in sorted(releases):
                rel, cap = esri_hist_image(site["lat"], site["lon"], year, sid, releases)
                if rel:
                    imgs[str(year)] = rel
                    if cap:
                        caps[str(year)] = cap
            if imgs:
                info["hist_luftbilder"] = imgs
                if caps:
                    info["esri_aufnahmedaten"] = caps
                n_img += 1
        if site["website"]:
            wb = wayback_history(site["website"], sid)
            if wb:
                info["wayback"] = wb
                n_wb += 1
        if not info:
            with lock:
                counters["done"] += 1
            return
        verdict = age_verdict(info.get("wayback", {}))
        ij = json.dumps(info, ensure_ascii=False)
        ts = datetime.now(timezone.utc).isoformat()
        def _write(c, sid=sid, ij=ij, ts=ts, verdict=verdict):
            if verdict:
                c.execute("UPDATE enrichment SET rental_age_est=?, updated=? WHERE site_id=?",
                          (verdict, ts, sid))
            else:
                c.execute("UPDATE enrichment SET updated=? WHERE site_id=?", (ts, sid))
        C.db_write(_write)
        # separate Tabelle fuer die Rohinfo (JSON)
        def _write2(c, sid=sid, ij=ij):
            c.execute("""CREATE TABLE IF NOT EXISTS history_info
                (site_id TEXT PRIMARY KEY, info TEXT)""")
            c.execute("INSERT OR REPLACE INTO history_info VALUES (?,?)", (sid, ij))
        C.db_write(_write2)
        with lock:
            counters["img"] += n_img
            counters["wb"] += n_wb
            counters["done"] += 1
            print("  %2d/%d %-40s Bilder:%s Wayback:%s" % (
                counters["done"], len(sites), site["name"][:40],
                ",".join(info.get("hist_luftbilder", {})) or "-",
                (info.get("wayback", {}).get("erstes_archiv") or "-")), flush=True)

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
    print("Fertig: hist. Bilder=%d, Wayback=%d" % (counters["img"], counters["wb"]), flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    region = args[0] if args else "seenplatte"
    top = None
    images = True
    for a in args[1:]:
        if a.startswith("--top="):
            top = int(a.split("=")[1])
        if a == "--no-images":
            images = False
    run(region, top=top, images=images)