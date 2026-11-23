"""Schritt 07: Export als Excel + interaktive Leaflet-Karte.

Aufruf:  python -m pipeline.s07_export seenplatte
"""
import json
import shutil
import sys

import pandas as pd

from . import common as C

COLS = [
    ("lead_score", "Lead-Score (gesamt)"),
    ("score_th", "Tiny-House-Score"),
    ("score_hb", "Hausboot-Score"),
    ("web_modern", "Website-Modernität (0-10)"),
    ("web_modern_info", "Website-Modernität: Merkmale"),
    ("name_source", "Namensquelle (falls nicht OSM)"),
    ("name", "Name"),
    ("site_class", "Typ (Klassifizierung)"),
    ("default_hidden", "Default ausgeblendet"),
    ("class_reason", "Klassifizierung: Grund"),
    ("online_status", "Online-Präsenz"),
    ("category", "Kategorie (OSM)"),
    ("water_score", "Wasser-Score"),
    ("water_name", "Gewässer"),
    ("waterbody_class", "Gewässer-Typ"),
    ("water_area_ha", "Gewässerfläche (ha)"),
    ("water_class_src", "Gewässer-Einstufung: Quelle"),
    ("houseboat_water", "Hausboot-Gewässer geeignet"),
    ("water_distance_m", "Abstand Wasser (m)"),
    ("shoreline_m", "Uferlänge (m)"),
    ("has_pier", "Steg"),
    ("marina_distance_m", "Marina-Abstand (m)"),
    ("protected_area", "Schutzgebiet"),
    ("area_m2", "OSM-Fläche (m²)"),
    ("parcel_area_m2", "Grundstücksfläche/Flurstücke (m²)"),
    ("parcel_count", "Flurstücke (#)"),
    ("flurstuecke", "Flurstück-Kennzeichen"),
    ("build_flag", "Bebaubarkeit"),
    ("bplan_namen", "B-Pläne (amtlich)"),
    ("bplan_links", "B-Plan-PDFs"),
    ("rental_age_est", "Bestandsalter / Erneuerung"),
    ("gebaeude_alkis", "Gebäude (amtl. Kataster/ALKIS)"),
    ("bildsichtung_txt", "Luftbild-Sichtung KI (Bestand/Zustand)"),
    ("hist_img", "Hist. Luftbilder"),
    ("booking_link", "Booking-Link (manuell)"),
    ("seasonal", "Dauercamper"),
    ("rentals", "Mietunterkünfte"),
    ("has_tinyhouse", "Tinyhaus vorh."),
    ("has_houseboat", "Hausboot vorh."),
    ("price_pitch", "Preis Stellplatz (€)"),
    ("price_tent", "Preis Zelt (€)"),
    ("price_rental", "Preis Unterkunft (€)"),
    ("season", "Saison"),
    ("revenue_example", "Rechenbeispiel Tinyhäuser"),
    ("top_argument", "Top-Argument"),
    ("score_details_txt", "Scoring-Zusammensetzung (Lead)"),
    ("score_th_txt", "Scoring-Zusammensetzung (Tiny House)"),
    ("score_hb_txt", "Scoring-Zusammensetzung (Hausboot)"),
    ("website", "Website"),
    ("phone", "Telefon"),
    ("contact_email", "E-Mail (Website)"),
    ("email", "E-Mail (OSM)"),
    ("contact_name", "Ansprechpartner"),
    ("chain", "Firma/Betreiber"),
    ("operator", "Betreiber (OSM)"),
    ("lat", "Breite"),
    ("lon", "Länge"),
    ("id", "OSM-ID"),
    ("scrape_notes", "Notizen"),
]


def load_df(region_name):
    conn = C.db()
    rows = conn.execute("""SELECT s.id, s.name, s.category, s.lat, s.lon,
        s.area_m2, s.website, s.phone, s.email, s.operator, s.geometry,
        e.* FROM sites s JOIN enrichment e ON s.id=e.site_id
        WHERE s.region=? ORDER BY e.lead_score DESC NULLS LAST""",
        (region_name,)).fetchall()
    hist = {}
    try:
        hist = {r["site_id"]: json.loads(r["info"]) for r in
                conn.execute("SELECT site_id, info FROM history_info")}
    except Exception:
        pass
    conn.close()
    from urllib.parse import quote
    recs = []
    for r in rows:
        d = dict(r)
        try:
            plist = json.loads(d.get("parcels") or "[]")
            # nur Flurstuecke, die wirklich zum Platz gehoeren (s03-Attribution)
            plist_own = [p for p in plist if p.get("zum_platz")] or plist
            d["parcel_count"] = len(plist_own)
            d["flurstuecke"] = "; ".join(
                p.get("kennzeichen", "?") for p in plist_own[:8])
        except Exception:
            d["parcel_count"] = 0
            d["flurstuecke"] = ""
        # B-Plan-Infos aufbereiten
        try:
            bp = json.loads(d.get("bplan_info") or "null")
        except Exception:
            bp = None
        if bp:
            d["bplan_namen"] = "; ".join(
                "%s (%s%s)" % (p["name"], p.get("rechtsstand") or "?",
                               ", " + p["inkrafttreten"] if p.get("inkrafttreten") else "")
                for p in bp.get("plans", [])[:4])
            links = []
            for p in bp.get("plans", []):
                for doc in p.get("dokumente", []):
                    if "rechtsplan" in doc["typ"].lower():
                        links.append(doc["url"])
            d["bplan_links"] = "; ".join(dict.fromkeys(links))
        else:
            d["bplan_namen"] = ""
            d["bplan_links"] = ""
        # Historie
        h = hist.get(d["id"], {})
        imgs = h.get("hist_luftbilder", {})
        d["hist_img"] = "; ".join("%s: %s" % (y, f) for y, f in imgs.items())
        # ALKIS-Gebaeude (BB/SN)
        try:
            gb = json.loads(d.get("buildings") or "null")
        except Exception:
            gb = None
        d["gebaeude_alkis"] = ("%d Geb., %d m²: %s" % (
            gb["n"], gb["flaeche_m2"],
            "; ".join("%s×%d" % (k, v) for k, v in list(gb["typen"].items())[:5])
        )) if gb else ""
        # KI-Bildsichtung
        try:
            bs = json.loads(d.get("bildsichtung") or "null")
        except Exception:
            bs = None
        d["bildsichtung_txt"] = ("%s | Zustand: %s | %s" % (
            bs.get("bestand", "?"), bs.get("zustand", "?"), bs.get("notiz", "")
        )).strip(" |") if bs else ""
        # Scoring-Zusammensetzung als Text (Lead / Tiny / Hausboot)
        def sd_txt(key):
            try:
                sd = json.loads(d.get(key) or "null")
            except Exception:
                sd = None
            def one(row):
                k, v = row[0], row[1]
                mx = row[2] if len(row) > 2 else None
                if v is None:
                    vs = "×"
                elif v < 0:
                    vs = str(v)
                elif mx is not None:
                    vs = "%s/%s" % (v, mx)
                else:
                    vs = "+%s" % v
                return "%s: %s" % (k, vs)
            return "; ".join(one(row) for row in sd) if sd else ""
        d["score_details_txt"] = sd_txt("score_details")
        d["score_th_txt"] = sd_txt("score_th_details")
        d["score_hb_txt"] = sd_txt("score_hb_details")
        d["booking_link"] = (
            "https://www.booking.com/searchresults.de.html?ss=%s"
            "&checkin=2026-07-10&checkout=2026-07-13&group_adults=2&no_rooms=1"
            % quote(d["name"] or "")) if d["name"] and d["name"] != "(unbenannt)" else ""
        recs.append(d)
    return pd.DataFrame(recs)


