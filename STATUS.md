# STATUS – Stand 2026-11-23 (ALLE 5 REGIONEN FERTIG + online + Runde 5)

## Nachschaerfung Runde 5 (2026-11-23, Vereine + Preis-Benchmark + Flaechen)
- **Vereins-Logik (s17) verschaerft-praezisiert**: Verein MIT Vereinsheim
  (ALKIS Wohn-/Wirtschafts-/oeffentliche Gebaeude) aber MIT Camping-
  Struktur (Mietunterkuenfte/Zelte/Dauercamper) bleibt jetzt SICHTBAR
  ('Einzelfall pruefen'); nur ohne Camping-Struktur hidden. Vereine ohne
  erfasstes Heim bleiben sichtbar. s14 nimmt bei --top=N jetzt ALLE
  Vereine mit (nicht nur Top-N nach Score) → Heim-Pruefung vollstaendig.
  Vereins-ERFASSUNG kommt nur aus OSM camp_site/caravan_site (44 Vereine
  gesamt) – Vereinsgelaende ohne Camping-Tag sind bewusst nicht drin.
- **Preis-Benchmark auf ganze Unterkuenfte erweitert (s06/s13)**:
  Vergleichsobjekt = eigenstaendige kleine Unterkunft MIT Kueche fuer
  ~4 Personen (2 Erw.+2 Kinder): Ferienhaus/FeWo/Bungalow/Chalet/
  Blockhuette/Tiny House/Mobilheim/Wohnung. RAUS: Zimmer in fremder
  Wohnung, Hotels/Pensionen, Zelte/Schlaffaesser/Jurten, Campingbusse.
  classify_offer() klassifiziert Titel+Typ; 'Privatunterkunft'/'Gaeste-
  haus' sind bei Airbnb (Filter 'ganze Unterkunft') Kategorien, keine
  Zimmer. Zusatz-Scrape 2026-11: Airbnb-Suche ganze Unterkunft,
  4 Gaeste, 9.-12.7.2027, 3 Seiten je Region (+232 Angebote, Dedup per
  Room-ID) → data/airbnb_units_scrape.json, gemergt in portalpreise_*_raw.
  Regions-Median jetzt 'unterkunft_median' (breiter Pool, Airbnb+Booking).
- **Einheitenzahl 1-5 flaechenbasiert (s06)**: Reserve = Grundstueck −
  genutzte Flaeche (~250 m² je Einheit inkl. Abstand/Gruen); nur eine
  Flaeche bekannt → 15 % davon konservativ frei; ohne Flaechen Standard 3.
  Herleitung steht im Rechenbeispiel-Text.
- **Flurstueck-Zuordnung repariert (s03 attribute_parcels)**: Punkt-
  Plaetze (OSM-node) hatten ALLE BBOX-Flurstuecke gezaehlt (inkl. Riesen-
  Seeflurstuecke, z.B. Surfclub Borna 1,9 km²!). Jetzt: Punkt im
  Flurstueck ODER >25 % Ueberlappung mit 100-m-Umkreis; Polygon-Plaetze
  >5 % wie bisher, aber buffer(0) gegen Topologiefehler (vorher stiller
  Fallback auf ALLE). Keine verwertbare Zuordnung → parcel_area NULL
  statt Summe. 434 Flaechen korrigiert, 161 auf NULL. s07 zeigt nur
  noch zum_platz-Flurstuecke. 'leer geprueft' wird als '[]' markiert
  (kein Endlos-Retry; CAMPING_REFRESH/CAMPING_RETRY_EMPTY holt zurueck).
  MV/BB: 92 Plaetze liefern dauerhaft keine Flurstuecke (Kataster-
  Abdeckung), SN: 60 nachgeholt.
- **Popup kompakter (s07/s08)**: 'Vorhanden: Hausboot / Tinyhaus' in
  EINER Zeile; Panel 540px/Popup 560px; Label 'Bebaubarkeit' ohne
  '(Ampel)'; Info-Texte Flaeche/Rechenbeispiel aktualisiert.

## Nachschaerfung Runde 4 (2026-11-23, Scoring-Feinschliff + Rechenbeispiel)
- **Score-Anzeige**: Komponenten als 'erreicht / erreichbar' (z.B. 8/15),
  keine Max-Fussnoten mehr. Bebaubarkeit-Unterteilung als Info-Icon:
  15=B-Plan Ferienhaus-/Campinggebiet, 12=feste Unterkuenfte (gelb-gruen),
  8=unklar/Bauamt (gelb), 0=keine Basis. score_*_details jetzt [Label,Wert,Max].
