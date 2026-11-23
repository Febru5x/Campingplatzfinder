"""Schritt 08: PDF-artige Dossiers (HTML) fuer Top-Leads.

Pro Platz eine druckfertige HTML-Seite mit Luftbild, Fakten, Rechenbeispiel.
Aufruf:  python -m pipeline.s08_dossiers seenplatte --top=20
"""
import json
import sys
from html import escape

from . import common as C

TMPL = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>{name}</title>
<style>
 body{{font-family:system-ui,sans-serif;max-width:850px;margin:24px auto;color:#222;font-size:14px}}
 h1{{font-size:22px;margin-bottom:2px}} .sub{{color:#666;margin-bottom:14px}}
 img{{width:100%;max-height:480px;object-fit:cover;border-radius:8px}}
 table{{border-collapse:collapse;width:100%;margin:14px 0}}
 td{{padding:5px 10px;border-bottom:1px solid #eee;vertical-align:top}}
 td:first-child{{color:#666;width:220px}}
 .box{{background:#f0f7f0;border-left:4px solid #1a9850;padding:10px 14px;margin:14px 0;border-radius:4px}}
 .warn{{background:#fff7e6;border-left-color:#e6a700}}
 .score{{font-size:30px;font-weight:700;color:{scorecolor}}}
 @media print{{body{{margin:0}}}}
</style></head><body>
<div style="float:right;text-align:center"><div class="score">{score}</div><div style="color:#666;font-size:12px">Lead-Score</div>
<div style="font-size:13px;margin-top:6px"><b style="color:#8e6c3a">TH {score_th}</b> · <b style="color:#2c7fb8">HB {score_hb}</b></div>
<div style="color:#666;font-size:11px">Tiny House · Hausboot</div></div>
<h1>{name}</h1>
<div class="sub">{category} · {watername} · {website}</div>
{img}
<table>
<tr><td>Gewässer / Abstand</td><td>{watername} — {waterdist}</td></tr>
<tr><td>Gewässer-Typ / Hausboot-Eignung</td><td>{waterclass}</td></tr>
<tr><td>Vorhanden: Hausboot / Tinyhaus</td><td>{houseboat_ex} / {tiny_ex}</td></tr>
<tr><td>Eigene Uferlänge (geschätzt)</td><td>{shoreline}</td></tr>
<tr><td>Steg / Marina</td><td>{pier}</td></tr>
<tr><td>Fläche genutzt (OSM) / Grundstück gesamt (Kataster)</td><td>{area}</td></tr>
<tr><td>Flurstücke (amtliche Grundstücke)</td><td>{parcels}</td></tr>
<tr><td>Dauercamper</td><td>{seasonal}</td></tr>
<tr><td>Mietunterkünfte (Website-Angabe)</td><td>{rentals}</td></tr>
<tr><td>Gebäude (amtl. Kataster/ALKIS)</td><td>{gebaeude}</td></tr>
<tr><td>Preise</td><td>{prices}</td></tr>
<tr><td>Schutzgebiet</td><td>{protected}</td></tr>
<tr><td>Website-Modernität (0-10)</td><td>{webmodern}</td></tr>
<tr><td>Kontakt</td><td>{contact}</td></tr>
</table>
<div class="box"><b>Bebaubarkeit (Vorabeinschätzung):</b> {buildflag}</div>
{bplan}
{bildsichtung}
{history}
<div class="box"><b>Verkaufsargument:</b> {argument}</div>
<details style="margin:10px 0"><summary style="cursor:pointer"><b>Tiny-House-Score: {score_th}/100</b></summary>
<table>{scorerows_th}</table>
<div style="font-size:11px;color:#666">Je Zeile: erreichte / erreichbare Punkte. Bebaubarkeit: 15 = B-Plan Ferienhaus-/Campinggebiet (grün), 12 = feste Unterkünfte vorhanden (gelb-grün), 8 = unklar/Bauamt fragen (gelb), 0 = keine Basis.</div></details>
<details style="margin:10px 0"><summary style="cursor:pointer"><b>Hausboot-Score: {score_hb}/100</b></summary>
<table>{scorerows_hb}</table>
<div style="font-size:11px;color:#666">Je Zeile: erreichte / erreichbare Punkte. Ohne Hausboot-Gewässer ist der Score auf 40 gedeckelt.</div></details>
<details style="margin:10px 0"><summary style="cursor:pointer"><b>Lead-Score (Rangliste kombiniert): {score}/100</b></summary>
<table>{scorerows}</table>
<div style="font-size:11px;color:#666">Je Zeile: erreichte / erreichbare Punkte. Kombinierte Heuristik für die Rangliste, kein amtlicher Wert.</div></details>
<div class="box"><b>Umsatz-Rechenbeispiel:</b><br>{revenue}</div>
{market}
{notes}
<p style="color:#999;font-size:11px">Datenquellen: OpenStreetMap, {geoquelle} (ALKIS, DOP20 {year}),
Website des Platzes. Automatisch erstellt – Angaben vor Vertragsabschluss prüfen.
Stand: {date}</p>
</body></html>
"""


def fmt(v, suffix=""):
    if v is None or v == "":
        return "–"
    if isinstance(v, float):
        return ("%.0f" % v) + suffix
    return str(v) + suffix


def run(region_name, top=20):
    region = C.load_region(region_name)
    geoquelle = region.get("geoquelle", "Geoportal")
    bplan_portal = {"mse": "LK MSE", "bb_plis": "GL Berlin-Brandenburg",
                    "sn_rapis": "RAPIS Sachsen"}.get(region.get("bplan_source"), geoquelle)
    hist_years = sorted(region.get("hist_dop", {}))
    hist_src = ("%s (%s)" % (geoquelle, "/".join(hist_years))) if hist_years else geoquelle
    conn = C.db()
    rows = conn.execute("""SELECT s.*, e.* FROM sites s JOIN enrichment e ON s.id=e.site_id
        WHERE s.region=? AND (e.default_hidden IS NULL OR e.default_hidden != 1)
        ORDER BY e.lead_score DESC LIMIT ?""",
        (region_name, top)).fetchall()
    meta_path = C.DATA / ("luftbild_meta_%s.json" % region_name)
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    outdir = C.OUTPUT / "dossiers" / region_name
    outdir.mkdir(parents=True, exist_ok=True)
    import datetime
    date = datetime.date.today().isoformat()
    # History-Infos + Marktpreise
    hist = {}
    try:
        hist = {r["site_id"]: json.loads(r["info"]) for r in
                conn.execute("SELECT site_id, info FROM history_info")}
    except Exception:
        pass
    mp_path = C.DATA / ("marktpreise_%s.json" % region_name)
    market = ""
    if mp_path.exists():
        mp = json.loads(mp_path.read_text(encoding="utf-8"))
        b = mp.get("benchmarks", {})
        lines = []
        if b.get("booking_hausboot_median"):
            lines.append("Hausboote auf Booking.com (Region, Hauptsaison, echter Abruf): Median <b>%.0f €/Nacht</b> (Spanne %.0f–%.0f €, n=%d)"
                         % (b["booking_hausboot_median"], b["booking_hausboot_spanne"][0], b["booking_hausboot_spanne"][1], b["n_booking_boote"]))
        if b.get("airbnb_tiny_median"):
            lines.append("Tiny Houses auf Airbnb (Region, Hauptsaison, echter Abruf): Median <b>%.0f €/Nacht</b> (Spanne %.0f–%.0f €, n=%d)"
                         % (b["airbnb_tiny_median"], b["airbnb_tiny_spanne"][0], b["airbnb_tiny_spanne"][1], b["n_airbnb_tiny"]))
        if b.get("airbnb_hausboot_median"):
            lines.append("Hausboote auf Airbnb: Median <b>%.0f €/Nacht</b> (n=%d)"
                         % (b["airbnb_hausboot_median"], b["n_airbnb_boote"]))
        if b.get("website_median"):
            lines.append("Unterkünfte auf Platz-Websites der Region: Median <b>%.0f €/Nacht</b> (Spanne %.0f–%.0f €, n=%d)"
                         % (b["website_median"], b["website_spanne"][0], b["website_spanne"][1], b["n_website"]))
        if b.get("portal_luxus_median"):
            lines.append("Glamping-Portale (Luxus-Segment): Median <b>%.0f €/Nacht</b> (Spanne %.0f–%.0f €, n=%d)"
                         % (b["portal_luxus_median"], b["portal_luxus_spanne"][0], b["portal_luxus_spanne"][1], b["n_portal"]))
        lines.append("<i>Booking/Airbnb: Momentaufnahme Hauptsaison Juli, 3 Nächte/2 Erw.; "
                     "Details je Platz über den Booking-Link in der Excel.</i>")
        market = '<div class="box"><b>Markt-Benchmark Region:</b><br>' + "<br>".join(lines) + "</div>"
    for i, r in enumerate(rows, 1):
        m = meta.get(r["id"], {})
        img = ""
        if m.get("file") and (C.OUTPUT / "luftbilder" / m["file"]).exists():
            img = '<img src="../luftbilder/%s">' % m["file"]
        try:
            plist = json.loads(r["parcels"] or "[]")
            parcels = "; ".join("%s (%s m²)" % (p.get("kennzeichen", "?"),
                                                fmt(p.get("flaeche_m2"))) for p in plist[:6]) or "–"
        except Exception:
            parcels = "–"
        score = r["lead_score"] or 0
        # ALKIS-Gebaeude (BB/SN)
        gebaeude = "– (in diesem Bundesland nicht frei verfügbar)"
        try:
            gb = json.loads(r["buildings"] or "null") if "buildings" in r.keys() else None
        except Exception:
            gb = None
        if gb:
            typen = "; ".join("%s×%d" % (escape(k), v) for k, v in list(gb["typen"].items())[:6])
            gebaeude = "%d Gebäude, %s m² überbaute Fläche – %s" % (
                gb["n"], fmt(gb["flaeche_m2"]), typen)
        # KI-Bildsichtung
        bildsichtung = ""
        try:
            bs = json.loads(r["bildsichtung"] or "null") if "bildsichtung" in r.keys() else None
        except Exception:
            bs = None
        if bs:
            bildsichtung = ('<div class="box"><b>Luftbild-Sichtung (KI):</b> %s<br>'
                            '<b>Zustand:</b> %s<br>%s</div>'
                            % (escape(bs.get("bestand", "–")), escape(bs.get("zustand", "–")),
                               escape(bs.get("notiz", ""))))
        sc = "#d73027" if score >= 70 else "#fc8d59" if score >= 50 else "#888"
        prices = []
        if r["price_pitch"]:
            prices.append("Stellplatz ~%.0f €" % r["price_pitch"])
        if r["price_tent"]:
            prices.append("Zelt ~%.0f €" % r["price_tent"])
        if r["price_rental"]:
            prices.append("Unterkunft ~%.0f €" % r["price_rental"])
        contact = []
        if r["contact_name"]:
            contact.append(escape(r["contact_name"]))
        if r["chain"]:
            contact.append(escape(r["chain"]))
        if r["contact_email"] or r["email"]:
            contact.append(escape(r["contact_email"] or r["email"]))
        if r["phone"]:
            contact.append(escape(r["phone"]))
        notes = ""
        if r["protected_area"]:
            notes = '<div class="box warn"><b>Hinweis Schutzgebiet:</b> %s – Auflagen prüfen!</div>' % escape(r["protected_area"])
        # B-Plan-Block
        bplan = ""
        try:
            bp = json.loads(r["bplan_info"] or "null")
        except Exception:
            bp = None
        if bp and bp.get("plans"):
            lis = []
            for p in bp["plans"][:4]:
                pdfs = " ".join('<a href="%s">%s</a>' % (escape(d["url"]), escape(d["typ"]))
                                for d in p.get("dokumente", []) if "rechtsplan" in d["typ"].lower()
                                or "begr" in d["typ"].lower())
                art = (" – " + escape(p["planart"])) if p.get("planart") else ""
                lis.append("<li>%s <i>(%s%s)</i>%s %s</li>" % (
                    escape(p["name"]), escape(p.get("rechtsstand") or "?"),
                    ", " + p["inkrafttreten"] if p.get("inkrafttreten") else "", art, pdfs))
            a = bp.get("analysis", {})
            facts = []
            if a.get("max_grundflaeche_qm"):
                facts.append("max. Grundfläche: %s qm" % "/".join(str(int(q)) for q in a["max_grundflaeche_qm"]))
            if a.get("firsthoehe_m"):
                facts.append("Firsthöhe max. %.2f m" % a["firsthoehe_m"])
            if a.get("dachneigung_grad"):
                facts.append("Dachneigung %s°" % "–".join(str(x) for x in a["dachneigung_grad"][:2]))
            if a.get("grz"):
                facts.append("GRZ %.2f" % a["grz"])
            bplan = ('<div class="box"><b>Bebauungspläne (amtlich, %s):</b><ul>%s</ul>%s</div>'
                     % (escape(bplan_portal), "".join(lis),
                        ("<b>Festsetzungen (OCR-Auswertung):</b> " + "; ".join(facts)) if facts else ""))
        # Historie-Block: volle Zeitreihe 1953..2024 (Esri-Wayback), Duplikate raus
        history = ""
        h = hist.get(r["id"], {})
        if h:
            imgs = []
            caps = h.get("esri_aufnahmedaten", {})
            seen_cap = set()
            for y in sorted(h.get("hist_luftbilder", {}), key=lambda s: int(s)):
                rel = h["hist_luftbilder"][y]
                if not rel or not (C.OUTPUT / rel).exists():
                    continue
                cap = caps.get(y)
                year = cap[:4] if cap else y
                dedup = cap or y
                if dedup in seen_cap or year in seen_cap:
                    continue
                seen_cap.add(dedup)
                seen_cap.add(year)
                label = "Befliegung %s" % year
                imgs.append('<figure style="margin:0;flex:1;min-width:30%%"><img src="../%s" style="max-height:240px">'
                            '<figcaption style="font-size:11px;color:#666">%s</figcaption></figure>' % (rel, label))
            wb = h.get("wayback", {})
            wbtxt = ""
            if wb.get("erstes_archiv"):
                wbtxt = "Website im Internet-Archiv seit %s." % wb["erstes_archiv"]
            if r["rental_age_est"]:
                wbtxt += " <b>%s</b>" % escape(r["rental_age_est"])
            if imgs or wbtxt:
                history = ('<div class="box"><b>Bestandshistorie (Luftbild-Zeitreihe):</b> %s'
                           '<div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap">%s</div>'
                           '<div style="font-size:11px;color:#666;margin-top:4px">Quellen: %s, '
                           'Esri World Imagery Wayback (2014–2024, Datum = tatsächliche Aufnahme)</div></div>'
                           % (wbtxt, "".join(imgs), escape(hist_src)))
        def srows(key):
            try:
                sd = json.loads(r[key] or "null") or []
            except Exception:
                sd = []
            def one(row):
                k, v = row[0], row[1]
                mx = row[2] if len(row) > 2 else None
                if v is None:
                    vs = "Multiplikator/Deckel"
                elif v < 0:
                    vs = str(v)
                elif mx is not None:
                    vs = "%s / %s" % (v, mx)
                else:
                    vs = "+%s" % v
                return "<tr><td>%s</td><td>%s</td></tr>" % (escape(k), vs)
            return "".join(one(row) for row in sd)
        scorerows = srows("score_details")
        scorerows_th = srows("score_th_details")
        scorerows_hb = srows("score_hb_details")
        html = TMPL.format(
            name=escape(r["name"] or ""), category=escape(r["category"] or ""),
            watername=escape(r["water_name"] or "–"),
            website=('<a href="%s">%s</a>' % (escape(r["website"]), escape(r["website"]))) if r["website"] else "keine Website",
            img=img, score=fmt(score), scorecolor=sc,
            waterdist=fmt(r["water_distance_m"], " m"),
            shoreline=fmt(r["shoreline_m"], " m"),
            pier=("Steg vorhanden" if r["has_pier"] else "kein Steg erfasst") +
                 ("; Marina %s m" % fmt(r["marina_distance_m"]) if r["marina_distance_m"] else ""),
            waterclass=escape((r["waterbody_class"] or "?") +
                (" (%.1f ha)" % float(r["water_area_ha"]) if r["water_area_ha"] else "") +
                " – Hausboot: " + (r["houseboat_water"] or "?")),
            houseboat_ex="ja" if r["has_houseboat"] else "nein",
            tiny_ex="ja" if r["has_tinyhouse"] else "nein",
            area="%s / %s m²" % (fmt(r["area_m2"]), fmt(r["parcel_area_m2"])),
            parcels=escape(parcels),
            seasonal="ja" if r["seasonal"] else "nein/unbekannt",
            rentals=escape(r["rentals"] or "keine erfasst"),
            gebaeude=gebaeude,
            prices="; ".join(prices) or "–",
            protected=escape(r["protected_area"] or "keines erfasst"),
            contact="<br>".join(contact) or "–",
            buildflag=escape(r["build_flag"] or "–"),
            argument=escape(r["top_argument"] or "–"),
            revenue=escape(r["revenue_example"] or "–"),
            notes=notes, year=m.get("year") or "", date=date,
            geoquelle=escape(geoquelle),
            bplan=bplan, bildsichtung=bildsichtung, history=history, market=market,
            webmodern=("%s / 10 (%s)" % (r["web_modern"], escape(r["web_modern_info"] or "")))
                if r["web_modern"] is not None else "nicht bewertet",
            scorerows=scorerows, scorerows_th=scorerows_th, scorerows_hb=scorerows_hb,
            score_th=fmt(float(r["score_th"])) if r["score_th"] is not None else "–",
            score_hb=fmt(float(r["score_hb"])) if r["score_hb"] is not None else "–")
        fname = "%02d_%s.html" % (i, r["id"].replace("/", "_"))
        (outdir / fname).write_text(html, encoding="utf-8")
    print("Dossiers:", outdir, "(%d Stueck)" % len(rows))
    conn.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    top = 20
    for a in sys.argv:
        if a.startswith("--top"):
            top = int(a.split("=")[1])
    run(args[0] if args else "seenplatte", top)
