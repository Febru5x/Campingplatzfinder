"""Schritt 20: Namen fuer unbenannte Plaetze aus der Website ableiten.

OSM kennt manche Plaetze nur als Polygon ohne Namen. Wenn eine Website
hinterlegt ist, holen wir den Seitentitel (og:site_name / <title> / h1)
und bereinigen ihn (Suffixe wie '| Stadt X', 'Startseite', Trennzeichen).
Uebernommen wird nur ein plausibler Platz-Name; Herkunft in name_source.
Danach s17 neu laufen lassen (Namensregeln greifen dann, z.B.
'Wohnmobilstellplatz' im Titel -> Stellplatz statt camping).

Aufruf: python -m pipeline.s20_namen alle
"""
import json
import re
import sys

from . import common as C
from .s05_website import page_text_robust

REGIONS = ["seenplatte", "brandenburg", "sachsen", "sachsen_anhalt", "thueringen"]

# Titel-Zusatz, der nichts mit dem Platznamen zu tun hat
STRIP_PAT = re.compile(
    r"^\s*(?:startseite|home|willkommen|start|homepage)\s*[:\-–|]*\s*", re.I)
# fuehrende Fuellwoerter ('auf dem Campingplatz am ...' -> 'Campingplatz am ...')
LEAD_PAT = re.compile(
    r"^(?:auf\s+dem|auf\s+der|am|an\s+der|im|in\s+der|bei\s+uns|unser[e]?)\s+", re.I)
GENERIC = {"camping", "camping & caravan", "camping und caravan", "campingplatz",
           "stellplatz", "wohnmobilstellplatz", "zeltplatz", "camping-caravan",
           "unsere campingwiese", "alpacacamping"}
SUFFIX_PAT = re.compile(
    r"\s*[|\-–•]\s*(?:startseite|home|willkommen|stadt\s+\w+|gemeinde\s+\w+|"
    r"tourismus[\w -]*|urlaub[\w -]*|offizielle? (?:webseite|website|seite)[\w -]*|"
    r"camping & caravan|camping und caravan)\s*$", re.I)
# Name muss nach Platz klingen (sonst lieber unbenannt lassen)
PLAUSIBLE_PAT = re.compile(
    r"camping|camp\b|stellplatz|caravan|wohnmobil|zeltplatz|naturcamp|"
    r"seecamp|freizeitpark|ferienpark|jugendherberge|biwak|kanu|"
    r"\bsee\b|\bpark\b|hof\b|marina|resort|glamping", re.I)


def clean_title(t):
    if not t:
        return None
    t = re.sub(r"\s+", " ", t).strip()
    # bei 'A | B | C' den passendsten Teil nehmen
    parts = re.split(r"\s*[|\u2013\u2022]\s*", t)
    cand = [p.strip() for p in parts if PLAUSIBLE_PAT.search(p)]
    if cand:
        t = max(cand, key=len)
    t = STRIP_PAT.sub("", t)
    t = LEAD_PAT.sub("", t)
    for _ in range(3):
        t2 = SUFFIX_PAT.sub("", t).strip()
        if t2 == t:
            break
        t = t2
    t = t.strip(" -–|:")
    if not (4 <= len(t) <= 80) or not PLAUSIBLE_PAT.search(t):
        return None
    # rein generische Titel ('Camping', 'Camping & Caravan') sind kein Name;
    # Platz bleibt dann '(unbenannt)' – keine erfundenen Namen
    if t.lower() in GENERIC:
        return None
    return t[0].upper() + t[1:]


def run(region_name):
    conn = C.init_db()
    regs = REGIONS if region_name == "alle" else [region_name]
    for reg in regs:
        rows = conn.execute("""SELECT s.id, s.name, s.website, e.water_name,
            e.name_source FROM sites s
            JOIN enrichment e ON s.id=e.site_id WHERE s.region=?
            AND (s.name IS NULL OR s.name='' OR s.name='(unbenannt)'
                 OR (e.name_source IS NOT NULL AND (s.name IN
                     ('Camping', 'Camping & Caravan',
                      'auf dem Campingplatz am Krakower See')
                     OR e.name_source LIKE '%abgeleitet%')))
            AND s.website IS NOT NULL AND s.website != ''""", (reg,)).fetchall()
        n = 0
        for r in rows:
            name = None
            try:
                soup, text, final_url, quelle = page_text_robust(r["website"], "s20")
                og = soup.find("meta", property="og:site_name")
                cands = []
                if og and og.get("content"):
                    cands.append(og["content"])
                h1 = soup.find("h1")
                if h1:
                    cands.append(h1.get_text(" ", strip=True))
                if soup.title:
                    cands.append(soup.title.get_text(" ", strip=True))
                for c in cands:
                    name = clean_title(c)
                    if name:
                        break
            except Exception as ex:
                print("  %s: Website nicht ladbar (%s)" % (r["id"], str(ex)[:60]))
            # KEIN erfundener Name: wenn Website-Titel nichts Plausibles
            # hergibt, bleibt der Platz '(unbenannt)' (Nutzer-Entscheidung).
            if name:
                conn.execute("UPDATE sites SET name=? WHERE id=?", (name, r["id"]))
                conn.execute("UPDATE enrichment SET name_source=? WHERE site_id=?",
                             ("Website-Titel (%s)" % r["website"][:80], r["id"]))
                print("  %s -> %s" % (r["id"], name))
                n += 1
            else:
                # zuvor abgeleitete Pseudo-Namen zuruecknehmen
                if ((r["name_source"] and "abgeleitet" in r["name_source"])
                        or (r["name"] or "").lower() in GENERIC
                        or r["name"] == "AlpacaCamping"):
                    conn.execute("UPDATE sites SET name='(unbenannt)' WHERE id=?", (r["id"],))
                    conn.execute("UPDATE enrichment SET name_source=NULL WHERE site_id=?", (r["id"],))
                    print("  %s -> (unbenannt) [Pseudo-Name zurueckgenommen]" % r["id"])
                else:
                    print("  %s: kein plausibler Name im Titel -> (unbenannt)" % r["id"])
        conn.commit()
        print("%s: %d/%d Namen ergaenzt" % (reg, n, len(rows)))
    conn.close()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "alle")