- **Erreichbarkeit gibt keine Punkte mehr** (ist Filterkriterium). Ersatz:
  **s19_website_modern** (neu): Website-Modernitaet 0-10 aus HTML-Merkmalen
  (mobil-tauglich +2, HTTPS +2, Online-Buchung +2, aktuelles Jahr +2,
  Social +1, Framework +1; Uralt-Technik -2, Steinzeit-Copyright -2,
  duenner Inhalt -1). Proxy fuer Investitionsbereitschaft/Auslastung.
  Nur eigene Websites (online_status='website'); Spalten web_modern,
  web_modern_info. In allen 3 Scores statt 'Erreichbarkeit'.
- **Rechenbeispiel neu (s06)**: 3 Einheiten (statt 5), Preis je Platz aus
  Airbnb/Booking-Angeboten im Umkreis 25 km (Ort aus Titel geparst +
  Nominatim-Geocoding, Cache portal_geo_<region>.json; Median ab 2
  Angeboten) minus 20 % Camping-Abschlag; sonst Regions-Median.
  140 Naechte = Auslastungsannahme; Stellplatz-Vergleich mit eigenem
  Website-Preis. Quelle steht im Text.
- **s20_namen** (neu): unbenannte Plaetze mit Website bekommen Namen aus
  og:site_name/h1/title (bereinigt, Plausibilitaetsfilter); name_source.
  KEINE erfundenen Namen (Nutzer-Entscheidung): generische Titel
  ('Camping', 'Camping & Caravan') oder nicht ableitbare Namen ->
  '(unbenannt)'. Zuvor abgeleitete Pseudo-Namen ('Campingplatz am
  Berzdorfer See' aus Gewaessername) werden zurueckgenommen.
- **s17**: goerlitz.de/gerstungen.de = AMTLICH; lausitzerseenland.de/
  alpacacamping.de = Verzeichnis. Berzdorfer-See-'unbenannt' war
  Stadt-Seite -> korrekt nur_verzeichnis/hidden bzw. Name ergaenzt.
- **Info-Icons neu**: Flaeche genutzt (OSM-Polygon, keine AI!),
  Website-Modernitaet, Rechenbeispiel, Bebaubarkeit-Unterteilung.
- run_all: s20 vor s17; s19 + s06-Neulauf ('6c') vor Export.
- **Filter-Reset-Button** ('↺ zuruecksetzen') im Filter-Panel: setzt alle
  Filter (auch in zugeklappten Gruppen) auf Standard. Ursache Nutzer-
  'Filter zeigt 0': Kombinationen wie 'Hausboot-Gewaesser' + 'Bestand
  Hausboot vorhanden=ja' sind logisch fast leer (Ziel-Leads haben gerade
  NOCH kein Hausboot). Filter selbst korrekt (SN: hb=24, Wasser=37).
- **refresh.py + tools/refresh.ps1** (neu): Update-Lauf OHNE KI.
  CAMPING_REFRESH=1 -> s01/s02 ignorieren Cache (OSM live, neue Plaetze),
  s04 laedt >180 Tage alte DOP neu. s15 (KI-Sichtung) + Portal-Browser-
  Scrapes bewusst nicht enthalten; vorhandene Daten bleiben.
  Aufgabenplanung: refresh.ps1 alle X Wochen -> aktualisiert + publisht.

## Nachschaerfung Runde 3 (2026-11-23, Dual-Scoring + Info-Icons)
- **Zwei Scores (s06)**: score_th (Tiny House: Wasserlage nur Bonus max 10,
  Bebaubarkeit 0-15 nach Ampel) und score_hb (Hausboot: Wasserlage max 35,
  Gewaesser-Eignung 15, Steg 12, Uferlaenge max 8; ohne Hausboot-Gewaesser
  Deckel 40). lead_score bleibt kombinierte Heuristik fuer Ranking/Top-20.
  Alle drei mit JSON-Komponenten (score_*_details) in Popup/Excel/Dossier.
- **Karte**: Score-Typ-Dropdown (Lead/TH/HB) fuer Min-Score-Filter +
  optionale Marker-Einfaerbung; Badges Lead/TH/HB im Popup; Ampel-Filter
  ohne rot (Stellplaetze sind eh default aus).
- **Info-Icons (i)** mit Hover-Erklaerung: Flurstuecke, ALKIS, Ampel,
  Gewaesser-Einstufung, Mietunterkuenfte, KI-Sichtung, Scoring.
  Flurstuecke nur noch als 'Grundstueck gesamt: X m² · N Flurstuecke'.
