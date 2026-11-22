"""Schritt 16: Regions-Zuordnung pruefen (Bounding-Box ist rechteckig!).

Die BB/SN-BBOXen enthalten Randgebiete anderer Bundeslaender (z.B. BB-BBOX
schneidet Sachsen-Anhalt: Dessau, Wittenberg, Jersleber See...). Erkennbar
auch an weissen DOP-Kacheln (kein Bild ausserhalb des Landes).

Vorgehen:
  1. Alle Plaetze der Region mit weissem/leerem Luftbild (oder --all)
     per Nominatim-Reverse-Geocoding (1 req/s, gecacht) einem Bundesland
     zuordnen.
  2. Plaetze ausserhalb des Regions-Bundeslands bekommen region=<slug>
     (z.B. 'sachsen_anhalt') bzw. 'ausland' -> fallen aus allen
     Region-Abfragen/Exporten raus, Daten bleiben erhalten.
  3. Weisse Bilder von Plaetzen, die WIRKLICH im Land liegen, werden
     geloescht (s04/s12 holen sie neu bzw. Esri-Fallback).

Aufruf: python -m pipeline.s16_region_check brandenburg [--all]
"""
import json
import os
import sys
import time

from PIL import Image, ImageStat

from . import common as C

STATE_SLUGS = {
    "Brandenburg": "brandenburg",
    "Sachsen": "sachsen",
    "Sachsen-Anhalt": "sachsen_anhalt",
    "Mecklenburg-Vorpommern": "mecklenburg_vorpommern",
    "Thüringen": "thueringen",
    "Niedersachsen": "niedersachsen",
    "Bayern": "bayern",
    "Schleswig-Holstein": "schleswig_holstein",
    "Berlin": "berlin",
    "Hessen": "hessen",
    "Nordrhein-Westfalen": "nordrhein_westfalen",
    "Rheinland-Pfalz": "rheinland_pfalz",
    "Saarland": "saarland",
    "Baden-Württemberg": "baden_wuerttemberg",
    "Hamburg": "hamburg",
    "Bremen": "bremen",
}


def is_white(path):
    try:
        im = Image.open(path).convert("L")
        st = ImageStat.Stat(im)
        return st.stddev[0] < 12 or st.mean[0] > 240
    except Exception:
        return False


def reverse_state(lat, lon):
    key = "nominatim_rev_%.4f_%.4f" % (lat, lon)
    raw = C.http_get("https://nominatim.openstreetmap.org/reverse",
                     params={"lat": lat, "lon": lon, "format": "json",
                             "zoom": 5, "addressdetails": 1},
                     cache_key=key, max_age_h=24 * 180, polite=1.1,
                     timeout=60, headers={"User-Agent": "Campingplatzfinder/0.1 (research)"})
    j = json.loads(raw)
    a = j.get("address", {})
    return a.get("state", ""), a.get("country_code", "").upper()


def run(region_name, check_all=False):
    region = C.load_region(region_name)
    state = region.get("state")
    conn = C.init_db()
    sites = conn.execute("SELECT * FROM sites WHERE region=?", (region_name,)).fetchall()
    conn.close()
    meta_path = C.DATA / ("luftbild_meta_%s.json" % region_name)
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    todo = []
    for s in sites:
        m = meta.get(s["id"], {})
        f = m.get("file")
        white = bool(f) and is_white(C.OUTPUT / "luftbilder" / f)
        if check_all or white:
            todo.append((s, white))
    print("Zu pruefen: %d von %d (weisse Bilder bzw. --all)" % (len(todo), len(sites)))
    moved, kept, white_in_state = {}, 0, 0
    for i, (s, white) in enumerate(todo):
        try:
            st, cc = reverse_state(s["lat"], s["lon"])
        except Exception as e:
            print("  ! Nominatim", s["name"][:35], str(e)[:60])
            continue
        sid = s["id"]
        if cc and cc != "DE":
            new_region = "ausland_" + cc.lower()
        elif st and st != state:
            new_region = STATE_SLUGS.get(st, "unbekannt")
        else:
            new_region = None
        if new_region:
            def _move(c, sid=sid, nr=new_region):
                c.execute("UPDATE sites SET region=? WHERE id=?", (nr, sid))
            C.db_write(_move)
            moved[new_region] = moved.get(new_region, 0) + 1
            # Zugehoerige Bilder/Meta entfernen (falsches Land)
            if white:
                p = C.OUTPUT / "luftbilder" / (sid.replace("/", "_") + ".jpg")
                if p.exists():
                    p.unlink()
            print("  -> %-35s %s => %s" % (s["name"][:35], st or cc, new_region))
        else:
            kept += 1
            if white:
                white_in_state += 1
                # weisses Bild im eigenen Land: DOP-Abdeckungsluecke ->
                # Esri World Imagery als Ersatz holen
                p = C.OUTPUT / "luftbilder" / (sid.replace("/", "_") + ".jpg")
                if p.exists():
                    p.unlink()
                try:
                    d = 0.0025  # ~250 m
                    data = C.http_get(
                        "https://server.arcgisonline.com/ArcGIS/rest/services/"
                        "World_Imagery/MapServer/export",
                        params={"bbox": "%f,%f,%f,%f" % (s["lon"] - d, s["lat"] - d,
                                                          s["lon"] + d, s["lat"] + d),
                                "bboxSR": "4326", "imageSR": "4326",
                                "size": "1000,1000", "format": "jpg", "f": "image"},
                        binary=True, cache_key="esriakt_" + sid.replace("/", "_"),
                        max_age_h=24 * 90, polite=0.5, timeout=90)
                    if data[:2] == b"\xff\xd8":
                        p.write_bytes(data)
                        meta[sid] = {"file": p.name, "year": None,
                                     "quelle": "Esri World Imagery (DOP-Luecke)"}
                except Exception:
                    if sid in meta:
                        meta[sid] = {"error": "DOP weiss + Esri-Fallback fehlgeschlagen"}
        if (i + 1) % 25 == 0:
            print("... %d/%d" % (i + 1, len(todo)), flush=True)
    if meta:
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Fertig: verschoben=%s, im Land behalten=%d (davon weisse DOP: %d)" % (
        json.dumps(moved, ensure_ascii=False), kept, white_in_state))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run(args[0] if args else "brandenburg", "--all" in sys.argv)