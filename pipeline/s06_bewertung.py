"""Schritt 06: Lead-Score, Baurecht-Ampel, Umsatz-Rechenbeispiel.

Score-Komponenten:
- Wasserlage (water_score aus s02)                       max 35
- Freie/verfuegbare Flaeche (Parzellen vs. OSM-Flaeche)  max 15
- Bestand-Erneuerungsbedarf (alte Unterkünfte, Dauer)    max 20
- Markt/Preisniveau (regionale Mietpreise)               max 15
- Erreichbarkeit (Website, E-Mail, Telefon)              max 10
- Groesse (Flaeche/Stellplaetze)                         max 5

Aufruf:  python -m pipeline.s06_bewertung seenplatte
"""
import json
import sys
from datetime import datetime, timezone

from . import common as C

# regionale Benchmarks (konservativ; spaeter aus echten Portalpreisen kalibrieren)
BENCH = {
    "seenplatte": {
        "tiny_price": 110.0,      # EUR/Nacht Tinyhaus am See (Spanne 80-160)
        "occupancy_nights": 140,  # vermietbare Naechte/Jahr
        "pitch_price": 30.0,      # EUR/Nacht Standard-Stellplatz
        "pitch_nights": 110,
        "n_units": 5,
    },
    "default": {
        "tiny_price": 120.0, "occupancy_nights": 140,
        "pitch_price": 32.0, "pitch_nights": 110, "n_units": 5,
    },
}


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

    for site in sites:
        score = 0.0
        args = []
        ws = site["water_score"] or 0
        score += ws * 0.35
        if ws >= 70:
            args.append("Top-Wasserlage (%s)" % (site["water_name"] or "See"))
        elif ws >= 50:
            args.append("direkt am Wasser (%s)" % (site["water_name"] or "?"))

        # Fläche: OSM-Fläche +Parcelldifferenz
        area = site["area_m2"] or 0
        parcel_area = site["parcel_area_m2"] or 0
        eff_area = max(area, parcel_area)
        if eff_area >= 100000:
            score += 15
        elif eff_area >= 50000:
            score += 11
        elif eff_area >= 20000:
            score += 7
        elif eff_area > 0:
            score += 3
        if parcel_area and area and parcel_area > area * 1.5:
            score += 4
            args.append("Grundstück deutlich größer als genutzte Fläche")

        # Bestand / Erneuerungsbedarf
        rentals = site["rentals"] or ""
        if site["seasonal"]:
            score += 6
            args.append("Dauercamper vorhanden")
        if any(t in rentals for t in ("Bungalow", "Mobilheim", "Hütte", "Ferienhaus")):
            score += 8
            args.append("feste Mietunterkünfte vorhanden (%s)" % rentals)
        if "Mobilheim" in rentals or "Bungalow" in rentals:
            score += 4  # Erneuerungszyklus wahrscheinlich
        if site["has_tinyhouse"]:
            score -= 5  # Wettbewerb, aber Markt validiert
            args.append("Tinyhäuser bereits vorhanden (Wettbewerb!)")
        if site["has_houseboat"]:
            args.append("Hausboote bereits vorhanden (Wettbewerb!)")
        if not rentals and ws >= 60:
            score += 10
            args.append("Top-Lage OHNE Mietunterkünfte – Lücke im Angebot")

        # Markt
        if site["price_rental"] and site["price_rental"] >= 90:
            score += 10
            args.append("hohes Preisniveau (%.0f EUR Unterkünfte)" % site["price_rental"])
        elif site["price_rental"]:
            score += 5
        elif site["price_pitch"] and site["price_pitch"] >= 30:
            score += 5

        # Erreichbarkeit
        contact = 0
        if site["website"]:
            contact += 4
        if site["contact_email"] or site["email"]:
            contact += 4
        if site["phone"]:
            contact += 2
        score += contact

        # Größe
        if eff_area >= 60000:
            score += 5
        elif eff_area >= 25000:
            score += 3

        # Penalty: Biwak/Wasserwander-Rastplätze (keine echten Campingplätze)
        name_low = (site["name"] or "").lower()
        if any(w in name_low for w in ("biwak", "wasserwander", "kanustation", "rastplatz")):
            score *= 0.35
            args.append("nur Biwak-/Rastplatz")

        # Bonus: eigener Steg/Marina direkt am Platz (Hausboot-Potenzial)
        if site["has_pier"] or (site["marina_distance_m"] is not None
                                and site["marina_distance_m"] < 100):
            score += 6
            args.append("Steg/Marina am Platz – Hausboot-Standort")

        # Penalty: Schutzgebiet mit strenger Klasse
        prot = site["protected_area"] or ""
        if "Klasse 2" in prot or "Nationalpark" in prot:
            score *= 0.6
            args.append("Schutzgebiet: %s" % prot[:60])

        score = round(min(score, 100), 1)

        # Rechenbeispiel
        n = bench["n_units"]
        rev_tiny = n * bench["tiny_price"] * bench["occupancy_nights"]
        rev_pitch = n * bench["pitch_price"] * bench["pitch_nights"]
        example = (
            "%d Tinyhäuser × %.0f €/Nacht × %d Nächte = %.0f €/Jahr "
            "(vs. %d Stellplätze: %.0f €/Jahr; Differenz +%.0f €)"
            % (n, bench["tiny_price"], bench["occupancy_nights"], rev_tiny,
               n, rev_pitch, rev_tiny - rev_pitch))
        # Hausboot-Rechenbeispiel, wenn Steg/Marina am Platz
        if hausboot_price and (site["has_pier"] or (site["marina_distance_m"] is not None
                                                   and site["marina_distance_m"] < 100)):
            rev_boat = 2 * hausboot_price * bench["occupancy_nights"]
            example += (" | Hausboot-Option: 2 Hausboote × %.0f €/Nacht × %d Nächte = %.0f €/Jahr "
                        "(Booking-Marktmedian Region)" % (hausboot_price, bench["occupancy_nights"], rev_boat))

        # B-Plan-Ampel (s11) hat Vorrang vor der Heuristik
        if site["bplan_info"]:
            flag = site["build_flag"] or build_flag(site, site)
        else:
            flag = build_flag(site, site)
        conn.execute("""UPDATE enrichment SET lead_score=?, top_argument=?,
            revenue_example=?, build_flag=?, updated=? WHERE site_id=?""",
            (score, "; ".join(args[:4]), example, flag,
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
