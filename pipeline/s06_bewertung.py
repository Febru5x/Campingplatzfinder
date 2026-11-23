"""Schritt 06: Lead-Scores, Baurecht-Ampel, Umsatz-Rechenbeispiel.

Drei Scores je Platz:
- lead_score  kombinierter Lead-Score (Ranking/Top-Listen):
  Wasserlage max 35, Flaeche max 15+4, Bestand/Luecke max 20, Markt max 10,
  Website-Modernitaet max 10, Groesse max 5, Steg +6, Abzuege (Tiny -5,
  Biwak x0.35, strenges Schutzgebiet x0.6)
- score_th    Tiny-House-Score: Wasserlage nur Bonus (max 10), dafuer
  Bebaubarkeit 0-15; Rest wie Lead-Score ohne Steg-Bonus
- score_hb    Hausboot-Score: Wasserlage max 35 + Gewaesser-Eignung 15
  + Steg/Marina 12 + Uferlaenge max 8 + Markt/Modernitaet/Dauer;
  kein Hausboot-Gewaesser -> Deckel 40

Reine Erreichbarkeit gibt keine Punkte mehr (ist Filterkriterium);
stattdessen Website-Modernitaet (s19) als Investitions-Proxy.
Rechenbeispiel: 3 Einheiten, Preis aus Portal-Angeboten im Umkreis 25 km
(Airbnb/Booking, geokodiert via Nominatim) minus 20 % Camping-Abschlag.

Aufruf:  python -m pipeline.s06_bewertung seenplatte
"""
import json
import re
import sys
from datetime import datetime, timezone

from . import common as C

# regionale Benchmarks (Fallback; Preise werden je Platz aus Portal-Daten
# im Umkreis 25 km kalibriert, s.u.)
BENCH = {
    "seenplatte": {
        "tiny_price": 110.0,      # EUR/Nacht Tinyhaus am See (Spanne 80-160)
        "occupancy_nights": 140,  # vermietbare Naechte/Jahr (ganzjaehrig)
        "pitch_price": 30.0,      # EUR/Nacht Standard-Stellplatz
        "pitch_nights": 110,
        "n_units": 3,
    },
    "default": {
        "tiny_price": 120.0, "occupancy_nights": 140,
        "pitch_price": 32.0, "pitch_nights": 110, "n_units": 3,
    },
}

RADIUS_M = 25000       # Umkreis fuer lokale Markt-Benchmarks
CAMP_DISCOUNT = 0.8    # Camping-Ausstattung vs. Premium-Portal-Inserate


