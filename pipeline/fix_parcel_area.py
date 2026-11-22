"""Korrigiert parcel_area_m2: nur Flurstuecke mit >5% Ueberlappung zaehlen.
Nutzt die bereits gecachten GFI-Antworten (schnell, keine neuen Requests).

Aufruf: python -m pipeline.fix_parcel_area seenplatte
"""
import json
import sys
from datetime import datetime, timezone

from shapely.geometry import shape

from . import common as C


def run(region_name):
    conn = C.init_db()
    rows = conn.execute("""SELECT s.id, s.geometry, e.parcels FROM sites s
        JOIN enrichment e ON s.id=e.site_id
        WHERE s.region=? AND e.parcels IS NOT NULL""", (region_name,)).fetchall()
    n_fix = 0
    for r in rows:
        if not r["geometry"]:
            continue
        g_site = shape(json.loads(r["geometry"]))
        plist = json.loads(r["parcels"])
        changed = False
        total = 0.0
        for p in plist:
            if p.get("geometry"):
                try:
                    gp = shape(p["geometry"])
                    inter = gp.intersection(g_site)
                    share = inter.area / gp.area if gp.area else 0
                    belongs = share > 0.05
                except Exception:
                    belongs = True
            else:
                belongs = True
            if p.get("zum_platz") != belongs:
                changed = True
            p["zum_platz"] = belongs
            if belongs:
                total += p.get("flaeche_m2") or 0
        if total > 0:
            sid = r["id"]
            pj = json.dumps(plist, ensure_ascii=False)
            ts = datetime.now(timezone.utc).isoformat()
            def _write(c):
                c.execute("UPDATE enrichment SET parcels=?, parcel_area_m2=?, updated=? WHERE site_id=?",
                          (pj, total, ts, sid))
            C.db_write(_write)
            n_fix += 1
    print("Aktualisiert:", n_fix)
    conn.close()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "seenplatte")