- **s18 Performance**: STRtree-Nearest-Index statt O(n*m) (BB 31k
  Gewaesser); alle 5 Regionen in ~2 Min.

## Nachschaerfung Runde 2 (2026-11-23, Nutzer-Feedback Karte/Popup)
- **s18_gewaesserflaeche** neu: misst Flaeche des naechsten Gewaessers in ha
  (OSM-Geometrie, einheitliche Quelle water_class_src). s17 nutzt jetzt:
  Typ-Tag > Flaechenmessung (>=5 ha = Hausboot ja) > Name nur als Hinweis.
  Grosser Teich >=5 ha zaehlt als See-Alternative. WATER_OVERRIDE bleibt.
- **Sandgrube-Fix (s17)**: OSM-Tag caravan_site=motorhome_stopover bzw.
  Name 'Wohnmobilstellplatz' = harter Stellplatz-Nachweis; Scrape-Fehltreffer
  (z.B. 'Ferienhaus' von Stadt-Website) werden dann ignoriert. Stadt-/
  Gemeindeseiten (AMTLICH_PAT) = nur_verzeichnis, nicht eigene Website.
  Zusaetzlich: camping ohne Online-Auftritt UND ohne E-Mail -> hidden.
- **Popup**: Breite 460px + max-height 62vh scrollbar; Karussell-Labels
  nur Aufnahmejahr (kein 'Release'); Hausboot vorhanden ja/nein + Tinyhaus
  vorhanden ja/nein; Gewaesserflaeche + Quelle; Scoring-Zusammensetzung
  als aufklappbare Tabelle (score_details aus s06); B-Plan-Block mit
  Erklaerung (WA/Versorgungsflaeche = Nachbar-Planflaechen); Labels
  'Grundstuecksflaeche (Flurstuecke)', 'Gebaeude (amtl. Kataster)',
  'Luftbild-Sichtung (KI)'. Motorboot-Zeile entfernt (irrelevant).
- **Filter**: Kontakt-Gruppe jetzt Checkboxen 'nur eigene Website',
  'nur Online-Auftritt', 'nur E-Mail', 'nur KI-Luftbild-Pruefung';
  neue Gruppe Bestand: Hausboot/Tinyhaus vorhanden ja/nein/egal.
- **s06**: score_details (JSON-Komponentenliste) je Platz; B-Plan-planart
  Duplikate dedupliziert + auf 160 Zeichen gekuerzt.
- **s08**: Motorboot raus, Hausboot/Tiny-Status + Gewaesserklasse +
  Scoring-Tabelle rein; Befliegungs-Labels nur Jahr.
- PowerShell-Falle: Get-Content/Set-Content zerlegt UTF-8-Umlaute
  (cp1252-Mojibake) + BOM. NIE fuer Code-Dateien nutzen; Reparatur:
  text.encode('cp1252').decode('utf-8'). Nur edit/write-Tools verwenden.

## Nachschaerfung 2026-11-23 (Nutzer-Feedback)
- **s17_datenqualitaet** neu: Klassifizierung camping/stellplatz/verein/
  sonstiges/unbenannt + Online-Praesenz (website/nur_verzeichnis/keine)
  + Gewaesser-Typ + Hausboot-Eignung (nur See/Stausee; Teich/Fluss nein).
  Default ausgeblendet: ST 107, TH 133, SN 247, BB 245, MV 108 Plaetze
  (Stellplaetze, Vereine mit Vereinsheim, Parkplaetze/Fahrerlager/Biwak,
  unbenannte ohne Kontakt, keine Online-Praesenz). Daten bleiben in DB/
  Excel; Karte zeigt sie nur per Filter. WATER_OVERRIDE aus Sichtungen:
  Kelbra=nein (Schwanksee), ThuerKies/Erfurt am See=ja (Kiesseen).
- **Karten-UI**: Filter-Panel mit aufklappbaren Gruppen (Typ, Wasser/
  Hausboot, Score/Ausstattung, Bebaubarkeit, Kontakt/Daten) + Zaehler;
  Bild-Karussell im Popup (DOP + Hist + Website-Fotos, ‹ ›).
- **Website-Fotos**: Subagent fertig (2026-11-23): 91/125 Top-Plaetze,
  226 Bilder (23 MB) in output/webbilder/ + enrichment.web_images.
  31 ohne grosse Fotos (Textseiten/JS-Galerien) → optional Browser-
  Zweitlauf. Skript: %TEMP%\opencode\cp_webbilder.py (idempotent).
