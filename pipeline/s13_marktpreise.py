"""Schritt 13: Marktpreise von Buchungsportalen (Benchmark für Angebote).

Quellen:
  1. Booking.com + Airbnb – im ECHTEN BROWSER gescrapt (Session-Cookies,
     Cookie-Banner akzeptiert, Hauptsaison-Daten). Rohdaten liegen in
     data/portalpreise_<region>_raw.json (Agenten-Scrape, siehe DATENQUELLEN).
     Booking: Hausboote (ht_id=215) + Glamping je Ort; Airbnb: komplette
     Regionssuche (15 Seiten), lokal nach Typ gefiltert.
  2. GlampingHub – Luxus-Glamping/Unterkünfte: Nachtpreise (Obergrenze).
  3. Eigene Website-Scrapes (s05) – Median der Unterkünfte der Region.

Ergebnis: data/marktpreise_<region>.json + Benchmarks für s06/s08,
Excel-Blätter "Marktpreise"/"Booking Hausboote"/"Airbnb Angebote" (via s07).

Aufruf: python -m pipeline.s13_marktpreise seenplatte
"""
import json
import re
import sys
from datetime import datetime, timezone

from . import common as C

# Regionen-Seiten je Bundesland (GlampingHub-Pfadstruktur)
GH_REGIONS = {
    "Mecklenburg-Vorpommern": "mecklenburgvorpommern",
    "Brandenburg": "brandenburg",
    "Bayern": "bavaria",
    "Schleswig-Holstein": "schleswig-holstein",
    "Sachsen": "saxony",
    "Sachsen-Anhalt": "saxonyanhalt",
    "Thüringen": "thuringia",
}


def gh_listings(state):
    slug = GH_REGIONS.get(state)
    if not slug:
        return []
    url = "https://glampinghub.com/germany/%s/" % slug
    try:
        html = C.http_get(url, cache_key="gh_list_" + slug, max_age_h=24 * 30,
                          polite=1.0, timeout=60)
    except Exception:
        return []
    urls = []
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            j = json.loads(m.group(1))
        except Exception:
            continue
        if j.get("@type") == "ItemList":
            for it in j.get("itemListElement", []):
                u = it.get("url")
                if u:
                    urls.append((it.get("name", ""), u))
    return urls


def gh_detail(name, url):
    try:
        html = C.http_get(url, cache_key="gh_det_" + re.sub(r"[^\w]", "_", url)[-70:],
                          max_age_h=24 * 30, polite=1.0, timeout=60)
    except Exception:
        return None
    out = {"name": name, "url": url}
    m = re.search(r"price_per_night:\s*(\d+)", html)
    if m:
        out["preis_nacht"] = int(m.group(1))
    m = re.search(r'property_type:\s*"([^"]+)"', html)
    if m:
        out["typ"] = m.group(1)
    m = re.search(r'location:\s*"([^"]+)"', html)
    if m:
        out["ort"] = m.group(1)
    m = re.search(r'"latitude":\s*([\d.]+)', html)
    m2 = re.search(r'"longitude":\s*([\d.]+)', html)
    if m and m2:
        out["lat"], out["lon"] = float(m.group(1)), float(m2.group(1))
    return out if out.get("preis_nacht") else None


def booking_link(site_name, lat, lon):
    """Deep-Link für manuelle Preisprüfung (Hauptsaison, 2 Erw.)."""
    from urllib.parse import quote
    return ("https://www.booking.com/searchresults.de.html?ss=%s"
            "&checkin=2026-07-10&checkout=2026-07-13&group_adults=2&no_rooms=1"
            % quote(site_name))


