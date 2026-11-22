"""Baut das oeffentliche GitHub-Pages-Site aus dem lokalen Output.

- Kopiert Karten/Excel/Dossiers/Vorlagen nach docs/
- Komprimiert ALLE Luftbilder (aktuell + historisch) als Web-JPEG
  (max 1000px, Qualitaet 72) nach docs/luftbilder* -> ~30-60 MB statt 345 MB
- Schreibt docs/daten/camping.db (Kopie) + kleine JSON-Daten
- Erzeugt docs/index.html (Uebersicht mit Links je Region)

Aufruf:  python -m tools.build_site [--full]
  --full: Bilder auch neu komprimieren, wenn Ziel schon existiert
Danach:  git add docs && git commit && git push  (GitHub Pages = /docs)
"""
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import common as C  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
REGIONS = ["seenplatte", "brandenburg", "sachsen",
           "sachsen_anhalt", "thueringen"]
LABELS = {"seenplatte": "Seenplatte (MV-Pilot)", "brandenburg": "Brandenburg",
          "sachsen": "Sachsen", "sachsen_anhalt": "Sachsen-Anhalt",
          "thueringen": "Thüringen"}


def compress_images(src_dir, dst_dir, full=False, maxpx=1000, quality=72):
    dst_dir.mkdir(parents=True, exist_ok=True)
    n_new = n_skip = 0
    files = sorted(src_dir.glob("*.jpg"))
    for f in files:
        out = dst_dir / f.name
        if out.exists() and not full:
            n_skip += 1
            continue
        try:
            im = Image.open(f)
            im = im.convert("RGB")
            if max(im.size) > maxpx:
                r = maxpx / max(im.size)
                im = im.resize((round(im.width * r), round(im.height * r)),
                               Image.LANCZOS)
            im.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
            n_new += 1
        except Exception as e:
            print("  FEHLER", f.name, e)
        if (n_new + n_skip) % 400 == 0:
            print("  ... %d/%d" % (n_new + n_skip, len(files)))
    print("  %s: neu=%d uebersprungen=%d" % (dst_dir.name, n_new, n_skip))


def build_index():
    import sqlite3
    conn = sqlite3.connect(DOCS / "daten" / "camping.db")
    stats = {}
    for reg in REGIONS:
        try:
            n, w, s = conn.execute("""SELECT COUNT(*),
                SUM(CASE WHEN e.water_distance_m<=50 THEN 1 ELSE 0 END),
                SUM(CASE WHEN e.lead_score>=70 THEN 1 ELSE 0 END)
                FROM sites s JOIN enrichment e ON s.id=e.site_id
                WHERE s.region=?""", (reg,)).fetchone()
            stats[reg] = (n or 0, w or 0, s or 0)
        except Exception:
            stats[reg] = (0, 0, 0)
    conn.close()
    cards = []
    for reg in REGIONS:
        xlsx = "campingplaetze_%s.xlsx" % reg
        karte = "karte_%s.html" % reg
        if not (DOCS / karte).exists():
            continue
        n_doss = len(list((DOCS / "dossiers" / reg).glob("*.html"))) \
            if (DOCS / "dossiers" / reg).exists() else 0
        doss_link = ('<a href="dossiers/%s/%s">Top-20-Dossiers</a>' % (reg, _first_dossier(reg))) if n_doss else ""
        n, w, s = stats.get(reg, (0, 0, 0))
        cards.append("""
    <div class="card">
      <h2>%s</h2>
      <p class="stats">%d Pl&auml;tze &middot; %d direkt am Wasser &middot; %d Top-Leads (Score &ge;70)</p>
      <p><a class="btn" href="%s">Interaktive Karte</a></p>
      <p><a href="%s">Excel-Tabelle</a> &middot; %s</p>
    </div>""" % (LABELS[reg], n, w, s, karte, xlsx, doss_link))
    html = """<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Campingplatzfinder</title>
<meta name="description" content="Campingplätze mit Wasserzugang in Ostdeutschland: interaktive Karten, Luftbilder, Flurstücke, B-Pläne, Marktpreise und Lead-Scores für 1.481 Plätze.">
<meta property="og:title" content="Campingplatzfinder">
<meta property="og:description" content="1.481 Campingplätze mit Wasserzugang – Karten, Luftbilder, Bebaubarkeit, Marktpreise.">
<meta property="og:type" content="website">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>&#9978;</text></svg>">
<style>
 body{font-family:system-ui,sans-serif;margin:0;background:#f4f6f8;color:#222}
 header{background:#1a5276;color:#fff;padding:24px 16px;text-align:center}
 header h1{margin:0 0 6px} header p{margin:0;opacity:.85}
 main{max-width:960px;margin:24px auto;padding:0 16px}
 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}
 .card{background:#fff;border-radius:10px;padding:18px;box-shadow:0 1px 4px rgba(0,0,0,.12)}
 .card h2{margin:0 0 10px;font-size:1.15em}
 .stats{color:#555;font-size:.9em;margin:0 0 12px}
 .btn{display:inline-block;background:#1a5276;color:#fff;padding:8px 14px;border-radius:6px;text-decoration:none}
 a{color:#1a5276}
 .note{background:#fff;border-radius:10px;padding:16px;margin-top:20px;box-shadow:0 1px 4px rgba(0,0,0,.12)}
 footer{text-align:center;color:#777;font-size:.85em;padding:24px}
</style></head><body>
<header><h1>Campingplatzfinder</h1>
<p>Campingpl&auml;tze mit Wasserzugang in Ostdeutschland &ndash; Stand 22.11.2026</p></header>
<main>
 <div class="grid">%s
 </div>
 <div class="note">
  <b>Daten:</b> <a href="daten/camping.db">SQLite-Datenbank</a> (alle Regionen, Anreicherungen, Scores)
  &middot; <a href="BAUAMT_VORLAGEN.md">Bauamt-Vorlagen</a><br>
  <b>Methode:</b> OSM-Grundliste &rarr; Wasseranalyse &rarr; Flurst&uuml;cke (ALKIS) &rarr;
  Luftbilder + Historie &rarr; Website-Scrape &rarr; B-Pl&auml;ne &rarr; KI-Bildsichtung &rarr;
  Marktpreise &rarr; Lead-Score. Details im <a href="https://github.com/Febru5x/Campingplatzfinder">GitHub-Repo</a>.<br>
  <b>Hinweis:</b> KI-Bildsichtungen sind Luftbildeindr&uuml;cke, keine Rechtsberatung.
  Datenquellen: OSM (ODbL), Landesvermessungs&auml;mter (dl-de/by-2-0 bzw. freie Nutzung), Esri Wayback.
 </div>
</main>
<footer>Campingplatzfinder &middot; erstellt mit Python + Leaflet</footer>
</body></html>""" % "\n".join(cards)
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    print("index.html geschrieben")