def _haversine(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, asin, sqrt
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * 6371000 * asin(sqrt(a))


def geocode_town(town):
    """Orts-Koordinate via Photon/Komoot (frei, OSM-basiert, gecacht).
    Fallback Nominatim. None bei Fehlschlag."""
    try:
        raw = C.http_get("https://photon.komoot.io/api/",
                         params={"q": town + ", Deutschland", "limit": 1},
                         cache_key="geoc_" + re.sub(r"[^\w]", "_", town.lower())[:60],
                         max_age_h=24 * 180, polite=0.5, retries=2, timeout=45)
        j = json.loads(raw)
        feats = j.get("features") or []
        if feats:
            lon, lat = feats[0]["geometry"]["coordinates"][:2]
            return float(lat), float(lon)
    except Exception:
        pass
    try:
        raw = C.http_get("https://nominatim.openstreetmap.org/search",
                         params={"q": town + ", Deutschland", "format": "json", "limit": 1},
                         cache_key="geocn_" + re.sub(r"[^\w]", "_", town.lower())[:60],
                         max_age_h=24 * 180, polite=1.2, retries=2, timeout=45)
        j = json.loads(raw)
        if j:
            return float(j[0]["lat"]), float(j[0]["lon"])
    except Exception:
        pass
    return None


def local_portal_offers(region_name):
    """Airbnb/Booking-Angebote mit Ort geokodiert (fuer 25-km-Benchmarks).
    Titel-Muster 'Tiny House in X' / '... am Y' -> Ortsname -> Nominatim.
    Ergebnis gecacht in data/portal_geo_<region>.json."""
    cache = C.DATA / ("portal_geo_%s.json" % region_name)
    if cache.exists():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            pass
    raw_p = C.DATA / ("portalpreise_%s_raw.json" % region_name)
    out = []
    if raw_p.exists():
        raw = json.loads(raw_p.read_text(encoding="utf-8"))
        nights = raw.get("naechte", 3) or 3
        offers = []
        for a in raw.get("airbnb", {}).get("angebote", []):
            if a.get("total"):
                offers.append({"quelle": "Airbnb", "title": a.get("title", ""),
                               "preis_nacht": a["total"] / nights,
                               "tiny": bool(re.match(r"tiny house", a.get("title", ""), re.I)),
                               "boot": bool(re.search(r"hausboot|^boot", a.get("title", ""), re.I))})
        for b in raw.get("booking", {}).get("hausboote", []):
            if b.get("preis_gesamt") and "Charter" not in (b.get("hinweis") or ""):
                offers.append({"quelle": "Booking", "title": b.get("name", ""),
                               "ort_fix": b.get("ort"), "preis_nacht": b["preis_gesamt"] / nights,
                               "tiny": False, "boot": True})
        for b in raw.get("booking", {}).get("glamping_camping", []):
            if b.get("preis_gesamt"):
                offers.append({"quelle": "Booking", "title": b.get("name", ""),
                               "ort_fix": b.get("ort"), "preis_nacht": b["preis_gesamt"] / nights,
                               "tiny": bool(re.search(r"tiny", (b.get("typ") or "") + " " + b.get("name", ""), re.I)),
                               "boot": False})
        towns = {}
        for o in offers:
            town = o.get("ort_fix")
            if not town:
                m = re.search(r"\b(?:in|am|an der|bei)\s+([A-ZÄÖÜ][\wäöüßÄÖÜ .\-/]+)$", o["title"])
                town = m.group(1).strip() if m else None
            o["ort"] = town
            if town:
                if town not in towns:
                    towns[town] = geocode_town(town)
                if towns[town]:
                    o["lat"], o["lon"] = towns[town]
            out.append(o)
    cache.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def local_price(offers, site, kind):
    """Median der passenden Portal-Angebote im Umkreis 25 km (mind. 2),
    sonst None. kind: 'tiny' oder 'boot'. Roh-Median (Abschlag macht Aufrufer)."""
    vals = []
    for o in offers:
        if not o.get(kind) or o.get("lat") is None or not o.get("preis_nacht"):
            continue
        if _haversine(site["lat"], site["lon"], o["lat"], o["lon"]) <= RADIUS_M:
            vals.append(o["preis_nacht"])
    if len(vals) >= 2:
        vals.sort()
        return vals[len(vals) // 2], len(vals)
    return None, len(vals)


def build_flag(site, enr):
    """Baurecht-Ampel für ortsfeste Tinyhäuser (Heuristik!)."""
    tags = json.loads(site["raw_tags"] or "{}")
    rentals = enr["rentals"] or ""
    # feste Mietunterkünfte vorhanden -> Gebäude am Platz offenbar genehmigt
    fixed = any(t in rentals for t in ("Bungalow", "Ferienhaus", "Tinyhaus", "Hütte"))
    mobile_home = "Mobilheim" in rentals
    if fixed:
        return "gelb-grün: feste Unterkünfte vorhanden – gute Basis, Details prüfen"
    if mobile_home:
        return "gelb: Mobilheime vorhanden – Sondergebiet wahrscheinlich, feste Bauten anfragen"
    if site["category"] == "caravan_site":
        return "rot/gelb: reiner Wohnmobil-Stellplatz – feste Bauten unwahrscheinlich"
    if tags.get("caravans") == "no" and tags.get("tents") == "yes":
        return "gelb: Zeltplatz – Widmung/B-Plan prüfen"
    return "gelb: unklar – B-Plan/Bauamt anfragen"


def run(region_name):
    bench = BENCH.get(region_name, BENCH["default"])
    conn = C.init_db()
    sites = conn.execute("""SELECT s.*, e.* FROM sites s
        JOIN enrichment e ON s.id=e.site_id WHERE s.region=?""",
        (region_name,)).fetchall()
    print("Plaetze:", len(sites))
    # regionale Mietpreis-Mediane aus gescrapten Daten
    # (nur echte Unterkunfts-Nachtpreise: 60-400 EUR; Wochenpreise filtern)
    rental_prices = [s["price_rental"] for s in sites
                     if s["price_rental"] and 60 <= s["price_rental"] <= 400]
    if rental_prices:
        rental_prices.sort()
        med = rental_prices[len(rental_prices) // 2]
        bench["tiny_price"] = round(max(90.0, min(med, 200.0)), 0)
    # Portal-Benchmarks (s13: Booking/Airbnb echter Browser-Scrape) haben Vorrang
    mp_path = C.DATA / ("marktpreise_%s.json" % region_name)
    mp_bench = {}
    if mp_path.exists():
        try:
            mp_bench = json.loads(mp_path.read_text(encoding="utf-8")).get("benchmarks", {})
        except Exception:
            pass
    if mp_bench.get("tiny_vorschlag"):
        bench["tiny_price"] = float(mp_bench["tiny_vorschlag"])
    hausboot_price = mp_bench.get("hausboot_vorschlag")
    # Stellplatzpreise: 15-80 EUR (Wasserwander-Biwak 5-10 EUR verfaelscht sonst)
    pitch_prices = [s["price_pitch"] for s in sites
                    if s["price_pitch"] and 15 <= s["price_pitch"] <= 80]
    if pitch_prices:
        pitch_prices.sort()
        bench["pitch_price"] = round(pitch_prices[len(pitch_prices) // 2], 1)
    print("Benchmark: Tinyhaus %.0f EUR/Nacht, Stellplatz %.1f EUR" %
          (bench["tiny_price"], bench["pitch_price"]))
    # Portal-Angebote mit Koordinaten fuer lokale 25-km-Benchmarks
    offers = local_portal_offers(region_name)
    print("Portal-Angebote geokodiert: %d/%d" % (
        sum(1 for o in offers if o.get("lat") is not None), len(offers)))

    for site in sites:
        args = []
        ws = site["water_score"] or 0
        if ws >= 70:
            args.append("Top-Wasserlage (%s)" % (site["water_name"] or "See"))
        elif ws >= 50:
            args.append("direkt am Wasser (%s)" % (site["water_name"] or "?"))

        # gemeinsame Basis-Komponenten (fuer beide Scores)
        area = site["area_m2"] or 0
        parcel_area = site["parcel_area_m2"] or 0
        eff_area = max(area, parcel_area)
        v_area = 15 if eff_area >= 100000 else 11 if eff_area >= 50000 \
            else 7 if eff_area >= 20000 else 3 if eff_area > 0 else 0
        v_reserve = 4 if (parcel_area and area and parcel_area > area * 1.5) else 0
        if v_reserve:
            args.append("Grundstück deutlich größer als genutzte Fläche")
        rentals = site["rentals"] or ""
        v_seasonal = 6 if site["seasonal"] else 0
        if v_seasonal:
            args.append("Dauercamper vorhanden")
        v_fixed = 8 if any(t in rentals for t in ("Bungalow", "Mobilheim", "Hütte", "Ferienhaus")) else 0
        if v_fixed:
            args.append("feste Mietunterkünfte vorhanden (%s)" % rentals)
        v_cycle = 4 if ("Mobilheim" in rentals or "Bungalow" in rentals) else 0
        v_gap = 10 if (not rentals and ws >= 60) else 0
        if v_gap:
            args.append("Top-Lage OHNE Mietunterkünfte – Lücke im Angebot")
        if site["price_rental"] and site["price_rental"] >= 90:
            v_market = 10
            args.append("hohes Preisniveau (%.0f EUR Unterkünfte)" % site["price_rental"])
        elif site["price_rental"]:
            v_market = 5
        elif site["price_pitch"] and site["price_pitch"] >= 30:
            v_market = 5
        else:
            v_market = 0
        # Website-Modernitaet (s19) statt reiner Erreichbarkeit: Proxy fuer
        # Investitionsbereitschaft. Kontakt ist bereits Filterkriterium.
        try:
            wm = int(site["web_modern"]) if site["web_modern"] is not None else None
        except (TypeError, ValueError):
            wm = None
        v_modern = wm if wm is not None else 0
        if wm is not None and wm >= 7:
            args.append("moderne, gepflegte Website (Proxy: investitionsfreudig)")
        v_size = 5 if eff_area >= 60000 else 3 if eff_area >= 25000 else 0
        pier = bool(site["has_pier"]) or (site["marina_distance_m"] is not None
                                          and site["marina_distance_m"] < 100)
        if pier:
            args.append("Steg/Marina am Platz – Hausboot-Standort")
        name_low = (site["name"] or "").lower()
        m_biwak = 0.35 if any(w in name_low for w in
                              ("biwak", "wasserwander", "kanustation", "rastplatz")) else 1.0
        if m_biwak < 1:
            args.append("nur Biwak-/Rastplatz")
        prot = site["protected_area"] or ""
        m_prot = 0.6 if ("Klasse 2" in prot or "Nationalpark" in prot) else 1.0
        if m_prot < 1:
            args.append("Schutzgebiet: %s" % prot[:60])

        def finalize(parts, mult):
            # Eintraege: [Label, Wert] oder [Label, Wert, Max]
            s = sum(p[1] for p in parts if isinstance(p[1], (int, float)))
            for p in parts:
                if p[1] is None:
                    s *= mult
            return round(min(max(s, 0), 100), 1)

        # --- Tiny-House-Score: Wasserlage nur kleiner Bonus (max 10) ---
        th = []
        v_water_th = round(ws * 0.10, 1)
        th.append(["Wasserlage (Bonus)", v_water_th, 10])
        bf = (site["build_flag"] or build_flag(site, site)).lower()
        v_bau = 15 if ("grün" in bf and "gelb-grün" not in bf and "grün-gelb" not in bf) \
            else 12 if ("gelb-grün" in bf or "grün-gelb" in bf) \
            else 8 if bf.startswith("gelb") else 0
        th.append(["Bebaubarkeit (B-Plan/Bauvorrecht)", v_bau, 15])
        th.append(["Fläche/Platzangebot", v_area, 15])
        th.append(["Reserve: Grundstück > genutzte Fläche", v_reserve, 4])
        th.append(["Dauercamper vorhanden", v_seasonal, 6])
        th.append(["Feste Mietunterkünfte (Erneuerungsbedarf)", v_fixed, 8])
        th.append(["Mobilheime/Bungalows (Erneuerungszyklus)", v_cycle, 4])
        if site["has_tinyhouse"]:
            th.append(["Tinyhäuser vorhanden (Wettbewerb)", -5])
            args_th = "Tinyhäuser bereits vorhanden (Wettbewerb!)"
            if args_th not in args:
                args.append(args_th)
        th.append(["Top-Lage OHNE Mietunterkünfte (Lücke)", v_gap, 10])
        th.append(["Preisniveau (Markt)", v_market, 10])
        th.append(["Website-Modernität", v_modern, 10])
        th.append(["Platzgröße", v_size, 5])
        if m_biwak < 1:
            th.append(["Abzug: nur Biwak-/Rastplatz (×0,35)", None])
        if m_prot < 1:
            th.append(["Abzug: strenges Schutzgebiet (×0,6)", None])
        score_th = finalize(th, m_biwak * m_prot)

        # --- Hausboot-Score: Wasserlage + Steg dominant, Gewaesser-Eignung ---
        hb = []
        hb.append(["Wasserlage (Abstand/Ufer)", round(ws * 0.35, 1), 35])
        hbw = site["houseboat_water"]
        v_hbw = 15 if hbw == "ja" else 5 if hbw == "unklar" else 0
        hb.append(["Gewässer für Hausboot geeignet", v_hbw, 15])
        hb.append(["Steg/Marina am Platz", 12 if pier else 0, 12])
        hb.append(["Uferlänge am Platz", min(round((site["shoreline_m"] or 0) / 50), 8), 8])
        hb.append(["Preisniveau (Markt)", v_market, 10])
        hb.append(["Website-Modernität", v_modern, 10])
        hb.append(["Dauercamper (Betrieb vorhanden)", v_seasonal, 6])
        if site["has_houseboat"]:
            hb.append(["Hausboote vorhanden (Wettbewerb)", -5])
            if "Hausboote bereits vorhanden (Wettbewerb!)" not in args:
                args.append("Hausboote bereits vorhanden (Wettbewerb!)")
        if m_biwak < 1:
            hb.append(["Abzug: nur Biwak-/Rastplatz (×0,35)", None])
        if m_prot < 1:
            hb.append(["Abzug: strenges Schutzgebiet (×0,6)", None])
        score_hb = finalize(hb, m_biwak * m_prot)
        # kein Hausboot-Gewaesser -> Hausboot-Score deckeln
        if hbw == "nein":
            score_hb = min(score_hb, 40.0)
            hb.append(["Deckel: kein Hausboot-Gewässer (max 40)", None])
        score_hb = round(score_hb, 1)

        # Lead-Score (Ranking gesamt) = kombinierte Heuristik (mit Max-Werten)
        comp = []
        score = round(ws * 0.35, 1)
        comp.append(["Wasserlage (Abstand/Ufer/Steg)", round(ws * 0.35, 1), 35])
        score += v_area
        comp.append(["Fläche/Platzangebot", v_area, 15])
        if v_reserve:
            score += v_reserve
            comp.append(["Reserve: Grundstück > genutzte Fläche", v_reserve, 4])
        if v_seasonal:
            score += v_seasonal
            comp.append(["Dauercamper vorhanden", v_seasonal, 6])
        if v_fixed:
            score += v_fixed
            comp.append(["Feste Mietunterkünfte (Erneuerungsbedarf)", v_fixed, 8])
        if v_cycle:
            score += v_cycle
            comp.append(["Mobilheime/Bungalows (Erneuerungszyklus)", v_cycle, 4])
        if site["has_tinyhouse"]:
            score -= 5
            comp.append(["Tinyhäuser vorhanden (Wettbewerb)", -5])
        if v_gap:
            score += v_gap
            comp.append(["Top-Lage OHNE Mietunterkünfte (Lücke)", v_gap, 10])
        if v_market:
            score += v_market
            comp.append(["Preisniveau (Markt)", v_market, 10])
        score += v_modern
        comp.append(["Website-Modernität", v_modern, 10])
        if v_size:
            score += v_size
            comp.append(["Platzgröße", v_size, 5])
        if pier:
            score += 6
            comp.append(["Steg/Marina am Platz (Hausboot-Potenzial)", 6, 6])
        if m_biwak < 1:
            score *= m_biwak
            comp.append(["Abzug: nur Biwak-/Rastplatz (×0,35)", None])
        if m_prot < 1:
            score *= m_prot
            comp.append(["Abzug: strenges Schutzgebiet (×0,6)", None])
        score = round(min(score, 100), 1)

        # Rechenbeispiel: 3 Einheiten (konservativ), Preis je Platz aus
        # Portal-Angeboten (Airbnb/Booking) im Umkreis 25 km; sonst Regions-
        # Median. Portal-Preise sind Premium-Inserate -> 20 % Abschlag fuer
        # Camping-Ausstattung. Naechte/Jahr = konservative Auslastungsannahme.
        n = bench["n_units"]
        lp, l_n = local_price(offers, site, "tiny")
        if lp:
            tiny_p = round(lp * CAMP_DISCOUNT)
            p_src = "Ø %d Airbnb/Booking-Angebote im Umkreis 25 km (%.0f €) minus 20 %% Camping-Abschlag" % (l_n, lp)
        else:
            tiny_p = round(bench["tiny_price"])
            p_src = "Regions-Median (%.0f €, zu wenige Portal-Angebote im Umkreis)" % tiny_p
        # Stellplatz: eigener Website-Preis des Platzes, sonst Regions-Median
        own_pitch = site["price_pitch"] if (site["price_pitch"] and
                                           15 <= site["price_pitch"] <= 80) else None
        pitch_p = own_pitch or bench["pitch_price"]
        pitch_src = "eigene Website" if own_pitch else "Regions-Median"
        nights = bench["occupancy_nights"]
        rev_tiny = n * tiny_p * nights
        rev_pitch = n * pitch_p * bench["pitch_nights"]
        example = (
            "3 Tinyhäuser × %d €/Nacht × %d Nächte/Jahr ≈ %s €/Jahr "
            "(statt 3 Stellplätzen à %.0f € × %d Nächte: %s €; +%.0f €). "
            "Preis: %s. Nächte = konservative Auslastungsannahme (ganzjährig)."
            % (tiny_p, nights, format(round(rev_tiny), ",").replace(",", "."),
               pitch_p, bench["pitch_nights"],
               format(round(rev_pitch), ",").replace(",", "."),
               rev_tiny - rev_pitch, p_src))
        # Hausboot-Rechenbeispiel, wenn Steg/Marina am Platz
        if pier and (hausboot_price or lp is not None):
            bp_l, bp_n = local_price(offers, site, "boot")
            if bp_l:
                boat_p = round(bp_l * CAMP_DISCOUNT)
                b_src = "%d Hausboot-Angebote im Umkreis 25 km" % bp_n
            elif hausboot_price:
                boat_p = hausboot_price
                b_src = "Booking-Marktmedian Region" + (
                    " (Fallback Brandenburg)" if region_name != "brandenburg"
                    and mp_bench.get("hausboot_hinweis") else "")
            else:
                boat_p, b_src = None, None
            if boat_p:
                rev_boat = 2 * boat_p * nights
                example += (" | Hausboot-Option: 2 Hausboote × %d €/Nacht × %d Nächte ≈ %s €/Jahr (%s)"
                            % (boat_p, nights,
                               format(round(rev_boat), ",").replace(",", "."), b_src))

        # B-Plan-Ampel (s11) hat Vorrang vor der Heuristik
        if site["bplan_info"]:
            flag = site["build_flag"] or build_flag(site, site)
        else:
            flag = build_flag(site, site)
        # B-Plan-Gebietsarten kuerzen (Popup/Excel lesbar statt Textwand)
        try:
            bpj = json.loads(site["bplan_info"])
            changed = False
            for p in bpj.get("plans", []):
                for key in ("planart", "nutzung"):
                    t = p.get(key)
                    if t and len(t) > 60:
                        seen = []
                        for part in re.split(r";\s*", t):
                            part = part.strip()
                            if part and part not in seen:
                                seen.append(part)
                        p[key] = "; ".join(seen)[:160]
                        changed = True
            if changed:
                site_bp = json.dumps(bpj, ensure_ascii=False)
            else:
                site_bp = site["bplan_info"]
        except Exception:
            site_bp = site["bplan_info"]
        conn.execute("""UPDATE enrichment SET lead_score=?, top_argument=?,
            revenue_example=?, build_flag=?, score_details=?, bplan_info=?,
            score_th=?, score_hb=?, score_th_details=?, score_hb_details=?,
            updated=? WHERE site_id=?""",
            (score, "; ".join(args[:4]), example, flag,
             json.dumps(comp, ensure_ascii=False), site_bp,
             score_th, score_hb,
             json.dumps(th, ensure_ascii=False), json.dumps(hb, ensure_ascii=False),
             datetime.now(timezone.utc).isoformat(), site["id"]))
    conn.commit()
    # Benchmarks fuer Dossiers/Export persistieren
    (C.DATA / ("benchmarks_%s.json" % region_name)).write_text(
        json.dumps(bench, ensure_ascii=False, indent=1), encoding="utf-8")
    top = conn.execute("""SELECT s.name, e.lead_score, e.top_argument FROM sites s
        JOIN enrichment e ON s.id=e.site_id WHERE s.region=?
        ORDER BY e.lead_score DESC LIMIT 15""", (region_name,)).fetchall()
    print("\nTop 15:")
    for t in top:
        print(" %5.1f  %s  | %s" % (t["lead_score"], t["name"], t["top_argument"]))
    conn.close()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "seenplatte")
