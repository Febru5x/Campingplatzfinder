# Datenquellen & methodische Grenzen

Stand: 2026-11-22 – Regionen Mecklenburgische Seenplatte (Pilot),
Brandenburg (gesamt), Sachsen (gesamt), Sachsen-Anhalt + Thüringen
(Ausbau, Anreicherung läuft). Aktiver Code:
`%LOCALAPPDATA%\Campingplatzfinder\code\` (Documents durch Defender
„Überwachter Ordnerzugriff" schreibgeschützt – siehe STATUS.md).

## Verwendete Quellen (alle kostenlos/öffentlich)

| Daten | Quelle MV (Pilot) | Quelle Brandenburg | Quelle Sachsen |
|---|---|---|---|
| Campingplatz-Grundliste | OpenStreetMap (Overpass) | dito | dito |
| Gewässer, Stege, Marinas, Schutzgebiete | OpenStreetMap | dito | dito |
| Flurstücke (Geometrie, amtliche Fläche) | GeoPortal.MV ALKIS-WMS (GetFeatureInfo) | LGB `isk.geobasis-bb.de/ows/alkis_vereinf_wfs` (ave:Flurstueck, WFS 1.1.0, EPSG:25833) | GeoSN `geodienste.sachsen.de/aaa/public_alkis/vereinf/wfs` (ave:Flurstueck) |
| **Gebäude-Footprints + Nutzungstyp** | – (WFS liefert keine Typen) | ave:GebaeudeBauwerk (s14, Top-40) | ave:GebaeudeBauwerk (s14, Top-40) |
| Luftbilder aktuell | GeoPortal.MV DOP20 | LGB DOP20 `mapproxy/dop20c` (kein Info-Layer → kein Befliegungsjahr) | GeoSN DOP `sn_dop_020` + Info-Layer (Jahr 2024/2025) |
| Historische Luftbilder | MV DOP 1953 + 1991 (s/w) | nur Esri Wayback | nur Esri Wayback |
| Luftbild-Zeitreihe ~2014–2024 | Esri World Imagery Wayback | dito | dito |
| Bebauungspläne | WFS LK MSE / bauleitplaene-mv.de (PDFs + OCR) | PLIS-Geoserver `plis-bb.de` (NUR WFS 2.0.0! Keine PDFs → Ampel aus Planart) | RAPIS ArcGIS `rapis.ipm-gis.de` Layer 3+2 (Nutzungsart, keine PDFs) |
| Flurstücks-Overlay in Karte | MV alkis_wms | LGB `alkis_flur_wms` Layer `flur` | GeoSN `wms_geosn_flurstuecke` Layer `Flurstueck` |
| Website-Historie (Bestandsalter) | Wayback Machine | dito | dito |
| Preise, Unterkünfte, Kontakt | Websites (+ Preis-PDFs) | dito | dito |
| Markt-Benchmarks | Booking + Airbnb (echter Browser), GlampingHub, Website-Mediane | dito | dito (Hausboot = BB-Fallback, s.u.) |
| Bundesland-Zuordnung | – | s16: Nominatim-Reverse je Platz | dito |

## Neue Regionen: Sachsen-Anhalt + Thüringen (Dienste & Quirks)

### Sachsen-Anhalt (GeoBasis-DE / LVermGeo LSA, dl-de/by-2-0)
- **DOP20**: ArcGIS **ImageServer** (kein WMS nutzbar!):
  `https://www.geodatenportal.sachsen-anhalt.de/arcgisimage/rest/services/DOP/ST_DOP20_RGBi/ImageServer/exportImage`
  (EPSG:25832/25833/3857/4326 ok). Adapter: `dop_kind="arcgis"` in regions.json.
- **Befliegungsdatum**: MapServer-identify
  `.../arcgis/rest/services/Geobasisdaten/DOP_Kacheluebersichten/MapServer/identify`
  (layers=all:0) → Feld `Befliegungsdatum` (taggenau, aktuell 2025/2026).