def export_excel(df, region_name):
    out = C.OUTPUT / ("campingplaetze_%s.xlsx" % region_name)
    cols = [(k, label) for k, label in COLS if k in df.columns]
    dfe = df[[k for k, _ in cols]].copy()
    dfe.columns = [label for _, label in cols]
    for c in ("Steg", "Dauercamper", "Tinyhaus vorh.", "Hausboot vorh."):
        if c in dfe.columns:
            dfe[c] = dfe[c].map({1: "ja", 0: "nein"})
    with pd.ExcelWriter(out, engine="openpyxl") as xw:
        dfe.to_excel(xw, index=False, sheet_name="Campingplätze")
        ws = xw.sheets["Campingplätze"]
        ws.freeze_panes = "C2"
        ws.auto_filter.ref = ws.dimensions
        # Spaltenbreiten grob anpassen
        from openpyxl.utils import get_column_letter
        for i, (_, label) in enumerate(cols, 1):
            width = max(12, min(50, len(label) + 4))
            if label in ("Rechenbeispiel Tinyhäuser", "Top-Argument", "Website", "Schutzgebiet",
                         "B-Pläne (amtlich)", "B-Plan-PDFs", "Booking-Link (manuell)",
                         "Bestandsalter / Erneuerung"):
                width = 55
            ws.column_dimensions[get_column_letter(i)].width = width
        # Blatt Marktpreise
        mp_path = C.DATA / ("marktpreise_%s.json" % region_name)
        if mp_path.exists():
            mp = json.loads(mp_path.read_text(encoding="utf-8"))
            rows = []
            b = mp.get("benchmarks", {})
            rows.append(["BENCHMARKS", "", ""])
            for k, v in b.items():
                rows.append([k, str(v), ""])
            rows.append(["", "", ""])
            rows.append(["PORTAL-ANGEBOTE (GlampingHub, Luxus-Segment)", "EUR/Nacht", "Typ/Ort"])
            for o in mp.get("portal_angebote", []):
                rows.append([o["name"], o.get("preis_nacht"),
                             "%s | %s | %s" % (o.get("typ", ""), o.get("ort", ""), o["url"])])
            rows.append(["", "", ""])
            rows.append(["UNTERKUNFTS-PREISE VON PLATZ-WEBSITES", "EUR/Nacht", "Typ"])
            for o in mp.get("website_preise", []):
                rows.append([o["name"], o.get("preis_nacht"), o.get("typ") or ""])
            pd.DataFrame(rows, columns=["Name / Kennzahl", "Wert", "Details"]).to_excel(
                xw, index=False, sheet_name="Marktpreise")
            ws2 = xw.sheets["Marktpreise"]
            ws2.column_dimensions["A"].width = 65
            ws2.column_dimensions["B"].width = 18
            ws2.column_dimensions["C"].width = 90
            # Blatt Booking-Hausboote (echter Browser-Scrape)
            boats = mp.get("booking_hausboote", [])
            if boats:
                brows = [[b["name"], b.get("preis_nacht"), b.get("preis_gesamt"),
                          b.get("ort", ""), b.get("bewertung", ""), b.get("hinweis", ""), b["url"]]
                         for b in boats]
                pd.DataFrame(brows, columns=["Hausboot / Anbieter", "EUR/Nacht",
                             "Gesamtpreis 3 Nächte", "Ort", "Bewertung", "Hinweis", "Booking-URL"]
                             ).to_excel(xw, index=False, sheet_name="Booking Hausboote")
                wsb = xw.sheets["Booking Hausboote"]
                for col, w in zip("ABCDEFG", (55, 12, 18, 22, 12, 20, 70)):
                    wsb.column_dimensions[col].width = w
            # Blatt Airbnb-Angebote (echter Browser-Scrape)
            air = mp.get("airbnb_angebote", [])
            if air:
                arows = [[a["title"], a.get("desc", ""), a.get("preis_nacht"), a.get("total"),
                          a.get("rating", ""), a.get("reviews", ""), a["url"]] for a in air]
                pd.DataFrame(arows, columns=["Typ / Ort", "Beschreibung", "EUR/Nacht",
                             "Gesamtpreis 3 Nächte", "Bewertung", "# Bewertungen", "Airbnb-URL"]
                             ).to_excel(xw, index=False, sheet_name="Airbnb Angebote")
                wsa = xw.sheets["Airbnb Angebote"]
                for col, w in zip("ABCDEFG", (34, 55, 12, 18, 12, 14, 55)):
                    wsa.column_dimensions[col].width = w
    print("Excel:", out)
    return out


