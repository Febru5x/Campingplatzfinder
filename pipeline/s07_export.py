"""Schritt 07: Export als Excel + interaktive Leaflet-Karte.

Aufruf:  python -m pipeline.s07_export seenplatte
"""
import json
import shutil
import sys

import pandas as pd

from . import common as C

COLS = [
    ("lead_score", "Lead-Score"),
    ("name", "Name"),
    ("category", "Kategorie"),
    ("water_score", "Wasser-Score"),
    ("water_name", "Gewässer"),
    ("water_distance_m", "Abstand Wasser (m)"),
    ("shoreline_m", "Uferlänge (m)"),
    ("has_pier", "Steg"),
    ("marina_distance_m", "Marina-Abstand (m)"),
    ("motorboat_flag", "Motorboot"),
    ("protected_area", "Schutzgebiet"),
    ("area_m2", "OSM-Fläche (m²)"),
    ("parcel_area_m2", "Flurstück-Fläche (m²)"),
    ("parcel_count", "Flurstücke (#)"),
    ("flurstuecke", "Flurstück-Kennzeichen"),
    ("build_flag", "Bebaubarkeit (Ampel)"),
    ("bplan_namen", "B-Pläne (amtlich)"),
    ("bplan_links", "B-Plan-PDFs"),
    ("rental_age_est", "Bestandsalter / Erneuerung"),
    ("gebaeude_alkis", "Gebäude (ALKIS amtlich)"),
    ("bildsichtung_txt", "KI-Bildsichtung (Bestand/Zustand)"),
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
            d["parcel_count"] = len(plist)
            d["flurstuecke"] = "; ".join(
                p.get("kennzeichen", "?") for p in plist[:8])
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
 .panel{{max-width:340px;font-size:13px;line-height:1.45}}
 .panel h3{{margin:0 0 6px}} .panel img{{width:100%;border-radius:6px;margin:6px 0}}
 .badge{{display:inline-block;padding:1px 7px;border-radius:9px;color:#fff;font-size:11px;margin-right:4px}}
 table.kv td{{padding:1px 6px 1px 0;vertical-align:top}} table.kv td:first-child{{color:#666}}
 #filter{{position:absolute;top:10px;right:10px;z-index:1000;background:#fff;padding:10px 14px;
   border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.3);font-size:13px}}
 .leaflet-control-layers{{font-size:12px}}
 #legend{{position:absolute;bottom:20px;left:10px;z-index:1000;background:#fff;padding:8px 12px;
   border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.3);font-size:12px;line-height:1.7}}
 .dot{{display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:6px}}