- **ALKIS-WFS**: `.../wss/service/ST_LVermGeo_ALKIS_WFS_OpenData/guest`,
  WFS 2.0.0, ave 2.0 (`ave:Flurstueck`, `ave:GebaeudeBauwerk`).
  **BBOX x,y + `,urn:ogc:def:crs:EPSG::25833` PFLICHT** (ohne Suffix 0
  Features; WFS 1.1.0 + BBOX kaputt).
- **ALKIS-WMS** (Karten-Overlay): `ST_LVermGeo_ALKIS_WMS_AdV_konform_App/guest`,
  Layer `adv_alkis_flurstuecke,adv_alkis_gebaeude`, STYLES leer lassen,
  nur große Maßstäbe (≤1:5000, sonst leeres PNG), BBOX E,N (minZoom 15).
- **B-Plan**: ARIS FeatureServer
  `.../arcgis/rest/services/ARIS/bauleitplanung_siedlungsentwicklung_extern/FeatureServer`
  Layer 2 (NUTZUNGSAR/VNA, RK_DAT = Epoch-ms) + Fallback Layer 6
  (Geltungsbereich). Keine PDFs im Dienst → Ampel aus Nutzungsart.
  Karten-Overlay: MapServer-Export layers=show:2,6 (esri-leaflet).
- **Historische Luftbilder**: nur GeoTIFF-Downloads (Katalog
  DOP20_20_21/22_23.geojson) → Pipeline nutzt Esri Wayback.
- **Störung dokumentiert**: DOP-WMS + alle `gfds/`/`wss/`-DOP-Dienste
  liefern „Cannot connect to the database" → Workaround ImageServer.

### Thüringen (GDI-Th, CC BY 4.0)
- Basis: `https://www.geoproxy.geoportal-th.de/geoproxy/services/`
- **DOP20**: WMS `th_dop`; Info-Layer `th_dop_info` (text/xml,
  Befliegungsjahr aus `<Erstellung>`).
- **ALKIS-WFS**: `adv_alkis_wfs` NUR **WFS 2.0.0**, TYPENAMES
  `ave:Flurstueck` / `ave:GebaeudeBauwerk`. **BBOX immer EPSG:25832 x,y**
  (CRS-Suffix wird ignoriert; falsche Koordinaten → still 0 Treffer!).
  SRSNAME steuert Ausgabe-CRS.
- **ALKIS-WMS** (Overlay): `adv_alkis_wms_th`.
- **B-Plan**: `kommunal/komm_wfs`, Layer `kommunal:komm_bp`
  (Name, Planart_Beschreibung, Rechtsstand_Beschreibung,
  Datum_Rechtskraft, Gemeinde, **Planunterlagen-PDF** → OCR-Pfad wie MV).
  Nicht flächendeckend → viele Außenbereich-Plätze ohne Treffer.
- **Historische Luftbilder**: nicht öffentlich → Esri Wayback.
- **s16-Bereinigung**: TH-Overpass-Bbox zog 158 Fremdplätze mit
  (bayern 87, hessen 52, niedersachsen 19) → echte TH-Plätze: 188.
  ST similarly: niedersachsen 22 + thueringen 40 verschoben → 221.

## Methodische Grenzen (bitte beachten)

