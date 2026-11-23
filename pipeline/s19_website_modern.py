"""Schritt 19: Website-Modernitaet als Proxy fuer Investitionsbereitschaft.

Reine Erreichbarkeit (Website/E-Mail vorhanden) gibt KEINE Punkte mehr –
das ist bereits Filterkriterium. Stattdessen bewerten wir, wie MODERN und
gepflegt der eigene Online-Auftritt ist: wer seine Website pflegt, pflegt
oft auch den Platz (Proxy fuer Investition/Auslastung, keine Garantie!).

Heuristik 0-10 aus dem HTML der Startseite (s05-Cache, sonst Live-Fetch):
  +2  mobil-tauglich (viewport-Meta oder responsives Framework)
  +2  HTTPS
  +2  Online-Buchung/Reservierung (Booking-Engine, Formular, 'online buchen')
  +2  aktuelles Jahr im Text/Copyright (2025/2026)
  +1  Social-Media-Links (Instagram/Facebook/YouTube)
  +1  modernes Framework/Builder (Bootstrap/Tailwind/Elementor/Wix/Squarespace,
      Webflow, Jimdo, Chayns, React/Vue/Next)
  -2  Uralt-Technik (Frameset, Tabellen-Layout, Font-Tag, <center>)
  -2  Steinzeit-Copyright (letztes Jahr <= 2019)
  -1  sehr duenner Inhalt (< 400 Zeichen Text)

Nur eigene Betreiber-Websites (online_status='website'); Verzeichnis-/
Stadtseiten werden nicht bewertet. Ergebnis: enrichment.web_modern (0-10)
+ web_modern_info (Merkmale).

Aufruf: python -m pipeline.s19_website_modern alle
"""
import json
import re
import sys
from datetime import datetime, timezone

from . import common as C
from .s05_website import page_text_robust

REGIONS = ["seenplatte", "brandenburg", "sachsen", "sachsen_anhalt", "thueringen"]
THIS_YEAR = datetime.now().year

BOOKING_PAT = re.compile(
    r"online[- ]?(?:buchen|buchung|reservier)|jetzt buchen|buchungsanfrage|"
    r"reservierungsanfrage|verf[üu]gbarkeit pr[üu]fen|book(?:ing)?[- ]?(?:now|online)|"
    r"regiondo|feratel|tomahawk|camping\.tools|bookings\.?site|easycamp|"
    r"pincamp|campmanager|guestoo|hotel-spider|dirks|bookingkit", re.I)
MODERN_PAT = re.compile(
    r"bootstrap|tailwind|elementor|wix\.com|wixstatic|squarespace|webflow|"
    r"jimdo|chayns|wp-content/themes|react|vue\.js|next/static|gatsby|"
    r"wp-block-|divi", re.I)
SOCIAL_PAT = re.compile(
    r"instagram\.com|facebook\.com|youtube\.com|youtu\.be|tiktok\.com", re.I)
OLDTECH_PAT = re.compile(
    r"<frameset|<frame\s|<font\s|<center>|<marquee|bgcolor=", re.I)
YEAR_PAT = re.compile(r"(?:©|&copy;|copyright|\b20\d{2}\b)", re.I)


def assess(html):
    """(score 0-10, merkmale-liste) aus Roh-HTML."""
    low = html.lower()
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    score, why = 0, []
    if re.search(r'<meta[^>]+name=["\']?viewport', low) or re.search(
            r"@media[^{]*\([^)]*(?:max|min)-width", low):
        score += 2; why.append("mobil-tauglich +2")
    if "https://" in low[:2000] or 'href="https://' in low:
        score += 2; why.append("HTTPS +2")
    if BOOKING_PAT.search(html):
        score += 2; why.append("Online-Buchung +2")
    years = [int(y) for y in re.findall(r"\b(20[0-2]\d)\b", text)]
    # Zukunftsjahre (Buchungskalender 'Sommer 2028') zaehlen nicht als Aktualitaet
    recent = [y for y in years if THIS_YEAR - 1 <= y <= THIS_YEAR]
    if recent:
        score += 2; why.append("aktuelles Jahr (%d) +2" % max(recent))
    if SOCIAL_PAT.search(html):
        score += 1; why.append("Social Media +1")
    if MODERN_PAT.search(html):
        score += 1; why.append("modernes Framework +1")
    if OLDTECH_PAT.search(html):
        score -= 2; why.append("Uralt-Technik (Frames/Font-Tag) -2")
    # Steinzeit-Copyright: juengstes vergangenes Jahr uralt UND kein aktuelles
    past = [y for y in years if y <= THIS_YEAR]
    if past and not recent and max(past) <= THIS_YEAR - 7:
        score -= 2; why.append("Copyright uralt (%d) -2" % max(past))
    if len(text) < 400:
        score -= 1; why.append("sehr duenner Inhalt -1")
    return max(0, min(score, 10)), why


def run(region_name):
    conn = C.init_db()
    regs = REGIONS if region_name == "alle" else [region_name]
    for reg in regs:
        rows = conn.execute("""SELECT s.id, s.name, s.website FROM sites s
            JOIN enrichment e ON s.id=e.site_id
            WHERE s.region=? AND e.online_status='website'
            AND s.website IS NOT NULL AND s.website != ''""", (reg,)).fetchall()
        n_ok = n_err = 0
        for r in rows:
            try:
                notes = []
                soup, text, final_url, quelle = page_text_robust(
                    r["website"], "s19", notes=notes)
                # Roh-HTML erneut aus Cache holen (page_text_robust liefert Text);
                # soup enthaelt keine script/style mehr -> Technik-Check am soup-String
                html = str(soup)
                # viewport-Meta geht beim soup-Parsen nicht verloren, aber
                # inline-CSS (@media) schon -> aus Original-Cache nachladen wenn moeglich
                import hashlib
                key = hashlib.sha1((final_url + "{}").encode()).hexdigest()
                cp = C.CACHE / (key + ".txt")
                if cp.exists():
                    html = cp.read_text(encoding="utf-8", errors="replace")
                score, why = assess(html)
                if quelle == "wayback":
                    why.append("nur Wayback-Snapshot bewertbar")
                    score = max(0, score - 1)
                info = "; ".join(why)
                conn.execute("""UPDATE enrichment SET web_modern=?, web_modern_info=?
                    WHERE site_id=?""", (int(score), info, r["id"]))
                n_ok += 1
            except Exception as ex:
                conn.execute("""UPDATE enrichment SET web_modern=NULL,
                    web_modern_info=? WHERE site_id=?""",
                    ("nicht bewertbar: " + str(ex)[:80], r["id"]))
                n_err += 1
            if (n_ok + n_err) % 50 == 0:
                conn.commit()
                print("%s: %d/%d" % (reg, n_ok + n_err, len(rows)), flush=True)
        conn.commit()
        dist = {}
        for r in conn.execute("""SELECT e.web_modern FROM enrichment e
            JOIN sites s ON s.id=e.site_id WHERE s.region=?""", (reg,)):
            k = str(r[0])
            dist[k] = dist.get(k, 0) + 1
        print("%s: bewertet=%d fehler=%d | Verteilung: %s" % (reg, n_ok, n_err, dist))
    conn.close()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "alle")