MAP_TMPL = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Campingplatzfinder – {label}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/esri-leaflet@3.0.12/dist/esri-leaflet.js"></script>
<style>
 body{{margin:0;font-family:system-ui,sans-serif}} #map{{height:100vh}}
 .panel{{max-width:540px;font-size:13px;line-height:1.45}}
 .leaflet-popup-content{{max-height:62vh;overflow-y:auto;overflow-x:hidden;margin:12px 14px}}
 .leaflet-popup-content-wrapper{{border-radius:8px}}
 .panel h3{{margin:0 0 6px}} .panel img{{width:100%;border-radius:6px;margin:6px 0}}
 .badge{{display:inline-block;padding:1px 7px;border-radius:9px;color:#fff;font-size:11px;margin-right:4px}}
 table.kv td{{padding:1px 6px 1px 0;vertical-align:top}} table.kv td:first-child{{color:#666}}
 #filter{{position:absolute;top:10px;right:10px;z-index:1000;background:#fff;padding:10px 14px;
   border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.3);font-size:13px;max-height:92vh;overflow:auto;width:250px}}
 #filter summary{{cursor:pointer;font-weight:600;margin:4px 0}}
 #filter .fgroup{{border-top:1px solid #eee;padding:4px 0}}
 #filter label{{display:block;margin:1px 0;font-weight:400}}
 #fToggle{{position:absolute;top:10px;right:10px;z-index:1001;background:#1a5276;color:#fff;
   border:none;border-radius:8px;padding:8px 12px;font-size:14px;cursor:pointer;box-shadow:0 1px 6px rgba(0,0,0,.3)}}
 #fCount{{font-size:12px;color:#555;margin-top:6px}}
 .carousel{{position:relative;margin:6px 0}}
 .carousel .cimg{{width:100%;height:190px;object-fit:cover;border-radius:6px;display:block}}
 .carousel .clabel{{font-size:11px;color:#666;text-align:center;margin-top:2px}}
 .carousel button{{position:absolute;top:80px;background:rgba(0,0,0,.45);color:#fff;border:none;
   border-radius:50%;width:28px;height:28px;font-size:15px;cursor:pointer;line-height:1}}
 .carousel .cprev{{left:4px}} .carousel .cnext{{right:4px}}
 .carousel .cdot{{text-align:center;font-size:10px;color:#999}}
 .leaflet-control-layers{{font-size:12px}}
 #legend{{position:absolute;bottom:20px;left:10px;z-index:1000;background:#fff;padding:8px 12px;
   border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.3);font-size:12px;line-height:1.7}}
 .dot{{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:6px}}
 .info{{display:inline-block;width:14px;height:14px;border-radius:50%;background:#8aa;color:#fff;
   font-size:10px;font-style:normal;text-align:center;line-height:14px;cursor:help;margin-left:4px;
   position:relative;vertical-align:middle}}
 .info .tip{{display:none;position:absolute;left:16px;top:-6px;width:240px;background:#333;color:#fff;
   padding:7px 9px;border-radius:6px;font-size:11px;line-height:1.4;z-index:2000;text-align:left;
   font-weight:400;box-shadow:0 2px 8px rgba(0,0,0,.4)}}
 .info:hover .tip{{display:block}}
</style></head><body>
<div id="map"></div>
<button id="fToggle">Filter ▾</button>
<div id="filter" style="display:none">
 <b>Filter</b> <span id="fReset" style="float:right;cursor:pointer;color:#2c7fb8;margin-right:10px;font-weight:400" title="alle Filter auf Standard zurücksetzen">↺ zurücksetzen</span> <span style="float:right;cursor:pointer" id="fClose">✕</span>
 <details open class="fgroup"><summary>Platz-Typ</summary>
  <label><input type="checkbox" class="fClass" value="camping" checked> Campingplätze</label>
  <label><input type="checkbox" class="fClass" value="stellplatz"> reine Wohnmobilstellplätze</label>
  <label><input type="checkbox" class="fClass" value="verein"> Vereine</label>
  <label><input type="checkbox" class="fClass" value="sonstiges"> Sonstiges (Parkplatz, Biwak …)</label>
  <label><input type="checkbox" class="fClass" value="unbenannt"> unbenannte Plätze</label>
  <details style="margin:4px 0 2px 2px"><summary style="cursor:pointer;font-size:11.5px;color:#2c7fb8">ⓘ Warum sind Vereine aufgeführt?</summary>
   <div style="font-size:11.5px;line-height:1.45;color:#444;padding:4px 2px 2px">
    Erfasst werden nur Gelände, die in OpenStreetMap als <b>Campingplatz</b> eingetragen sind –
    deshalb finden sich hier nur Vereine mit Camping-Struktur (Zelt-/Wohnwagenbetrieb),
    nicht alle Sportvereine der Region.<br>
    <b>Verein mit Vereinsheim</b> (amtlich erfasste Wohn-/Wirtschafts-/öffentliche Gebäude, ALKIS):
    standardmäßig <b>ausgeblendet</b> – kein Vermietungspartner.<br>
    <b>Verein ohne erfasstes Heim</b>: sichtbar als „Einzelfall prüfen“ – oft nur eine Wiese
    am Wasser, die für Tinyhäuser interessant sein kann.<br>
    Hinweis: MV liefert über freie Dienste keine Gebäudetypen – dort ist die Heim-Prüfung offen;
    ausgeblendete Vereine zeigt der Filter oben.
   </div></details>
 </details>
 <details open class="fgroup"><summary>Wasser &amp; Hausboot</summary>
  <label><input type="checkbox" id="fWater"> nur direkt am Wasser (≤50 m)</label>
  <label><input type="checkbox" id="fHb"> nur Hausboot-taugliches Gewässer</label>
  <label>Gewässer-Typ:
   <select id="fWb"><option value="">alle</option>
    <option>see/stausee</option><option>see/stausee (Name)</option>
    <option>fluss/kanal</option><option>teich/becken</option>
    <option>untypisiert</option><option>bach/graben</option><option>kein/fern</option>
   </select></label>
 </details>
 <details open class="fgroup"><summary>Score &amp; Ausstattung</summary>
  <label>Score-Typ:
   <select id="fScoreKind"><option value="lead">Lead (kombiniert)</option>
    <option value="th">Tiny House</option><option value="hb">Hausboot</option></select></label>
  <label>Min-Score: <input type="range" id="fMin" min="0" max="100" value="0" style="width:100px">
   <span id="fMinVal">0</span></label>
  <label><input type="checkbox" id="fColor"> Marker nach diesem Score einfärben</label>
  <label><input type="checkbox" id="fPier"> nur mit Steg/Marina</label>
  <label><input type="checkbox" id="fRent"> nur mit Mietunterkünften</label>
  <label><input type="checkbox" id="fNoRent"> nur OHNE Mietunterkünfte (Lücke)</label>
  <label><input type="checkbox" id="fSeasonal"> nur mit Dauercampern</label>
 </details>
 <details class="fgroup"><summary>Bestand: Hausboot / Tinyhaus</summary>
  <label>Hausboot vorhanden:
   <select id="fHbEx"><option value="">egal</option><option value="ja">ja</option><option value="nein">nein</option></select></label>
  <label>Tinyhaus vorhanden:
   <select id="fThEx"><option value="">egal</option><option value="ja">ja</option><option value="nein">nein</option></select></label>
 </details>
 <details class="fgroup"><summary>Bebaubarkeit</summary>
  <label><input type="checkbox" id="fBplan"> nur mit B-Plan</label>
  <label>Ampel:
   <select id="fFlag"><option value="">alle</option>
    <option value="grün">grün (Anteil)</option>
    <option value="gelb-grün">gelb-grün</option>
    <option value="gelb">gelb</option>
   </select></label>
 </details>
 <details class="fgroup"><summary>Kontakt &amp; Daten</summary>
  <label><input type="checkbox" id="fWeb"> nur mit eigener Website</label>
  <label><input type="checkbox" id="fOnlineAny"> nur mit Online-Auftritt (Website oder Verzeichnis)</label>
  <label><input type="checkbox" id="fEmail"> nur mit E-Mail</label>
  <label><input type="checkbox" id="fSicht"> nur Plätze mit KI-Luftbild-Prüfung (Bestand per Luftbild gesichtet)</label>
 </details>
 <div id="fCount"></div>
</div>
<div id="legend">
 <b>Lead-Score</b><br>
 <span class="dot" style="background:#d73027"></span>≥ 70 heißer Lead<br>
 <span class="dot" style="background:#fc8d59"></span>50–69 interessant<br>
 <span class="dot" style="background:#fee08b"></span>30–49 prüfen<br>
 <span class="dot" style="background:#91bfdb"></span>&lt; 30 gering
</div>
<script>
const SITES = {sites_json};
const map = L.map('map').setView([{clat}, {clon}], 9);
const osm = L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
  {{maxZoom:19, attribution:'© OpenStreetMap'}});
