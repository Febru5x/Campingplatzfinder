# Deployment & Hosting – wie alles online kommt

## Einrichtung (einmalig, erledigt am 2026-11-23)

- **GitHub-Repo:** https://github.com/Febru5x/Campingplatzfinder (public, kostenlos)
- **Hosting:** GitHub Pages aus dem Ordner `docs/` (Branch `main`).
  Aktiviert per `gh api repos/Febru5x/Campingplatzfinder/pages -f ...`.
- **Live-URL:** https://febru5x.github.io/Campingplatzfinder/
  Funktioniert auf jedem Endgerät (Handy/Tablet/PC), kein Server, kein Abo.
- **Lokales Repo:** `C:\Users\bruen\Campingplatzfinder`
  (Code = Kopie von `%LOCALAPPDATA%\Campingplatzfinder\code`;
  Arbeitsdaten bleiben in `%LOCALAPPDATA%`, siehe pipeline/common.py).

## Was online ist (docs/)

| Inhalt | Quelle |
|---|---|
| index.html (Übersicht, mobilfreundlich) | tools/build_site.py |
| karte_<region>.html ×5 (Leaflet, DOP/ALKIS/ARIS live) | output/ |
| campingplaetze_<region>.xlsx ×5 | output/ |
| dossiers/<region>/ (Top-20 HTML) ×5 | output/ |
| luftbilder/ + luftbilder_hist/ (Web-komprimiert ≤800px q60 / 600px q55) | output/, Pillow |
| daten/camping.db (VACUUM-Kopie; ohne parcels-Rohgeometrien, die bleiben lokal) | data/ |
| daten/marktpreise_*.json, bildsichtung_*.json | data/ |
| BAUAMT_VORLAGEN.md | output/ |

Originale Luftbilder (345 MB) bleiben lokal; Web-Version ~100 MB.
GitHub Pages: Soft-Limit 1 GB pro Site, 100 GB Traffic/Monat – locker ausreichend.

## Update-Workflow (nach Pipeline-Läufen)

```bat
cd C:\Users\bruen\Campingplatzfinder
:: 1. Code-Änderungen aus der Arbeitskopie übernehmen (falls geändert):
robocopy "%LOCALAPPDATA%\Campingplatzfinder\code\pipeline" pipeline /E /XD __pycache__ /R:2 /W:2
robocopy "%LOCALAPPDATA%\Campingplatzfinder\code\config" config /E /R:2 /W:2
copy "%LOCALAPPDATA%\Campingplatzfinder\code\STATUS.md" .
copy "%LOCALAPPDATA%\Campingplatzfinder\code\DATENQUELLEN.md" .
:: 2. Site bauen (nur neue/fehlende Bilder werden komprimiert):
python -m tools.build_site
:: 3. Veröffentlichen:
git add -A
git commit -m "Daten-Update <Datum>"
git push
```

Pages baut automatisch neu (1–2 Min). --full erzwingt Neu-Komprimierung ALLER Bilder.

## Grenzen / Hinweise

- Karten laden DOP/ALKIS/ARIS-Kacheln live von den Landes-Servern →
  deren Verfügbarkeit gilt auch online (ST-ImageServer-Workaround aktiv).
- Die SQLite-DB ist ein Download (kein Online-Query); für Ad-hoc-Abfragen
  lokal nutzen oder DB-Browser-Apps (z. B. DB Browser for SQLite).
- Keine personenbezogenen Geheimnisse im Repo (geprüft); Kontaktdaten der
  Plätze sind öffentlich (Websites/OSM) und Teil des Geschäftszwecks.
- Repo public = jeder kann Karten/Daten sehen. Falls später privat gewünscht:
  Pages ginge dann nur mit GitHub Pro (kostenpflichtig) – Alternative wäre
  Cloudflare Pages (kostenlos, auch für private Repos, eigener Build nötig).