def _first_dossier(reg):
    files = sorted((DOCS / "dossiers" / reg).glob("*.html"))
    return files[0].name if files else ""


def main():
    full = "--full" in sys.argv
    DOCS.mkdir(exist_ok=True)
    (DOCS / "daten").mkdir(exist_ok=True)

    # 1) Karten, Excel, Dossiers, Vorlagen
    for reg in REGIONS:
        for name in ("karte_%s.html" % reg, "campingplaetze_%s.xlsx" % reg):
            src = C.OUTPUT / name
            if src.exists():
                shutil.copy2(src, DOCS / name)
        dsrc = C.OUTPUT / "dossiers" / reg
        if dsrc.exists():
            shutil.copytree(dsrc, DOCS / "dossiers" / reg, dirs_exist_ok=True)
    v = C.OUTPUT / "BAUAMT_VORLAGEN.md"
    if v.exists():
        shutil.copy2(v, DOCS / v.name)
    print("Karten/Excel/Dossiers kopiert")

    # 2) Luftbilder komprimiert (Web: 800px q60; Hist kleiner)
    print("Luftbilder komprimieren (aktuell)...")
    compress_images(C.OUTPUT / "luftbilder", DOCS / "luftbilder", full,
                    maxpx=800, quality=60)
    print("Luftbilder komprimieren (historisch)...")
    compress_images(C.OUTPUT / "luftbilder_hist", DOCS / "luftbilder_hist", full,
                    maxpx=600, quality=55)

    # 3) Datenbank (VACUUM-Kopie) + kleine JSONs
    # parcels-Geometrien sind 54 MB und auf der Karte nicht noetig
    # (ALKIS-WMS live); online-Version ohne parcels, Originale lokal.
    import sqlite3
    dst_db = DOCS / "daten" / "camping.db"
    if dst_db.exists():
        dst_db.unlink()
    src = sqlite3.connect(C.DB_PATH)
    dst = sqlite3.connect(dst_db, isolation_level=None)
    src.backup(dst)
    dst.execute("UPDATE enrichment SET parcels=NULL")
    dst.execute("VACUUM")
    dst.close()
    src.close()
    for f in C.DATA.glob("marktpreise_*.json"):
        shutil.copy2(f, DOCS / "daten" / f.name)
    for f in C.DATA.glob("bildsichtung_*.json"):
        shutil.copy2(f, DOCS / "daten" / f.name)
    print("DB + JSONs kopiert")

    build_index()
    total = sum(f.stat().st_size for f in DOCS.rglob("*") if f.is_file()) / 1e6
    print("docs/ gesamt: %.1f MB" % total)


if __name__ == "__main__":
    main()
