"""Schritt 15: KI-Bildsichtung der Luftbilder – 'was steht da, in welchem Zustand?'

Zweistufig (bewusst KEIN unbeaufsichtigtes ML-Modell):
  1. Dieses Skript sammelt die Bildpfade + amtlichen ALKIS-Gebaeudedaten
     der Top-Plaetze und legt eine Sichtungs-Liste an
     (data/bildsichtung_<region>.json, Status 'offen').
  2. Der Agent (Multimodal-KI) sieht die Bilder an und schreibt je Platz
     eine strukturierte Bewertung zurueck:
       - bestand_typen: was steht da (Mobilheime, Bungalows, Sanitaer, ...)
       - anzahl_geschaetzt: Groessenordnung
       - zustand: gepflegt / mittel / erneuerungsbeduerftig + Begruendung
       - auffaelligkeiten: Leerstand, Zuwachs seit aelteren Bildern, etc.
  3. Erneuter Lauf dieses Skripts uebernimmt fertige Sichtungen in
     enrichment.rental_age_est-Ergaenzung bzw. eigenes Feld 'bildsichtung'
     und Excel/Dossiers zeigen sie.

Aufruf: python -m pipeline.s15_bildsichtung brandenburg [--top=20]
"""
import json
import sys
from datetime import datetime, timezone

from . import common as C


def run(region_name, top=20):
    conn = C.init_db()
    rows = conn.execute("""SELECT s.id, s.name, s.lat, s.lon, e.buildings,
        e.lead_score FROM sites s JOIN enrichment e ON s.id=e.site_id
        WHERE s.region=? ORDER BY e.lead_score DESC LIMIT ?""",
        (region_name, top)).fetchall()
    hist = {}
    try:
        hist = {r["site_id"]: json.loads(r["info"]) for r in
                conn.execute("SELECT site_id, info FROM history_info")}
    except Exception:
        pass
    meta_path = C.DATA / ("luftbild_meta_%s.json" % region_name)
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    path = C.DATA / ("bildsichtung_%s.json" % region_name)
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    out = {}
    n_done = 0
    for r in rows:
        sid = r["id"]
        prev = existing.get(sid, {})
        imgs = {"aktuell": "luftbilder/%s" % meta.get(sid, {}).get("file", "")}
        for y, rel in sorted(hist.get(sid, {}).get("hist_luftbilder", {}).items()):
            imgs[y] = rel
        entry = {
            "name": r["name"], "lat": r["lat"], "lon": r["lon"],
            "score": r["lead_score"],
            "bilder": {k: v for k, v in imgs.items() if v and (C.OUTPUT / v).exists()},
            "alkis_gebaeude": json.loads(r["buildings"]) if r["buildings"] else None,
            "status": prev.get("status", "offen"),
        }
        if prev.get("sichtung"):
            entry["sichtung"] = prev["sichtung"]
            entry["status"] = "gesichtet"
            n_done += 1
        out[sid] = entry
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    # fertige Sichtungen in die DB spiegeln
    for sid, e in out.items():
        if e.get("status") == "gesichtet" and e.get("sichtung"):
            sj = json.dumps(e["sichtung"], ensure_ascii=False)
            ts = datetime.now(timezone.utc).isoformat()
            def _write(c, sid=sid, sj=sj, ts=ts):
                cols = {x[1] for x in c.execute("PRAGMA table_info(enrichment)")}
                if "bildsichtung" not in cols:
                    c.execute("ALTER TABLE enrichment ADD COLUMN bildsichtung TEXT")
                c.execute("UPDATE enrichment SET bildsichtung=?, updated=? WHERE site_id=?",
                          (sj, ts, sid))
            C.db_write(_write)
    print("Sichtungs-Liste:", path)
    print("Plaetze: %d, davon gesichtet: %d, offen: %d" % (len(out), n_done, len(out) - n_done))
    conn.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    top = 20
    for a in sys.argv:
        if a.startswith("--top="):
            top = int(a.split("=")[1])
    run(args[0] if args else "brandenburg", top)