1. **Bebaubarkeit-Ampel**: MV = OCR amtlicher Plan-PDFs (Fehler möglich,
   Original gegenprüfen!). BB/SN = keine öffentlichen PDFs → Ampel aus
   Planart/Nutzungsart des amtlichen WFS („Sondergebiet Erholung" etc.);
   konkrete Festsetzungen (GRZ, Firsthöhe, Stellplätze) nur beim Bauamt.
   Ohne B-Plan-Treffer: Heuristik aus Unterkünften + OSM-Kategorie.
   Verbindlich ist immer die Bauamts-Auskunft (Vorlagen: BAUAMT_VORLAGEN.md).
2. **Preise** automatisch aus Website-Text extrahiert (unteres Quartil
   plausibler Werte). Stichproben prüfen! **Website-Rettung (s05)**:
   Fallback-Kette normal → Browser-UA + URL-Varianten → Wayback-
   Original-HTML (`id_`-Timestamp); Herkunft/Datum in `scrape_notes`.
   Gerettete Seiten können veraltet sein (Wayback-Datum beachten!).
   Echter Bot-Schutz (HTTP 403, z.B. chayns.site) nur per echter
   Browser-Session lösbar – keine Captcha-/Login-Umgehung.
3. **Uferlänge** = Schnitt OSM-Platzgrenze mit Gewässer (+15 m Puffer);
   OSM-Grenzen ungenau, ±30 % möglich.
4. **Flurstücke/Gebäude**: Eigentümer NICHT enthalten (Grundbuch ≠
   öffentlich in DE). ALKIS-Gebäudezählung = Umkreis/Polygon+Puffer,
   kann Nachbargebäude mit erfassen (bei Vereinsplätzen prüfen!).
   MV: keine Gebäude-Typen verfügbar.
5. **KI-Bildsichtung (s15)**: Agent sichtet aktuelles DOP20 der Top-20
   je Region und schätzt Bestand/Zustand/Erweiterungsflächen; Quercheck
   mit ALKIS-Nutzungstypen. **Luftbildeindruck, keine Vor-Ort-Prüfung** –
   Zustand/Anzahl sind Schätzungen. Ergebnisse: `data/bildsichtung_<region>.json`,
   Spalte „KI-Bildsichtung" in Excel + Box im Dossier.
6. **Bestandsalter**: Wayback-Mindestalter („seit 2007" = mind. 19 Jahre)
   + hist. Luftbilder zum visuellen Vergleich (Popup/Dossier).
7. **Booking/Airbnb-Preise**: echter Browser (browse-Extension).
   Booking: Regionssuche `ss=<Region>, Deutschland` + Datum-Parameter
   (checkin 2027-07-09, 3 Nächte, 2 Erw.), Hausboot-Filter `nflt=ht_id%3D215`
   (funktioniert mit aid=304142 oder UI-Klick); Karten
   `[data-testid="property-card"]`; Offset-Pagination wirkungslos.
   Airbnb: ohne Login, Keyword-Suche über Suchfeld; Karten
   `[itemprop="itemListElement"]`, Preis aus „Gesamtpreis X €".
   Fremdland-Treffer werden lokal aussortiert; Charter-Angebote markiert.
   Grenzen: Momentaufnahme EINER Hauptsaison-Woche; Booking teils zzgl.
   Endreinigung, Airbnb inkl. Servicegebühr; Preis = Gesamtpreis ÷ Nächte.
   Rohdaten `data/portalpreise_<region>_raw.json`, Benchmarks
   `data/marktpreise_<region>.json`.
   **s13-Fallback**: Hausboot-Vorschlag nur bei ≥3 echten Boot-Angeboten;
   sonst Brandenburg-Median + `hausboot_hinweis`. Sachsen hat keine
   Hausboot-Portalangebote → Marktlücke (Chance!), Benchmark geliehen.
8. **Motorboot-Flaggen** aus OSM-Tags – lückenhaft. Vor Hausboot-Vertrieb:
   WSA-Regeln je Gewässer prüfen (Elbe = Bundeswasserstraße, Hochwasser!).
9. **Bundesland-Check (s16)**: Nominatim-Reverse ordnet jeden Platz dem
   echten Bundesland zu; Grenzflächen können falsch liegen (Beispiel
   Turisede: Kulturpark beidseits der Neiße – deutsches Polygon bleibt
   in Sachsen, polnischer Teil in `ausland_pl`). Fremdregionen bleiben
   in der DB, fallen aber aus den Regions-Exporten.

## Rechtlicher Hinweis

Grundbuch-Einsicht (DE) setzt berechtigtes Interesse voraus – nicht Teil
dieser Pipeline. Österreich: Grundbuchauszug öffentlich (kostenpflichtig),
Kataster-Geometrie frei. Schweiz: amtliche Vermessung einsehbar.
Diese Quellen werden bei der DACH-Ausweitung je Region ergänzt.