def load_portal_raw(region_name):
    """Browser-Scrape-Rohdaten (Booking + Airbnb), falls vorhanden."""
    p = C.DATA / ("portalpreise_%s_raw.json" % region_name)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def run(region_name):
    region = C.load_region(region_name)
    conn = C.db()
    # 1) Portal-Preise (GlampingHub = Luxus-Segment) – nur Angebote IN der Region
    listings = gh_listings(region.get("state", ""))
    print("GlampingHub-Inserate (%s): %d" % (region.get("state"), len(listings)))
    from shapely.geometry import Point, box as sbox
    s, w, n, e = region["bbox"]
    region_box = sbox(w - 0.05, s - 0.05, e + 0.05, n + 0.05)
    offers = []
    for name, url in listings:
        d = gh_detail(name, url)
        if d:
            if d.get("lat") and not region_box.contains(Point(d["lon"], d["lat"])):
                continue  # Inserat liegt ausserhalb der Region (Bundesland-Seite!)
            offers.append(d)
            print("  %-60s %4d EUR/Nacht (%s)" % (
                d["name"][:60], d["preis_nacht"], d.get("typ", "?")))
    # 1b) Booking/Airbnb-Browser-Scrape
    raw = load_portal_raw(region_name)
    booking_boats, booking_glamp, airbnb_offers = [], [], []
    nights = 3
    if raw:
        nights = raw.get("naechte", 3)
        for b in raw.get("booking", {}).get("hausboote", []):
            if b.get("preis_gesamt"):
                b["preis_nacht"] = round(b["preis_gesamt"] / nights)
            booking_boats.append(b)
        for b in raw.get("booking", {}).get("glamping_camping", []):
            if b.get("preis_gesamt"):
                b["preis_nacht"] = round(b["preis_gesamt"] / nights)
            booking_glamp.append(b)
        for a in raw.get("airbnb", {}).get("angebote", []):
            if a.get("total"):
                a["preis_nacht"] = round(a["total"] / nights)
            airbnb_offers.append(a)
        print("Browser-Scrape: Booking-Hausboote=%d, Airbnb-Sonderunterkuenfte=%d"
              % (len(booking_boats), len(airbnb_offers)))
    # 2) eigene Website-Preise
    rows = conn.execute("""SELECT s.name, s.lat, s.lon, e.price_rental, e.rentals
        FROM sites s JOIN enrichment e ON s.id=e.site_id
        WHERE s.region=? AND e.price_rental IS NOT NULL""", (region_name,)).fetchall()
    own = [{"name": r["name"], "preis_nacht": r["price_rental"],
            "typ": r["rentals"], "quelle": "Website"} for r in rows
           if 40 <= r["price_rental"] <= 400]
    # 3) Benchmarks
    def median(v):
        v = sorted(v)
        return v[len(v) // 2] if v else None
    portal_prices = [o["preis_nacht"] for o in offers]
    own_prices = [o["preis_nacht"] for o in own]
    boat_prices = [b["preis_nacht"] for b in booking_boats
                   if b.get("preis_nacht") and "Charter" not in (b.get("hinweis") or "")]
    air_tiny = [a["preis_nacht"] for a in airbnb_offers
                if a.get("preis_nacht") and a["title"].startswith("Tiny House")]
    air_boats = [a["preis_nacht"] for a in airbnb_offers
                 if a.get("preis_nacht") and ("Hausboot" in a["title"] or a["title"].startswith("Boot"))]
    bench = {
        "portal_luxus_median": median(portal_prices),
        "portal_luxus_spanne": [min(portal_prices), max(portal_prices)] if portal_prices else None,
        "website_median": median(own_prices),
        "website_spanne": [min(own_prices), max(own_prices)] if own_prices else None,
        "n_portal": len(offers), "n_website": len(own),
        "booking_hausboot_median": median(boat_prices),
        "booking_hausboot_spanne": [min(boat_prices), max(boat_prices)] if boat_prices else None,
        "n_booking_boote": len(boat_prices),
        "airbnb_tiny_median": median(air_tiny),
        "airbnb_tiny_spanne": [min(air_tiny), max(air_tiny)] if air_tiny else None,
        "n_airbnb_tiny": len(air_tiny),
        "airbnb_hausboot_median": median(air_boats),
        "n_airbnb_boote": len(air_boats),
        "hinweis": ("Booking + Airbnb im echten Browser gescrapt (Hauptsaison %s, "
                    "%d Nächte, 2 Erw.). Preise sind Gesamtpreis/Nächte; Servicegebühren "
                    "Airbnb inklusive, Booking zzgl. teils Endreinigung. "
                    "Deep-Links je Platz in Excel für Detailprüfung."
                    % ((raw or {}).get("checkin", "?"), nights)),
    }
    # Vorschlag Tinyhaus-Preis: Airbnb-Tiny-Median (realer Markt!), sonst Website-Median
    if bench["airbnb_tiny_median"]:
        bench["tiny_vorschlag"] = round(max(90, min(bench["airbnb_tiny_median"], 200)))
    elif bench["website_median"]:
        bench["tiny_vorschlag"] = round(max(90, min(bench["website_median"], 200)))
    elif bench["portal_luxus_median"]:
        bench["tiny_vorschlag"] = round(max(90, min(bench["portal_luxus_median"] * 0.6, 200)))
    else:
        bench["tiny_vorschlag"] = 90
    # Vorschlag Hausboot-Preis: Booking-Hausboot-Median (ohne Charter)
    # Mindestens 3 Boote noetig, sonst Fallback Nachbarregion (Schiffspension != Hausboot)
    if bench["booking_hausboot_median"] and bench["n_booking_boote"] >= 3:
        bench["hausboot_vorschlag"] = round(bench["booking_hausboot_median"])
    else:
        fb = C.DATA / "marktpreise_brandenburg.json"
        if region_name != "brandenburg" and fb.exists():
            bb = json.loads(fb.read_text(encoding="utf-8"))
            v = bb.get("benchmarks", {}).get("hausboot_vorschlag")
            if v:
                bench["hausboot_vorschlag"] = v
                bench["hausboot_hinweis"] = ("Zu wenige Hausboot-Angebote in der Region "
                    "(n=%s); Fallback Brandenburg-Median. Hausboot-Markt hier kaum existent."
                    % bench["n_booking_boote"])
    # 4) Deep-Links je Platz
    sites = conn.execute("""SELECT s.name, s.lat, s.lon FROM sites s
        JOIN enrichment e ON s.id=e.site_id WHERE s.region=?
        ORDER BY e.lead_score DESC NULLS LAST""", (region_name,)).fetchall()
    links = [{"name": s["name"], "booking": booking_link(s["name"], s["lat"], s["lon"])}
             for s in sites[:40]]
    result = {"region": region_name, "stand": datetime.now(timezone.utc).isoformat(),
              "benchmarks": bench, "portal_angebote": offers,
              "website_preise": own, "booking_links": links,
              "booking_hausboote": booking_boats,
              "booking_glamping": booking_glamp,
              "airbnb_angebote": airbnb_offers,
              "scrape_info": {k: raw.get(k) for k in ("checkin", "checkout", "naechte", "methode")} if raw else None}
    path = C.DATA / ("marktpreise_%s.json" % region_name)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Benchmark:", json.dumps(bench, ensure_ascii=False, indent=1))
    print("Gespeichert:", path)
    conn.close()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "seenplatte")