- s08-Dossiers: nur nicht-ausgeblendete Plaetze in Top-20.
- User-Beispiele verifiziert: Camping Freiberg=Stellplatz+Pferdeschwemme
  (nein), Parkplatz Klein Erzgebirge=sonstiges, Fahrerlager=sonstiges,
  KSV Floeha=Verein (kein Vereinsheim erfasst → sichtbar, Einzelfall).

## Repo + Hosting (2026-11-23)
- Oeffentliches GitHub-Repo `Febru5x/Campingplatzfinder`, lokale Kopie
  `C:\Users\bruen\Campingplatzfinder` (git + gh als Febru5x eingerichtet).
- GitHub Pages aus `docs/` → https://febru5x.github.io/Campingplatzfinder/
  (Karten/Excel/Dossiers/DB online, Luftbilder web-komprimiert ~100 MB).
  Update-Workflow + Details: DEPLOYMENT.md im Repo.
- Documents-Sync damit OBSOLET (Nutzer: muss nicht in Documents liegen;
  Defender-Freigabe nicht mehr noetig).
- **Aktiver Code:** `%LOCALAPPDATA%\Campingplatzfinder\code\` (Pipeline
  laeuft dort); Repo-Kopie wird per robocopy aktualisiert (DEPLOYMENT.md).
- Daten/Output zentral: `%LOCALAPPDATA%\Campingplatzfinder\{data,output}`.

## Ergebnisstand (alle 5 Regionen FERTIG)
| Region | Plaetze | ≤50m Wasser | Flurstuecke | B-Plan Top-30 | Hist Top-30 | ALKIS Top-40 | Bildsichtung |
|---|---|---|---|---|---|---|---|
| seenplatte | 223 | (Pilot) | ja | ja | 1953/1991+Esri | – (MV keine Typen) | Top-6 gesichtet |
| brandenburg | 434 | 204 | 403 | 26/30 | 30 (Esri-Wayback) | 37/40 (97 Geb. Koerbiskrug) | **Top-20 gesichtet** |
| sachsen | 375 | 97 | 315 | 27/30 | 30 (Wayback 26) | 35/40 | **Top-20 gesichtet** |
| thueringen | 228 (nach s16+ST-Zugang) | 69 | 228 (100%) | 23/30 +23 OCR | 30 (Esri-Wayback 25) | 34/40 (Linkenmuehle 314 Geb!) | **Top-20 gesichtet** |
| sachsen_anhalt | 221 (nach s16) | 85 | 221 (100%) | 26/30 | 30 (Esri-Wayback 21) | 39/40 (Birnbaumteich 170 Geb.) | **Top-20 gesichtet** |

- **ST FERTIG**: Excel 221 Zeilen (20 Bildsichtungen, 221 Rechenbeispiele
  mit echten Portal-Benchmarks 138/242 €), Karte verifiziert (221 Marker,
  Popup mit DOP+Hist+ALKIS-Gebäuden+B-Plan+Rechenbeispiel, ALKIS-WMS-
  Kacheln 32/32 geladen, ARIS-Overlay + ImageServer-DOP aktiv),
  Top-20-Dossiers. Blütengrund-Sichtung korrigiert (Website zeigt doch
  Bungalow+Tinyhaus = Wettbewerb, Score 77.5→74.5).
- **TH FERTIG**: Excel 228 Zeilen (Top-20 gesichtet inkl. 5 Nachzuegler
  Kelbra/Weissensee/Quick-Camping/Erfurt am See/ThuerKies, 228
  Rechenbeispiele, Benchmarks 161/217-Fallback), Karte verifiziert
  (228 Marker, Popup vollstaendig, DOP+ALKIS-WMS 64/64 Kacheln
  geladen), Top-20-Dossiers. Kelbra-DOP nachgeladen (2025, Vollbild;
  150-200 Einheiten, Steg im Westen, Schlickflaechen = schwankender
  Wasserstand → kein Hausboot). 38 Flaeming-Plaetze ohne Flurstuecke
  nachgeholt (s03) → jetzt 100%; dadurch 3 neue Plaetze in Top-20
  (Quick-Camping 74.0 = Kelbra-DUPLIKAT, Erfurt am See 72.0 =
  Baggersee-Doppelanlage, ThuerKies 70.2 = Kiessee mit Strand+Steg).
- **ST/TH-Dienste vollstaendig in regions.json** (Adapter-Keys:
  `alkis_wfs_version`, `alkis_bbox_crs`, `dop_kind="arcgis"`,
  `dop_info_layer`, `bplan_mapserver`). Details/Quirks: DATENQUELLEN.md.
- **Website-Rettung erfolgreich** (s05 --only-missing, neue Fallback-
  Kette Browser-UA→Wayback): TH 35/41, ST 12/16 gerettet.
- ST-DOP-WMS + gfds/wss-DOP-Dienste: Serverstoerung → ImageServer-
  Workaround aktiv (DOP 2026, 283/283 ok). TH: 346/346 DOPs ok.

- Output je Region: `output/campingplaetze_<region>.xlsx`,
  `output/karte_<region>.html`, `output/dossiers/<region>/` (Top-20).
- Seenplatte heute neu exportiert (s07/s08): Bildsichtung jetzt in
  Excel (6 Zeilen) + Dossiers. Alte Wurzel-Dossiers (96 Dateien, teils
  veraltete Rankings) gesichert nach `output/dossiers/_alt_vor_2026-11-22/`.
- **Karten im Browser verifiziert** (BB + SN): ALKIS-Flurstuecksgrenzen
  laden (BB 32 Kacheln, SN 42/42), Popup mit DOP + Hist-Zeitreihe +
  Gebaeudetypen + B-Plan + Rechenbeispiel, Layer-Controls + Filter ok.
  Trick fuer Agent: Leaflet-Objekte (`map`, `markers`) sind globale
  `const` → nur per injiziertem <script>-Tag erreichbar (eval-ISOLATED
  world sieht sie nicht); Ergebnis via document.title zuruecklesen.
  Hintergrund-Tab: `map.invalidateSize()` noetig, sonst halbe Karte.

## Top-Leads (nach KI-Bildsichtung)
### Brandenburg (434)
1. Koerbiskrug 86.8 – ~90 Wochenendhaeuser (ALKIS 97 Geb.) → Austausch
2. Kuhle Wampe 85.2 – Hausboot-Kolonie = Wettbewerb/Kooperation
3. Plauer See 84.8
4. Spreewald „Am See" 84.0 + Voigtswiese 81.0 – freie Uferflaechen = TOP
5. Treppelsee 82.8, Schervenzsee 78.0, Springsee 77.8, Glower See 77.2
- Marina Oderberg: Werft/Kran/Slip → Hausboot-Logistikpartner
- Spreewald-Fliesse: zu flach/Bruecken → Tinyhaus-Fokus
### Sachsen (375)
1. Kulkwitzer See 81.8 – 59x Beherbergung, Hausboot schon da (Kooperation),
   freie Nordwiese mit Wegenetz = ideale Tinyhaus-Erweiterung. TOP.
2. Waldbad Niesendorf 77.0 – naturnah, fast unbebaut (nur 2 Geb.)
3. Greifensteine 76.0 – dichte Bungalowkolonie (141 Wohngeb.), Austausch;
   ACHTUNG: 2. Polygon way/319709251 (62.0) = derselbe Platz, nicht doppelt!
4. Dammuehlenteich 74.0 – Wochenendhaus-Kolonie (94 Wohngeb.), Luecke
   Mietunterkuenfte → Austausch-Lead
5. **Zum Muencherteich 68.0 – fast unbebaute Uferhalbinsel, 2 Stege,
   B-Plan da = hoechster Entwicklungs-Hebel (Tinyhaus-Dorf + Hausboot)**
- Riesaer WSV 68.5 / Dresdner Segelclub 64.8: Vereinswiesen an der Elbe
  → Hausboot-Steg + Kooperation (Hochwasser pruefen!)
- Bierwiesenteich 62.0: Gastro am Teich, null Camping-Struktur = gruene Wiese
- Halbendorfer See 62.8: Tinyhaeuser vorhanden (Wettbewerb), Lausitzer
  Seenland boomt; Tonschacht 63.0: junger Wachstumsplatz
- Nachrangig: Pirna (Laerm), Ostrauer Muehle (Nationalpark/enge Zufahrt),
  Ochelbaude/Barth-Muehle (Aussenbereich/kein Camping)
### Seenplatte (223, Pilot)
- Havelberge 93, Sommersdorf 87.5 (staerkster Tiny-Lead: ~100 Dauer-
  Caravans, keine Mietunterkuenfte, Acker im NO), C25 85.5
### Thueringen (228, Bildsichtung Top-20 fertig)
1. **Neumannshof 90.2** – Hohenwarte-Stausee, ~150-250 Dauer-Einheiten,
   viele Privatstege = Hausboot-Kultur etabliert. TH-Top-Lead.
2. **Seecamping Kelbra 85.8** – Stausee Kelbra, 400-EUR-Unterkuenfte
   (hoechstes Niveau TH!), Bungalow/Schlaffass, freie Ostwiese.
   Talsperre schwankt stark (Hochwasserschutz) → Hausboot kritisch.
3. Paulfeld 85.0 – Wald-Grossplatz, 200-300 Dauer + Bungalow-Reihe,
   Austausch-Lead (Waldteiche, kein Hausboot).
3. Meyersgrund 84.0 – 100+ Alt-Huetten im Ilmtal, 92-EUR-Niveau =
   Premium funktioniert; Austausch-Lead, Hanglage pruefen.
4. Schoensee 80.0 – Solar/Investitionssignale; **DUPLIKAT mit
   node/2429435644 (Urnshausen, 63.0)** – nicht doppelt anschreiben!
5. **Palumpa-Land 76.8 – fast leere Wiesen-Halbinsel an Talsperre
   Seebach = groesster Entwicklungs-Hebel (Tinyhaus-Dorf + Steg)**
6. **Stausee Wangenheim 75.8 – freie Suedwiese, keine Mietunterkuenfte
   = idealer Tinyhaus-Pilot + kleiner Hausboot-Steg**
7. **Linkenmuehle 73.8 – leere Ost-Terrassen (ehem. Wochenendgebiet)
   mit Wegenetz + Stegen = Rueckbau-/Austausch-Flaeche, hoher Hebel**
8. **Plothener Teiche 72.0 – frisch geschotterte Zentralflaeche =
   Betreiber investiert GERADE (Timing!); FFH-Status pruefen**
- Droschkau 75.8 (e.V., Hohenwarte), Eisenach 74.0 (dicht, Wartburg-
  Tourismus), Hopfenmuehle Drognitz 65.8 (Hausboote vorhanden =
  Wettbewerb), Bergsee Ratscher 65.5 (freie Uferwiese + Steg),
  Hohenfelden 61.0 (Tinyhaeuser vorhanden, Grossbetreiber).
- Neu in Top-20 (nach Flurstueck-Nachholung): **Kelbra Quick-Camping
  74.0 = DUPLIKAT von Kelbra (landseitiger Teilplatz), nicht doppelt
  anschreiben!**; Erfurt am See 72.0 (Baggerseen, Kiesabbau/Rechte
  klaeren, Bahnlaerm); **ThuerKies 70.2 (Kiessee, eigener Strand +
  T-Steg, Kieswerk-Betreiber = direkter Wasserrechte-Ansprechpartner,
  keine Mietunterkuenfte = Luecke)**.
- Hohenwarte-Stausee = Hausboot-Cluster (Neumannshof/Linkenmuehle/
  Droschkau/Hopfenmuehle). Streichen: Unter den Linden (Kleingaerten),
  Verkehrsgarten Lessingstrasse, Grossmutterwiese (Parkplatz).
### Sachsen-Anhalt (221, Bildsichtung Top-20 fertig)
1. **Jersleber See 95.5 – B-Plan 'Sondergebiet Wochenendhausgebiet'
   rechtskraeftig (BP Nr. 9)! 200-300 Einheiten, 150-EUR-Niveau,
   Steg da = erster Ansprechpartner in ST**
2. Harz-Camp Bremer Teich 85.0 – **DUPLIKAT: way/438492699 +
   way/479722112 = eine Anlage**; freie Sandflaeche westl. Servicehalle.
3. Plattensee 81.0 – locker bewaldet, viel Reserve, Solar, Badesee.
4. Zabakuck 80.0 – freie Nordwest-Wiese am See, Vermietung laeuft.
5. **Bluetengrund 74.5 – Saale-Unstrut-Weinregion; Website zeigt doch
   Bungalow+Tinyhaus (Wettbewerb!), grosse freie Suedwiese =
   Kooperations-/Erweiterungs-Lead**
6. Aken Boot&Campingcenter 76.8 + Marina-Camp Elbe 71.5 – vermutlich
   EIN Komplex (zusammen ansprechen); Boots-Hallen/Solar = kapital-
   starker Wasser-Betrieb; Elbe-Hochwasserschutz beachten.
7. **Niegripper See 72.2 – Marina + OHNE Mietunterkuenfte + freie
   Nordwiese = guter Kombi-Lead (Burg/Magdeburg)**
8. Schifferklause 71.5 – Boots-Community, 20+ Boote am Steg,
   Nischen-Lead Hausboot+Tinyhaus im Kleinen.
- Prettin 74.0 (Elbe-Strand, Solarpark nebenan), Steinhafen 75.8
  (rustikales Altwasser), Kellerwiehl 72.0 (Solar, Teiche),
  Aktivcamp&Tipidorf 71.0 (Kanu, Wiesen-Reserve), Adria 68.0
  (tuerkiser Restlochsee, dicht).
- Streichen: Junkers Paddelgemeinschaft (Verein), Sportboothafen
  Calvoerde (Mini-Stellplatz); Radfahrer-Zeltplatz 70.5 = Hafen-Hotel
  mit freier Suedwiese → Eigentuemer klaeren, evtl. interessant.

## Marktpreise / Rechenbeispiele (s06/s13)
- Portal-Methode: echter Browser (browse-Extension), Booking-Regionssuche
  `ss=<Region>, Deutschland&checkin=2027-07-09&checkout=2027-07-12` +
  ht_id=215-Filter (aid=304142), Selektor `[data-testid="property-card"]`;
  Airbnb ohne Login per Keyword-Suche, Karten `[itemprop="itemListElement"]`,
  Preis aus „Gesamtpreis X €". Fremdland-Treffer lokal aussortiert.
- BB: Tiny-Median 111 €, Hausboot-Median 217 € (17 Boote).
- SN: Tiny-Median 113 €, Hausboot 217 € = **BB-Fallback** (SN hat keine
  Hausboot-Angebote = Marktluecke; s13 setzt hausboot_hinweis).
- TH: Tiny-Median 161 € (Airbnb, n=2), Stellplatz 23 €; Hausboot 217 €
  = BB-Fallback (keine Portal-Hausboote in TH; Hohenwarte-Verleih
  laeuft ueber eigene Websites = Marktluecke/Chance).
- **ST: ECHTER Hausboot-Markt!** Booking-Median 242 € (n=6:
  Geiseltalsee El'milia 794/3 + Marina Braunsbedra 800/3, Goitzsche
  La Belle Vie 726/3, Arneburg/Elbe 650/3, Silbersee-Waldfloesse
  227+279/3); Airbnb-Tiny-Median 138 € (n=4). Kein Fallback noetig.
  Geiseltalsee = Hausboot-Cluster Nr. 2 neben Hohenwarte (TH).
- Seenplatte: Hausboot 272 €, Tiny 103 €.
- Stellplatz-Benchmark: MV/BB/SN ~20 €.
- s13 GH_REGIONS erweitert: Thueringen→thuringia,
  Sachsen-Anhalt→saxonyanhalt (GlampingHub, HTTP 200 verifiziert).
- Rechenbeispiele in ALLEN Excel-Zeilen (375/434/223) gefuellt.

## Bundesland-Zuordnung (s16_region_check)
- Nominatim-Reverse (zoom 8) je Platz; Fremdgebiete bekommen eigene
  Region und fallen aus Regions-Exporten raus (Daten bleiben in DB).
- DB-Bestand: brandenburg 434, sachsen 375, seenplatte 223,
  **sachsen_anhalt 221**, **thueringen 188**, ausland_cz 253,
  ausland_pl 20, mecklenburg_vorpommern 21, bayern/hessen/
  niedersachsen durch s16 stark gewachsen (TH-Bbox zog 158
  Fremdplaetze, ST-Bbox 62 → alle verschoben).
- SN-Bereinigung verifiziert: Hradec/Česká brána/Sloup/Altenburg-Pahna
  raus. **Turisede-Grenzfall korrekt geloest:** way/1347782564 liegt
  laut Nominatim (zoom 8/10/16) in Zentendorf/Neißeaue, Sachsen (DE)
  → bleibt in SN. Der polnische Teil (node/13045239503, Bielawa Dolna)
  liegt in ausland_pl. Kulturpark liegt beidseits der Neiße.

## Pipeline-Besonderheiten (Service-Quirks)
- **SQLite-Migrationsfallen**: ALTER TABLE ADD COLUMN ... TEXT liefert
  bestehende Zeilen als TEXT zurueck (auch '0'/'1'!) → bool('0')=True.
  Neue Flags immer als int schreiben und beim Lesen str(...)!='1' testen.
- s04: `region --size= --workers=`; DOP-Nachladen einzeln moeglich
  (site_bbox_25833 + get_dop + get_flight_year, Meta-JSON pflegen!).
- s05: --shard=i/n + --only-missing; s02: Wasser-Cache 180 Tage.
- s11 BB: PLIS-Geoserver NUR WFS 2.0.0, BBOX-Suffix
  `urn:ogc:def:crs:EPSG::25833`; SN: RAPIS ArcGIS Layer 3+2,
  inSR=3857/outSR=4326; **TH: komm_wfs (PDFs→OCR); ST: ARIS
  FeatureServer Layer 2→Fallback 6 (RK_DAT Epoch-ms, keine PDFs)**.
- s12: MV hist_dop 1953/1991; BB/SN/ST/TH nur Esri Wayback (hist_dop={}).
- s14: ave:GebaeudeBauwerk BB/SN (WFS 1.1.0, TYPENAME Singular,
  EPSG:25833); **TH/ST: WFS 2.0.0 ave 2.0 (Adapter-Keys
  alkis_wfs_version/alkis_bbox_crs; TH BBOX 25832 ohne Suffix,
  ST BBOX 25833 MIT Suffix Pflicht)**; MV liefert keine Typen.
- **s04 ST: ArcGIS-ImageServer-Zweig (dop_kind="arcgis") +
  MapServer-identify Befliegungsdatum; TH: th_dop_info text/xml
  `<Erstellung>`**. s07: esri-leaflet + ARIS-B-Plan-Overlay fuer ST,
  ALKIS-WMS minZoom 15 (ST nur grosse Massstaebe).
- **s05: page_text_robust + wayback_text (Fallback-Kette),
  --only-missing filtert updated IS NULL OR FEHLER%**.
- s15: Sichtungsliste data/bildsichtung_<region>.json; Agent traegt
  `sichtung{bestand,anzahl_geschaetzt,zustand,notiz,datum,methode}` +
  status="gesichtet" ein (Umlaute ae/oe/ue); Re-Run spiegelt in
  enrichment.bildsichtung → s06 → s07 → s08.
- s17: Klassifizierung + Hausboot-Gewaesser; WATER_OVERRIDE fuer
  Sichtungskorrekturen (Kelbra nein, ThuerKies/Erfurt ja). Neue
  Korrekturen dort eintragen, dann s17+s07 neu.
- Website-Fotos: Skript %TEMP%\opencode\cp_webbilder.py (Subagent),
  idempotent; schreibt enrichment.web_images + output/webbilder/.
  Danach s07 neu (Karussell) + build_site (webbilder kopieren).
- s07: Popup zeigt jetzt auch KI-Bildsichtung (Zeile 'KI-Bildsichtung',
  bildsichtung_txt im Map-JSON) – seit 2026-11-22 nachts in ALLEN
  Regionen-Karten (TH+ST im Browser verifiziert).
- Agenten-Sichtungen per Musterskript schreiben:
  `%TEMP%\opencode\sichtung_brandenburg.py` / `sichtung_sachsen.py` /
  `sichtung_thueringen.py` / `sichtung_sachsen_anhalt.py`.
- s08: TMPL %-Formatierung → literale % als `%%`; Dateien
  `output/dossiers/<region>/%02d_<id>.html`.
- Hintergrund-Shells: explizit grosses timeout (Default killt Kette).
- PowerShell zerhackt Inline-Python-Quotes → write/edit-Tools nutzen;
  `$env:PYTHONIOENCODING='utf-8'` fuer Umlaute.
- Map-Server: `Start-Process -WindowStyle Hidden python -ArgumentList
  '-m','http.server','8765','--directory','…\output'`.
- DB: db_write mit BEGIN IMMEDIATE + Retry (prozesssicher);
  lead_score steht in enrichment, NICHT in sites.

## Naechste Schritte / offene Entscheidungen
1. Sinnvolle Erweiterungen (Vorschlaege, noch nicht beauftragt):
   - Kontakt-/CRM-Liste der Top-Leads (Ansprechpartner, Status,
     naechster Schritt) als eigene Excel/Seite.
   - Restliche MV-Plaetze (21) + neue Regionen (BY/HE/NI sind durch
     s16 bereits in der DB) konfigurieren.
   - Saisonkalender/Auslastungs-Annahmen je Region fuer realistischere
     Rechenbeispiele (140 Naechte ist pauschal).
   - Preis-Update-Lauf (s13) vor Vertragsverhandlungen.
2. Top-Leads anschreiben (BAUAMT_VORLAGEN.md, jetzt auch online).
   Erste Kontakte: Jersleber See (ST, B-Plan rechtskraeftig!),
   Neumannshof + Kelbra + Palumpa-Land + Wangenheim + ThuerKies (TH),
   Bluetengrund + Niegripper See (ST).
3. ST-DOP-WMS spaeter erneut pruefen (Serverstoerung), ImageServer
   funktioniert aber vollwertig.
4. Hausboot-Logistik: ST hat mit Geiseltalsee (Marina Braunsbedra)
   und Goitzsche Resort bereits kommerzielle Hausboot-Vermieter =
   potenzielle Kooperationspartner statt nur Wettbewerb.
