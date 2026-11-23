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
| s17 | Datenqualität: Klassifizierung (Camping/Stellplatz/Verein/Sonstiges), Online-Präsenz-Check, Hausboot-Gewässer-Eignung; Default-Ausblendung von Nicht-Leads | eigene Heuristik + Sichtungen |
| s18 | Gewässerflächen: Fläche des nächsten Gewässers in ha (einheitliche Basis der Hausboot-Eignung, ≥5 ha) | OSM-Geometrie |
| s19 | Website-Modernität (0–10): Proxy für Investitionsbereitschaft; ersetzt reine Erreichbarkeit im Score | HTML-Merkmale der Betreiber-Website |
| s20 | Namen für unbenannte Plätze aus dem Website-Titel (bereinigt + Plausibilitätsfilter; keine erfundenen Namen – sonst „(unbenannt)") | og:site_name / h1 / title |

## Karten-Features (seit 2026-11-23)

- **Filter-Panel** (Button „Filter ▾", aufklappbare Gruppen): Platz-Typ
  (Camping/Stellplatz/Verein/Sonstiges/unbenannt), Wasser & Hausboot
  (≤50 m, Hausboot-taugliches Gewässer, Gewässer-Typ), Score & Ausstattung
  (Min-Score, Steg/Marina, Mietunterkünfte ja/nein/Lücke, Dauercamper),
  Bebaubarkeit (B-Plan, Ampel), Kontakt & Daten (Online-Präsenz, E-Mail,
  KI-Sichtung). Zähler „X von Y sichtbar".
- **Default ausgeblendet** (s17): reine Wohnmobilstellplätze, Vereine mit
  Vereinsheim, Parkplätze/Fahrerlager/Biwak, unbenannte ohne Kontakt,
  Plätze ohne Online-Präsenz. Per Filter zuschaltbar; Daten bleiben in
  Excel/DB.
- **Bild-Karussell** im Popup: aktuelles DOP + historische Luftbilder +
  Website-Fotos (‹ › durchklickbar, Label = Aufnahmejahr bzw. „Website-Foto").
  Popup scrollbar (max. 62 % Fensterhöhe) und 460 px breit.
- **Hausboot-Gewässer-Bewertung**: einheitlich über OSM-Typ + gemessene
  Gewässerfläche (s18, ≥ 5 ha = „ja"); Teich/Fluss/Kanal/Bach = „nein";
  Quelle der Einstufung wird im Popup angezeigt. Manuelle Overrides aus
  KI-Sichtungen in s17 (WATER_OVERRIDE: Kelbra nein, ThürKies/Erfurt am See ja).
- **Zwei Scores je Platz**: **Tiny-House-Score** (Wasserlage nur kleiner
  Bonus max 10, dafür Bebaubarkeit bis 15) und **Hausboot-Score**
  (Wasserlage max 35 + Gewässer-Eignung 15 + Steg 12 + Uferlänge max 8;
  ohne Hausboot-Gewässer max 40). Der Lead-Score kombiniert beides für
  die Rangliste. Komponenten als „erreicht / erreichbar" (z. B. 8/15) in
  Popup, Excel und Dossier; Score-Typ im Filter umschaltbar (inkl.
  Marker-Einfärbung).
- **Website-Modernität (0–10)** statt reiner Erreichbarkeit im Score
  (Kontakt ist Filterkriterium): mobil-tauglich, HTTPS, Online-Buchung,
  Aktualität, Social Media, Framework – Proxy für Investitionsbereitschaft.
- **Rechenbeispiel je Platz**: 3 Einheiten × Nachtpreis × 140 Nächte;
  Preis bevorzugt aus Airbnb/Booking-Angeboten im Umkreis 25 km
  (Median − 20 % Camping-Abschlag), sonst Regions-Median; Quelle im Text.
- **Info-Symbole ⓘ** mit Hover-Erklärung bei Flurstücken, ALKIS,
  Bebaubarkeits-Ampel (+ Punkt-Unterteilung), Gewässer-Einstufung,
  Mietunterkünften, KI-Luftbild-Sichtung, Scoring, genutzter Fläche
  (OSM), Website-Modernität und Rechenbeispiel. Flurstücke nur als
  Gesamtgröße + Anzahl.
- **Bestand im Popup**: „Hausboot vorhanden ja/nein",
  „Tinyhaus vorhanden ja/nein" (Website-Angaben), B-Plan-Erklärung
  (Gebietsarten wie WA = Wohngebiet, Versorgungsfläche = angrenzende
  Planflächen).

## Update-Lauf (neue Plätze / Daten auffrischen)

Die Pipeline ist **komplett ohne KI lauffähig** – alle Schritte sind
mechanische Skripte (OSM, Kataster-WMS, Luftbild-WMS, Website-Scrape,
Heuristiken). Nur zwei Dinge brauchen einen Agenten/Browser und sind
bewusst *nicht* Teil des Updates: die KI-Luftbild-Sichtung (s15) und die
Booking/Airbnb-Portal-Scrapes (vorhandene Rohdaten werden weiterverwendet;
bestehende KI-Sichtungen bleiben in der DB erhalten).

```bat
python -m pipeline.refresh alle        :: alle 5 Regionen auffrischen + exportieren
python -m pipeline.refresh sachsen     :: einzelne Region
```

Der Refresh holt die OSM-Grundliste **live** (neue/umbenannte/entfernte
Plätze werden automatisch übernommen), scrapt Websites neu, lädt fehlende
bzw. >180 Tage alte Luftbilder neu (neue Befliegungen) und rechnet alles
durch. Für regelmäßige Updates (z. B. alle 4 Wochen) einfach
`tools\refresh.ps1` in die Windows-Aufgabenplanung legen – das Skript
aktualisiert alle Regionen und veröffentlicht danach automatisch.

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
Ordner `/docs`). Luftbilder werden fürs Web auf ≤800 px / JPEG q60 komprimiert
(~345 MB → ~125 MB); die Originale bleiben lokal. Die Online-DB enthält alle
Scores/Analysen, aber nicht die 54 MB Flurstück-Rohgeometrien (Karte lädt
ALKIS live; vollständige DB bleibt lokal).

**Alles in einem Schritt:** `powershell -ExecutionPolicy Bypass -File tools\publish.ps1`
(spiegelt Code aus der Arbeitskopie, baut docs/, committet, pusht).

## Rechtliches / Datenlizenzen

- OpenStreetMap-Daten: © OpenStreetMap-Mitwirkende, ODbL.
- Amtliche Geodaten (DOP/ALKIS/B-Pläne): freie Nutzung gemäß den jeweiligen
  Landesbedingungen (z. B. Datenlizenz Deutschland – Namensnennung 2.0).
- Esri Wayback: © Esri & Partner, nur zur Ansicht/Auswertung.
- KI-Bildsichtungen sind Luftbildeindrücke, keine verbindliche Bestandsaufnahme;
  Bebaubarkeit immer mit dem Bauamt klären (`docs/BAUAMT_VORLAGEN.md`).