const dop = L.tileLayer.wms('{dop_url}', {{
  layers:'{dop_layer}', format:'image/jpeg', transparent:false,
  attribution:'{geo_attr}'}});
const sat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}',
  {{maxZoom:19, attribution:'© Esri World Imagery'}});
osm.addTo(map);
const bases = {{'Karte (OSM)':osm,'Luftbild aktuell (DOP20)':dop,'Satellit (Esri)':sat}};
const overlays = {{}};
{extra_layers}
const layerCtl = L.control.layers(bases, overlays,
  {{collapsed:false, position:'topleft'}}).addTo(map);

function color(s){{return s>=70?'#d73027':s>=50?'#fc8d59':s>=30?'#fee08b':'#91bfdb';}}
function esc(t){{return (t==null?'':String(t)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');}}
const INFO={{
 flurst:'Flurstück = kleinste amtliche Einheit im Liegenschaftskataster: ein vermessenes, nummeriertes Stück Land. Mehrere Flurstücke bilden ein Grundstück. Hier: Anzahl der Flurstücke unter dem Platz und deren Gesamtfläche – wichtig für Ausbau-Reserve und spätere Eigentümer-/Grundbuch-Anfragen.',
 alkis:'ALKIS = amtliches Liegenschaftskataster der Vermessungsämter (keine Schätzung). Zeigt Anzahl, Grundfläche und Nutzungstyp der offiziell erfassten Gebäude auf dem Platz – die harte Faktenbasis für festen Bestand (z. B. Vereinsheim-Prüfung).',
 ampel:'Vorabeinschätzung, ob ortsfeste Tinyhäuser genehmigungsfähig wären: grün(-gelb) = B-Plan mit Ferienhaus-/Campinggebiet oder feste Unterkünfte vorhanden → gute Basis. gelb = unklar (B-Plan ohne Camping-Bezug oder Außenbereich §35 BauGB) → Bauamt fragen. Heuristik, keine Rechtsauskunft.',
 wasser:'Einheitliche Einstufung: OSM-Gewässertyp + gemessene Fläche des nächsten Gewässers (Hektar). Hausboot „ja" nur bei See/Stausee bzw. ≥5 ha; Teich/Fluss/Kanal/Bach = „nein". Quelle je Platz unten angegeben; einzelne Korrekturen aus KI-Luftbild-Sichtungen.',
 sicht:'Eine KI hat das aktuelle amtliche Luftbild (DOP20) des Platzes gesichtet und Bestand, Zustand und Erweiterungsflächen beschrieben. Luftbildeindruck – keine Vor-Ort-Prüfung.',
 miet:'Aus der Betreiber-Website ausgelesene Mietunterkünfte. Kann Fehltreffer enthalten (z. B. Angebote des Betreibers an anderem Ort) – vor Kontakt prüfen.',
 score:'Zwei getrennte Bewertungen: Tiny-House-Score (Wasserlage nur kleiner Bonus, dafür Bebaubarkeit) und Hausboot-Score (Wasserlage, Gewässer-Eignung, Steg und Uferlänge dominant; ohne Hausboot-Gewässer max 40). Der Lead-Score kombiniert beides für die Rangliste. Je Zeile: erreichte / erreichbare Punkte. Heuristik zur Vorauswahl.',
 modern:'Wie modern und gepflegt ist die eigene Website (0–10)? Merkmale: mobil-tauglich, HTTPS, Online-Buchung, aktuelles Jahr, Social Media, modernes Framework; Abzug für Uralt-Technik oder veraltetes Copyright. Proxy für Investitionsbereitschaft: wer die Website pflegt, pflegt oft auch den Platz. Reine Erreichbarkeit gibt keine Punkte (ist bereits Filterkriterium).',
 flaeche:'Genutzte Platzfläche aus OpenStreetMap: die dort von Freiwilligen eingezeichnete Platzgrenze (Polygon), berechnet aus der Geometrie. Keine AI-Bilderkennung, kein amtlicher Plan – kann ungenau sein (±30 %). Die amtliche Eigentumsfläche steht, sofern erfasst, unter „Grundstück gesamt" (Liegenschaftskataster). Fehlt der OSM-Umriss (Platz nur als Punkt erfasst), wird eine SCHÄTZUNG gezeigt (~, gestrichelte Linie auf der Karte): Umriss der zugeordneten Kataster-Flurstücke bzw. einer nahen OSM-Freizeitfläche – das ist die Grundstücks-/Umgebungsgrenze, nicht die exakt genutzte Campingfläche. Liefert auch das Kataster nichts, fehlt die Zeile.',
 rechen:'Modellrechnung, kein Businessplan: 1–5 Tinyhäuser je Platz (grobe Schätzung aus der Flächenreserve: Grundstück − genutzte Fläche, ~250 m² je Einheit inkl. Abstand/Grün; ohne Flächenangaben Standard 3) × Nachtpreis × 140 vermietbare Nächte/Jahr (Auslastungsannahme, ganzjährig). Nachtpreis aus echten Airbnb-/Booking-Angeboten im Umkreis 25 km: ganze kleine Unterkünfte mit Küche für ~4 Personen (Ferienhaus, Bungalow, Chalet, Ferienwohnung …) – keine Zimmer in fremder Wohnung, keine Hotels, keine Zelte/Schlaffässer. Median minus 20 % Camping-Abschlag gegenüber Premium-Inseraten; zu wenige Angebote → Regions-Median. Stellplatz-Vergleich: eigener Website-Preis oder Regions-Median × 110 Nächte.',
 bau:'Unterteilung nach Bebaubarkeits-Ampel: 15/15 = B-Plan weist Ferienhaus-/Campinggebiet aus (grün); 12/15 = feste Unterkünfte vorhanden, Details prüfen (gelb-grün); 8/15 = unklar, Bauamt fragen (gelb); 0/15 = keine belastbare Basis.'
}};
function info(k){{return '<span class="info">i<span class="tip">'+INFO[k]+'</span></span>';}}
function carStep(btn,d){{
 const c=btn.closest('.carousel');
 const slides=JSON.parse(c.getAttribute('data-slides'));
 let i=(+c.getAttribute('data-i')+d+slides.length)%slides.length;
 c.setAttribute('data-i',i);
 const img=c.querySelector('.cimg');
 img.style.opacity=1; img.src=slides[i].src;
 c.querySelector('.clabel').textContent=slides[i].label;
 const dot=c.querySelector('.cdot'); if(dot) dot.textContent=(i+1)+' / '+slides.length;
}}
function popupHtml(p){{
 let h='<div class="panel"><h3>'+esc(p.name)+'</h3>';
 h+='<span class="badge" style="background:'+color(p.lead_score)+'">Lead '+(p.lead_score??'–')+'</span>';
 h+='<span class="badge" style="background:#8e6c3a" title="Tiny-House-Score">TH '+(p.score_th??'–')+'</span>';
 h+='<span class="badge" style="background:#2c7fb8" title="Hausboot-Score">HB '+(p.score_hb??'–')+'</span>';
 if(p.water_score>=70) h+='<span class="badge" style="background:#1a9850">Top-Wasserlage</span>';
 if(p.site_class&&p.site_class!=='camping') h+='<span class="badge" style="background:#777"'+(p.class_reason?' title="'+esc(p.class_reason)+'"':'')+'>'+esc(p.site_class)+'</span>';
 if(p.houseboat_water==='ja') h+='<span class="badge" style="background:#2c7fb8">Hausboot-Gewässer</span>';
 else if(p.houseboat_water==='nein'&&p.water_name) h+='<span class="badge" style="background:#999">kein Hausboot-Gewässer</span>';
 // Bild-Karussell: aktuelles DOP + Hist + Website-Fotos
 const slides=[];
 if(p.img) slides.push({{src:'luftbilder/'+p.img,label:'Luftbild aktuell'+(p.imgyear?' ('+p.imgyear+')':'')}});
 if(p.hist) for(const t of p.hist) slides.push({{src:t.img,label:t.label}});
 if(p.webimg) p.webimg.forEach((w,i)=>slides.push({{src:'webbilder/'+w,label:'Website-Foto '+(i+1)}}));
 if(slides.length){{
  h+='<div class="carousel" data-i="0" data-slides="'+esc(JSON.stringify(slides))+'">';
  h+='<img class="cimg" src="'+slides[0].src+'" loading="lazy" onerror="this.style.opacity=.2">';
  h+='<div class="clabel">'+esc(slides[0].label)+'</div>';
  if(slides.length>1){{
   h+='<button class="cprev" onclick="carStep(this,-1)">‹</button><button class="cnext" onclick="carStep(this,1)">›</button>';
   h+='<div class="cdot">1 / '+slides.length+'</div>';
  }}
  h+='</div>';
 }}
  h+='<table class="kv">';
  const jaNein=v=>v?'ja':'nein';
  const rows=[['Gewässer',p.water_name,null],
   ['Gewässer-Typ'+info('wasser'),p.waterbody_class+(p.water_area_ha!=null?' ('+Number(p.water_area_ha).toLocaleString('de')+' ha)':''),'html'],
   ['↳ Quelle der Einstufung',p.water_class_src,null],
   ['Hausboot-Gewässer geeignet',p.houseboat_water==='ja'?'ja (See/Stausee ≥5 ha)':p.houseboat_water==='nein'?'nein (zu klein/Fluss/Teich)':'unklar – prüfen',null],
   ['Vorhanden: Hausboot / Tinyhaus',jaNein(p.has_houseboat)+' / '+jaNein(p.has_tinyhouse),null],
   ['Abstand Wasser',p.water_distance_m!=null?p.water_distance_m+' m':null,null],
   ['Uferlänge',p.shoreline_m?p.shoreline_m+' m':null,null],['Steg',p.has_pier?'ja':null,null],
   ['Fläche genutzt'+info('flaeche'),p.area_m2?Math.round(p.area_m2).toLocaleString('de')+' m²':(p.ersatz_area_m2?'~'+Math.round(p.ersatz_area_m2).toLocaleString('de')+' m² (Schätzung'+(p.ersatz_src?', '+esc(p.ersatz_src):'')+')':null),'html'],
   ['Grundstück gesamt'+info('flurst'),p.parcel_area_m2?Math.round(p.parcel_area_m2).toLocaleString('de')+' m²'+(p.parcel_count?' · '+p.parcel_count+' Flurstück'+(p.parcel_count>1?'e':''):''):null,'html'],
   ['Bebaubarkeit'+info('ampel'),p.build_flag,'html'],
   ['Dauercamper',p.seasonal?'ja':null,null],
   ['Mietunterkünfte'+info('miet'),p.rentals,'html'],['Bestandsalter',p.rental_age_est,null],
   ['Gebäude (amtl. Kataster)'+info('alkis'),p.geb?p.geb.n+' Geb., '+p.geb.flaeche.toLocaleString('de')+' m² ('+p.geb.typen.map(t=>t[0]+'×'+t[1]).join(', ')+')':null,'html'],
   ['Website-Modernität'+info('modern'),p.web_modern!=null?p.web_modern+' / 10'+(p.web_modern_info?' <span style="color:#666;font-size:11px">('+esc(p.web_modern_info)+')</span>':''):null,'html'],
   ['Preis Stellplatz',p.price_pitch?p.price_pitch+' €':null,null],
   ['Preis Unterkunft',p.price_rental?p.price_rental+' €':null,null],
   ['Luftbild-Sichtung (KI)'+info('sicht'),p.bildsichtung_txt,'html'],
   ['Schutzgebiet',p.protected_area,null],['Argument',p.top_argument,null],
   ['Rechenbeispiel'+info('rechen'),p.revenue_example,'html'],['Telefon',p.phone,null],['E-Mail',p.contact_email||p.email,null]];
  for(const [k,v,mode] of rows){{
   if(v==null||v==='')continue;
   h+='<tr><td>'+k+'</td><td>'+(mode==='html'?v:esc(v))+'</td></tr>';
  }}
  h+='</table>';
  function scoreBlock(title,val,details){{
   if(!details||!details.length)return '';
   let s='<details style="margin:6px 0"><summary style="cursor:pointer"><b>'+title+': '+(val??'–')+'/100</b>'+info('score')+'</summary>';
   s+='<table class="kv" style="margin:4px 0">';
   for(const row of details){{
    const k=row[0],v=row[1],mx=row[2];
    let vv;
    if(v==null) vv='Multiplikator/Deckel';
    else if(v<0) vv=String(v);
    else if(mx!=null) vv=v+' / '+mx;
    else vv='+'+v;
    const kk=esc(k)+(k.indexOf('Bebaubarkeit')===0?info('bau'):'');
    s+='<tr><td>'+kk+'</td><td>'+vv+'</td></tr>';
   }}
   s+='</table></details>';
   return s;
  }}
  h+=scoreBlock('Tiny-House-Score',p.score_th,p.score_th_details);
  h+=scoreBlock('Hausboot-Score',p.score_hb,p.score_hb_details);
  h+=scoreBlock('Lead-Score (Rangliste kombiniert)',p.lead_score,p.score_details);
 if(p.bplan){{
  h+='<details style="margin:6px 0"><summary style="cursor:pointer"><b>Bebauungspläne im Umkreis (amtlich)</b></summary>';
  h+='<div style="font-size:11px;color:#666;margin:3px 0">Ein B-Plan regelt, was auf den Flächen gebaut werden darf. „Sondergebiet Camping/Erholung" = Camping ausgewiesen; „Allgemeines Wohngebiet (WA)" = Wohnbebauung; „Versorgungsfläche" = z. B. Handel/Verkehr – nicht der Campingplatz selbst, sondern angrenzende Planflächen. Entscheidend ist der Plan, der das Platz-Grundstück überdeckt.</div><ul style="margin:4px 0;padding-left:18px">';
  for(const bp of p.bplan){{
   h+='<li>'+esc(bp.name)+(bp.rechtsstand?' <i>('+esc(bp.rechtsstand)+')</i>':'');
   if(bp.planart) h+='<br><span style="color:#666;font-size:12px">'+esc(bp.planart)+'</span>';
   if(bp.pdf) h+=' <a href="'+esc(bp.pdf)+'" target="_blank">Plan-PDF</a>';
   h+='</li>';
  }}
  h+='</ul></details>';
 }}
 if(p.website) h+='<a href="'+esc(p.website)+'" target="_blank">Website öffnen</a>';
 if(p.booking) h+=' · <a href="'+esc(p.booking)+'" target="_blank">Booking-Preise prüfen</a>';
 return h+'</div>';
}}
const markers=[];
for(const p of SITES){{
 const m=L.circleMarker([p.lat,p.lon],{{radius:p.lead_score>=70?9:7,
   color:'#333',weight:1,fillColor:color(p.lead_score),fillOpacity:.9}});
 m.bindPopup(()=>popupHtml(p),{{maxWidth:560}});
 if(p.geom){{
  const poly=L.geoJSON(p.geom,{{style:p.geom_ersatz?{{color:color(p.lead_score),weight:2,fillOpacity:.05,dashArray:'6 4'}}:{{color:color(p.lead_score),weight:2,fillOpacity:.08}}}});
  poly.bindPopup(()=>popupHtml(p),{{maxWidth:560}});
  m._poly=poly;
 }}
 m._p=p; markers.push(m);
}}
const group=L.layerGroup(markers).addTo(map);
const polyGroup=L.layerGroup().addTo(map);
map.on('zoomend',()=>{{
 // Platz-Umrisse erst ab Zoom 12 anzeigen (sonst zu unruhig)
 polyGroup.clearLayers();
 if(map.getZoom()>=12) for(const m of markers) if(m._poly&&group.hasLayer(m)) polyGroup.addLayer(m._poly);
}});
function applyFilter(){{
 const cls=new Set([...document.querySelectorAll('.fClass:checked')].map(c=>c.value));
 const w=document.getElementById('fWater').checked;
 const hb=document.getElementById('fHb').checked;
 const wb=document.getElementById('fWb').value;
 const mn=+document.getElementById('fMin').value;
 document.getElementById('fMinVal').textContent=mn;
 const sk=document.getElementById('fScoreKind').value;
 const scoreOf=p=>sk==='th'?(p.score_th??0):sk==='hb'?(p.score_hb??0):(p.lead_score||0);
 // Marker optional nach gewaehltem Score einfaerben
 if(document.getElementById('fColor').checked){{
  for(const m of markers){{
   const c=color(scoreOf(m._p));
   m.setStyle({{fillColor:c}});
   if(m._poly) m._poly.setStyle({{color:c}});
  }}
 }}
 const pier=document.getElementById('fPier').checked;
 const rent=document.getElementById('fRent').checked;
 const norent=document.getElementById('fNoRent').checked;
 const seas=document.getElementById('fSeasonal').checked;
 const bplan=document.getElementById('fBplan').checked;
 const flag=document.getElementById('fFlag').value;
 const onlineany=document.getElementById('fOnlineAny').checked;
 const web=document.getElementById('fWeb').checked;
 const hbex=document.getElementById('fHbEx').value;
 const thex=document.getElementById('fThEx').value;
 const email=document.getElementById('fEmail').checked;
 const sicht=document.getElementById('fSicht').checked;
 group.clearLayers();
 let n=0;
 const anyClassFilter=[...document.querySelectorAll('.fClass')].some(c=>c.checked!==c.defaultChecked);
 for(const m of markers){{
  const p=m._p;
  // Initial: nur nicht-ausgeblendete Plaetze; sobald Typ-Filter angefasst, gilt Auswahl
  if(!anyClassFilter&&!p.init_visible)continue;
  if(anyClassFilter&&!cls.has(p.site_class||'camping'))continue;
  if(w&&!(p.water_distance_m!=null&&p.water_distance_m<=50))continue;
  if(hb&&p.houseboat_water!=='ja')continue;
  if(wb&&p.waterbody_class!==wb)continue;
  if(scoreOf(p)<mn)continue;
  if(pier&&!(p.has_pier||(p.marina_distance_m!=null&&p.marina_distance_m<100)))continue;
  if(rent&&!p.rentals)continue;
  if(norent&&p.rentals)continue;
  if(seas&&!p.seasonal)continue;
  if(bplan&&!(p.bplan&&p.bplan.length))continue;
  if(flag&&!(p.build_flag||'').includes(flag))continue;
  if(onlineany&&!(p.online_status==='website'||p.online_status==='nur_verzeichnis'))continue;
  if(web&&p.online_status!=='website')continue;
  if(hbex==='ja'&&!p.has_houseboat)continue;
  if(hbex==='nein'&&p.has_houseboat)continue;
  if(thex==='ja'&&!p.has_tinyhouse)continue;
  if(thex==='nein'&&p.has_tinyhouse)continue;
  if(email&&!(p.contact_email||p.email))continue;
  if(sicht&&!p.bildsichtung_txt)continue;
  group.addLayer(m); n++;
 }}
 document.getElementById('fCount').textContent=n+' von '+markers.length+' Plätzen sichtbar';
 polyGroup.clearLayers();
 if(map.getZoom()>=12) for(const m of markers) if(m._poly&&group.hasLayer(m)) polyGroup.addLayer(m._poly);
}}
for(const el of document.querySelectorAll('#filter input,#filter select')){{
 el.onchange=applyFilter;
}}
document.getElementById('fMin').oninput=applyFilter;
// Alle Filter auf Standard zuruecksetzen (verhindert '0 Plaetze' durch
// vergessene Kombinationen aus anderen Filter-Gruppen)
document.getElementById('fReset').onclick=()=>{{
 for(const el of document.querySelectorAll('#filter input,#filter select')){{
  if(el.type==='checkbox') el.checked=el.defaultChecked;
  else if(el.tagName==='SELECT') el.selectedIndex=0;
  else if(el.type==='range') el.value=el.defaultValue;
 }}
 applyFilter();
}};
document.getElementById('fToggle').onclick=()=>{{
 const f=document.getElementById('filter');
 const open=f.style.display!=='none';
 f.style.display=open?'none':'block';
 document.getElementById('fToggle').style.display=open?'block':'none';
}};
document.getElementById('fClose').onclick=()=>{{
 document.getElementById('filter').style.display='none';
 document.getElementById('fToggle').style.display='block';
}};
applyFilter();
</script></body></html>
"""


def export_map(df, region_name):
    region = C.load_region(region_name)
    # Luftbilder in OUTPUT kopieren (falls DATA woanders liegt)
    src = C.DATA / ("luftbild_meta_%s.json" % region_name)
    meta = json.loads(src.read_text(encoding="utf-8")) if src.exists() else {}
    imgdir_src = C.OUTPUT / "luftbilder"
    fields = ["id", "name", "category", "lat", "lon", "area_m2", "website",
              "phone", "email", "lead_score", "score_th", "score_hb",
              "water_score", "water_name",
              "water_distance_m", "shoreline_m", "has_pier",
              "protected_area", "parcel_area_m2", "parcel_count", "build_flag", "seasonal",
              "rentals", "rental_age_est", "price_pitch", "price_rental",
              "top_argument", "revenue_example", "contact_email", "buildings",
              "bildsichtung_txt", "site_class", "class_reason", "online_status",
              "waterbody_class", "houseboat_water", "default_hidden",
              "web_images", "marina_distance_m", "has_houseboat", "has_tinyhouse",
              "water_area_ha", "water_class_src", "web_modern", "web_modern_info",
              "name_source", "ersatz_area_m2", "ersatz_src"]
    # History-Infos (hist. Luftbilder) und B-Pläne laden
    hist = {}
    conn = C.db()
    try:
        hist = {r["site_id"]: json.loads(r["info"]) for r in
                conn.execute("SELECT site_id, info FROM history_info")}
    except Exception:
        pass
    bplans = {}
    for r in conn.execute("""SELECT e.site_id, e.bplan_info FROM enrichment e
            JOIN sites s ON s.id=e.site_id WHERE s.region=? AND e.bplan_info IS NOT NULL""",
            (region_name,)):
        try:
            bplans[r["site_id"]] = json.loads(r["bplan_info"])
        except Exception:
            pass
    conn.close()
    from urllib.parse import quote
    sites = []
    for _, r in df.iterrows():
        d = {k: (None if pd.isna(r.get(k)) else r.get(k)) for k in fields}
        m = meta.get(r["id"], {})
        if m.get("file") and (imgdir_src / m["file"]).exists():
            d["img"] = m["file"]
            d["imgyear"] = m.get("year")
        # Website-Fotos (Subagent s18/web_images)
        try:
            wi = json.loads(r.get("web_images") or "null")
            if wi:
                d["webimg"] = [w for w in wi
                               if (C.OUTPUT / "webbilder" / w).exists()]
        except Exception:
            pass
        hi = hist.get(r["id"], {})
        h = hi.get("hist_luftbilder", {})
        caps = hi.get("esri_aufnahmedaten", {})
        timeline = []
        seen_cap = set()
        for y in sorted(h, key=lambda s: int(s)):
            if not (C.OUTPUT / h[y]).exists():
                continue
            cap = caps.get(y)
            label = cap[:4] if cap else y
            # identische Quellbilder nur einmal zeigen: gleiches
            # Aufnahmedatum ODER gleiches Anzeigejahr (neuestes Bild gewinnt)
            dedup_key = cap if cap else y
            if dedup_key in seen_cap or label in seen_cap:
                continue
            seen_cap.add(dedup_key)
            seen_cap.add(label)
            # nur Aufnahmejahr anzeigen (Release-Jahr ist fuer Nutzer irrelevant)
            timeline.append({"label": label, "img": h[y]})
        if timeline:
            d["hist"] = timeline
        try:
            gb = json.loads(r.get("buildings") or "null")
            if gb:
                d["geb"] = {"n": gb["n"], "flaeche": gb["flaeche_m2"],
                            "typen": list(gb["typen"].items())[:6]}
        except Exception:
            pass
        for key, dst in (("score_details", "score_details"),
                         ("score_th_details", "score_th_details"),
                         ("score_hb_details", "score_hb_details")):
            try:
                sd = json.loads(r.get(key) or "null")
                if sd:
                    d[dst] = sd
            except Exception:
                pass
        bp = bplans.get(r["id"])
        if bp:
            bl = []
            for p in bp.get("plans", [])[:4]:
                pdf = next((doc["url"] for doc in p.get("dokumente", [])
                            if "rechtsplan" in doc["typ"].lower()), None)
                bl.append({"name": p["name"], "rechtsstand": p.get("rechtsstand"),
                           "planart": p.get("nutzung") or p.get("planart"),
                           "pdf": pdf})
            d["bplan"] = bl
        if d["name"] and d["name"] != "(unbenannt)":
            d["booking"] = ("https://www.booking.com/searchresults.de.html?ss=%s"
                            "&checkin=2026-07-10&checkout=2026-07-13&group_adults=2&no_rooms=1"
                            % quote(d["name"]))
        if r.get("geometry") and not pd.isna(r["geometry"]):
            try:
                d["geom"] = json.loads(r["geometry"])
            except Exception:
                pass
        # Ersatz-Umriss (Kataster/OSM-Freizeitflaeche) fuer Punkt-Plaetze:
        # gestrichelt anzeigen, kein OSM-Polygon vorhanden
        # (ersatz_geom ist NICHT in fields -> direkt aus r lesen)
        if not d.get("geom") and r.get("ersatz_geom") and not pd.isna(r["ersatz_geom"]):
            try:
                d["geom"] = json.loads(r["ersatz_geom"])
                d["geom_ersatz"] = True
            except Exception:
                pass
        d.pop("ersatz_geom", None)  # Geometrie steckt bereits in geom
        # Default-Ausblendung: nur echte Camping-Plaetze mit Online-Praesenz
        # sichtbar; Rest per Filter zuschaltbar. (SQLite liefert 0/1 als TEXT!)
        d["init_visible"] = str(d.get("default_hidden") or "0") != "1"
        sites.append(d)
    bbox = region["bbox"]
    # Overlays je Bundesland aus Regions-Config (ALKIS + historische DOPs)
    extra = []
    if region.get("dop_kind") == "arcgis":
        # ST: DOP als ArcGIS ImageServer (WMS zurzeit gestoert)
        extra.append(
            "bases['Luftbild aktuell (DOP20)'] = L.esri.imageMapLayer({url:'%s', "
            "format:'jpgpng', attribution:'%s'});"
            % (region["wms_dop"], region.get("geoquelle", "")))
        extra.append(
            "bases['B-Pläne (ARIS)'] = L.esri.dynamicMapLayer({url:'%s', "
            "layers:[2,6], opacity:0.5, attribution:'%s'});"
            % (region.get("bplan_mapserver", ""), region.get("geoquelle", "")))
    if region.get("alkis_wms"):
        extra.append(
            "overlays['Flurstücksgrenzen (ALKIS)'] = L.tileLayer.wms('%s', "
            "{layers:'%s', format:'image/png', transparent:true, attribution:'%s', "
            "version:'1.3.0', minZoom:15});"
            % (region["alkis_wms"], region.get("alkis_wms_layer", ""),
               region.get("geoquelle", "")))
    for year, svc in sorted(region.get("hist_dop", {}).items()):
        extra.append(
            "bases['Historisch %s (s/w)'] = L.tileLayer.wms('%s', "
            "{layers:'%s', format:'image/jpeg', transparent:false, attribution:'%s'});"
            % (year, svc[0], svc[1], region.get("geoquelle", "")))
    html = MAP_TMPL.format(
        label=region["label"],
        sites_json=json.dumps(sites, ensure_ascii=False),
        clat=(bbox[0] + bbox[2]) / 2, clon=(bbox[1] + bbox[3]) / 2,
        dop_url=region.get("wms_dop", ""), dop_layer=region.get("wms_dop_layer", ""),
        geo_attr=region.get("geoquelle", ""),
        extra_layers="\n".join(extra))
    out = C.OUTPUT / ("karte_%s.html" % region_name)
    out.write_text(html, encoding="utf-8")
    print("Karte:", out)
    return out


def run(region_name):
    df = load_df(region_name)
    print("Zeilen:", len(df))
    export_excel(df, region_name)
    export_map(df, region_name)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "seenplatte")