</style></head><body>
<div id="map"></div>
<div id="filter">
 <b>Filter</b><br>
 <label><input type="checkbox" id="fWater"> nur direkt am Wasser (≤50 m)</label><br>
 <label><input type="checkbox" id="fScore"> nur Lead-Score ≥ 50</label><br>
 <label>Min-Score: <input type="range" id="fMin" min="0" max="100" value="0" style="width:110px">
 <span id="fMinVal">0</span></label>
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
function esc(t){{return (t==null?'':String(t)).replace(/&/g,'&amp;').replace(/</g,'&lt;');}}
function popupHtml(p){{
 let h='<div class="panel"><h3>'+esc(p.name)+'</h3>';
 h+='<span class="badge" style="background:'+color(p.lead_score)+'">Score '+(p.lead_score??'–')+'</span>';
 if(p.water_score>=70) h+='<span class="badge" style="background:#1a9850">Top-Wasserlage</span>';
 if(p.img) h+='<img src="luftbilder/'+p.img+'" loading="lazy">';
 if(p.hist&&p.hist.length){{
  h+='<div style="display:flex;gap:4px;flex-wrap:wrap">';
  for(const t of p.hist) h+='<figure style="margin:0;flex:1;min-width:45%"><img src="'+t.img+'" loading="lazy"><figcaption style="font-size:10px;color:#666">'+esc(t.label)+'</figcaption></figure>';
  h+='</div>';
 }}
 h+='<table class="kv">';
 const rows=[['Gewässer',p.water_name],['Abstand Wasser',p.water_distance_m!=null?p.water_distance_m+' m':null],
  ['Uferlänge',p.shoreline_m?p.shoreline_m+' m':null],['Steg',p.has_pier?'ja':null],
  ['Motorboot',p.motorboat_flag],['Fläche',p.area_m2?Math.round(p.area_m2).toLocaleString('de')+' m²':null],
  ['Flurstücke',p.parcel_area_m2?Math.round(p.parcel_area_m2).toLocaleString('de')+' m²':null],
  ['Bebaubarkeit',p.build_flag],['Dauercamper',p.seasonal?'ja':null],
  ['Mietunterkünfte',p.rentals],['Bestandsalter',p.rental_age_est],
  ['Gebäude (ALKIS)',p.geb?p.geb.n+' Geb., '+p.geb.flaeche.toLocaleString('de')+' m² ('+p.geb.typen.map(t=>t[0]+'×'+t[1]).join(', ')+')':null],
  ['Preis Stellplatz',p.price_pitch?p.price_pitch+' €':null],
  ['Preis Unterkunft',p.price_rental?p.price_rental+' €':null],
  ['KI-Bildsichtung',p.bildsichtung_txt],
  ['Schutzgebiet',p.protected_area],['Argument',p.top_argument],
  ['Rechenbeispiel',p.revenue_example],['Telefon',p.phone],['E-Mail',p.contact_email||p.email]];
 for(const [k,v] of rows) if(v!=null&&v!=='') h+='<tr><td>'+k+'</td><td>'+esc(v)+'</td></tr>';
 h+='</table>';
 if(p.bplan){{
  h+='<b>B-Pläne (amtlich):</b><ul style="margin:4px 0;padding-left:18px">';
  for(const bp of p.bplan){{
   h+='<li>'+esc(bp.name)+(bp.rechtsstand?' <i>('+esc(bp.rechtsstand)+')</i>':'');
   if(bp.pdf) h+=' <a href="'+esc(bp.pdf)+'" target="_blank">Plan-PDF</a>';
   h+='</li>';
  }}
  h+='</ul>';
 }}
 if(p.website) h+='<a href="'+esc(p.website)+'" target="_blank">Website öffnen</a>';
 if(p.booking) h+=' · <a href="'+esc(p.booking)+'" target="_blank">Booking-Preise prüfen</a>';
 return h+'</div>';
}}
const markers=[];
for(const p of SITES){{
 const m=L.circleMarker([p.lat,p.lon],{{radius:p.lead_score>=70?9:7,
   color:'#333',weight:1,fillColor:color(p.lead_score),fillOpacity:.9}});
 m.bindPopup(()=>popupHtml(p),{{maxWidth:360}});
 if(p.geom){{
  const poly=L.geoJSON(p.geom,{{style:{{color:color(p.lead_score),weight:2,fillOpacity:.08}}}});
  poly.bindPopup(()=>popupHtml(p),{{maxWidth:360}});
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
 const w=document.getElementById('fWater').checked;
 const s50=document.getElementById('fScore').checked;
 const mn=+document.getElementById('fMin').value;
 document.getElementById('fMinVal').textContent=mn;
 group.clearLayers();
 for(const m of markers){{
  const p=m._p;
  if(w&&!(p.water_distance_m!=null&&p.water_distance_m<=50))continue;
  if(s50&&!(p.lead_score>=50))continue;
  if((p.lead_score||0)<mn)continue;
  group.addLayer(m);
 }}
 polyGroup.clearLayers();
 if(map.getZoom()>=12) for(const m of markers) if(m._poly&&group.hasLayer(m)) polyGroup.addLayer(m._poly);
}}
document.getElementById('fWater').onchange=applyFilter;
document.getElementById('fScore').onchange=applyFilter;
document.getElementById('fMin').oninput=applyFilter;
</script></body></html>
"""


def export_map(df, region_name):
    region = C.load_region(region_name)
    # Luftbilder in OUTPUT kopieren (falls DATA woanders liegt)
    src = C.DATA / ("luftbild_meta_%s.json" % region_name)
    meta = json.loads(src.read_text(encoding="utf-8")) if src.exists() else {}
    imgdir_src = C.OUTPUT / "luftbilder"
    fields = ["id", "name", "category", "lat", "lon", "area_m2", "website",
              "phone", "email", "lead_score", "water_score", "water_name",
              "water_distance_m", "shoreline_m", "has_pier", "motorboat_flag",
              "protected_area", "parcel_area_m2", "build_flag", "seasonal",
              "rentals", "rental_age_est", "price_pitch", "price_rental",
              "top_argument", "revenue_example", "contact_email", "buildings",
              "bildsichtung_txt"]
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
        hi = hist.get(r["id"], {})
        h = hi.get("hist_luftbilder", {})
        caps = hi.get("esri_aufnahmedaten", {})
        timeline = []
        seen_cap = set()
        for y in sorted(h, key=lambda s: int(s)):
            if not (C.OUTPUT / h[y]).exists():
                continue
            cap = caps.get(y)
            # identische Quellbilder (gleiches Aufnahmedatum) nur einmal zeigen
            dedup_key = cap if cap else y
            if dedup_key in seen_cap:
                continue
            seen_cap.add(dedup_key)
            label = cap[:4] if cap else y
            if cap and cap[:4] != y:
                label = "%s (Release %s)" % (cap[:4], y)
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
        bp = bplans.get(r["id"])
        if bp:
            bl = []
            for p in bp.get("plans", [])[:4]:
                pdf = next((doc["url"] for doc in p.get("dokumente", [])
                            if "rechtsplan" in doc["typ"].lower()), None)
                bl.append({"name": p["name"], "rechtsstand": p.get("rechtsstand"),
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
