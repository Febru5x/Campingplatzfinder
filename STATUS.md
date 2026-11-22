# STATUS – Stand 2026-11-22 nachts (ALLE 5 REGIONEN FERTIG)

## WICHTIG: Arbeitskopie des Codes + Documents-Sperre
- **Ursache der Documents-Sperre GEKLAERT:** Windows Defender
  „Überwachter Ordnerzugriff" (Controlled Folder Access) ist AKTIV
  (`Get-MpPreference` → EnableControlledFolderAccess = 1).
  Defender-Eventlog ID 1123 blockiert python.exe / powershell.exe /
  Robocopy.exe beim Schreiben nach `Documents\Campingplatzfinder`
  (Lesen geht). Das war KEIN paralleler Agent.
- **Fix (nur manuell durch den Nutzer, Admin):** Windows-Sicherheit →
  Viren- & Bedrohungsschutz → Ransomware-Schutz → „Überwachter
  Ordnerzugriff" → App zulassen: `python.exe`
  (C:\Users\bruen\AppData\Local\Programs\Python\Python39\python.exe) und
  ggf. `robocopy.exe`/`powershell.exe` freigeben – ODER Schutz aus.
  Agent-seitig nicht aenderbar (Admin noetig, Sicherheitsentscheidung).
- **Aktiver Code bleibt:** `%LOCALAPPDATA%\Campingplatzfinder\code\`
  (pipeline + config). Aufruf: `cd %LOCALAPPDATA%\Campingplatzfinder\code`,
  `python -m pipeline.run_all <region>`.
- Daten/Output zentral: `%LOCALAPPDATA%\Campingplatzfinder\{data,output}`.
- Nach Freigabe: `robocopy "%LOCALAPPDATA%\Campingplatzfinder\code"
  "%USERPROFILE%\Documents\Campingplatzfinder" /E /XD __pycache__ .git`
  (ohne Endlos-Retry: `/R:2 /W:2` anhaengen!).

## Ergebnisstand (MV/BB/SN FERTIG; ST+TH Anreicherung laeuft)
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
1. Documents-Sync nach Defender-Freigabe (siehe oben; Schutz noch
   aktiv, EnableControlledFolderAccess=1), dann STATUS/DATENQUELLEN
   zurueckkopieren.
4. Optional: restliche MV-Plaetze (mecklenburg_vorpommern 21) dem
   Pilot zuschlagen oder separate Region.
5. Optional: Top-Leads anschreiben (BAUAMT_VORLAGEN.md in output/).
   Erste Kontakte: Jersleber See (ST, B-Plan rechtskraeftig!),
   Neumannshof + Kelbra + Palumpa-Land + Wangenheim (TH),
   Bluetengrund + Niegripper See (ST).
6. ST-DOP-WMS spaeter erneut pruefen (Serverstoerung), ImageServer
   funktioniert aber vollwertig.
7. Hausboot-Logistik: ST hat mit Geiseltalsee (Marina Braunsbedra)
   und Goitzsche Resort bereits kommerzielle Hausboot-Vermieter =
   potenzielle Kooperationspartner statt nur Wettbewerb.
