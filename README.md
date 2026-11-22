# Campingplatzfinder

Wiederverwendbare Python-Pipeline, die **Campingplätze mit Wasserzugang** findet,
anreichert und für Partnerschaften bewertet (Hausboot-/Tiny-House-Vermietung auf
Campingplätzen). Aktuell ausgewertet: **Seenplatte (MV), Brandenburg, Sachsen,
Sachsen-Anhalt, Thüringen** – 1.481 Plätze.

**Live ansehen (ohne Installation, auch mobil):**
👉 https://febru5x.github.io/Campingplatzfinder/

Dort: interaktive Karten je Region (Luftbilder, Flurstücke, B-Pläne, historische
Luftbilder, KI-Bildsichtung, Rechenbeispiele), Excel-Tabellen, Top-20-Dossiers
und die komplette SQLite-Datenbank zum Download.

## Was die Pipeline je Platz liefert

| Schritt | Inhalt | Quelle |
|---|---|---|
| s01 | Grundliste aller Campingplätze/Stellplätze | OpenStreetMap (Overpass) |
| s02 | Wasseranalyse: Abstand, Uferlänge, Steg, Motorboot, Schutzgebiet | OSM |
| s03 | Flurstücke + Flächen ( Kataster) | ALKIS-WFS der Länder |
| s04 | Aktuelles Luftbild (DOP20) + Befliegungsjahr | Landesvermessung |
| s05 | Website-Scrape: Mietunterkünfte, Preise, Kontakte (Fallback: Browser-UA → Wayback) | Betreiber-Websites |
| s06 | Lead-Score + Umsatz-Rechenbeispiele | eigene Gewichtung |
| s07 | Excel + interaktive Leaflet-Karte | – |
| s08 | Top-20-Dossiers (HTML) | – |
| s09 | Regions-Report | – |
| s11 | Bebauungspläne inkl. OCR der Plan-PDFs | Landesplanungsportale |
| s12 | Bestandsalter: hist. Luftbilder 2014–2024 + Wayback-Website | Esri Wayback |
| s13 | Markt-Benchmarks (Tiny-Haus/Hausboot €/Nacht) | Booking/Airbnb (echter Browser) |
| s14 | ALKIS-Gebäude: Anzahl, Fläche, Nutzungstypen | ALKIS-WFS |
| s15 | KI-Bildsichtung der Top-20 (Bestand/Zustand/Hebel) | DOP + Agent |
| s16 | Bundesland-Check (Grenzfälle) | Nominatim |

## Schnellstart (Pipeline lokal laufen lassen)

```bat
pip install requests pandas openpyxl pillow shapely pyproj
python -m pipeline.run_all brandenburg          :: alle Schritte
python -m pipeline.run_all thueringen --only=s05,s06,s07
```

- Daten/Output landen in `%LOCALAPPDATA%\Campingplatzfinder\{data,output}`
  (überlebt Code-Updates; konfigurierbar in `pipeline/common.py`).
- Regionen + alle Geo-Dienst-Adapter: `config/regions.json`
  (neue Bundesländer = neuer Eintrag, Details in `DATENQUELLEN.md`).
- Projekt-Status/Ergebnisse: `STATUS.md` · Datenquellen & Quirks: `DATENQUELLEN.md`.

## Website aktualisieren (GitHub Pages)

```bat
python -m tools.build_site        :: docs/ aus output/ bauen (Bilder komprimiert)
git add -A && git commit -m "Update" && git push
```

GitHub Pages serviert den Ordner `docs/` (Settings → Pages → Branch `main`,
Ordner `/docs`). Luftbilder werden fürs Web auf ≤1000 px / JPEG q72 komprimiert
(~345 MB → ~40 MB); die Originale bleiben lokal.

## Rechtliches / Datenlizenzen

- OpenStreetMap-Daten: © OpenStreetMap-Mitwirkende, ODbL.
- Amtliche Geodaten (DOP/ALKIS/B-Pläne): freie Nutzung gemäß den jeweiligen
  Landesbedingungen (z. B. Datenlizenz Deutschland – Namensnennung 2.0).
- Esri Wayback: © Esri & Partner, nur zur Ansicht/Auswertung.
- KI-Bildsichtungen sind Luftbildeindrücke, keine verbindliche Bestandsaufnahme;
  Bebaubarkeit immer mit dem Bauamt klären (`docs/BAUAMT_VORLAGEN.md`).
