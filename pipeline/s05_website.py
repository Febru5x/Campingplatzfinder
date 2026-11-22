"""Schritt 05: Website-Anreicherung.

- laedt Startseite + folgt Links zu Preisen/Unterkuenften/Kontakt/Impressum
- extrahiert: Preise, Mietunterkunft-Typen, Dauercamper-Hinweise,
  Tinyhaus/Hausboot-Erwaehnungen, Kontakt, Betreiber, Saison
- speichert Rohtext gecacht, Ergebnisse in enrichment

Aufruf:  python -m pipeline.s05_website seenplatte
"""
import json
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from . import common as C

LINK_WORDS = {
    "preise": ["preis", "preise", "preisliste", "tarif", "kosten", "gebuehr", "rates", "pricing"],
    "unterkunft": ["unterkuenft", "unterkünfte", "mietunterk", "bungalow", "mobilheim",
                   "mobile-home", "tiny", "hausboot", "ferienhaus", "huette", "hütte",
                   "glamping", "schlaffass", "pod", "accommodation", "mieten"],
    "dauer": ["dauer", "dauercamp", "standplatz", "jahresstellplatz", "saisonstellplatz"],
    "kontakt": ["kontakt", "contact", "impressum", "anfahrt", "ansprechpartner"],
}
# URL-Varianten mit Umlauten: 'unterkuenfte' vs 'unterkünfte'
def umlaut_variants(word):
    return [word, word.replace("ue", "ü").replace("ae", "ä").replace("oe", "ö")]


RE_PRICE = re.compile(r"(\d{1,3}(?:[.,]\d{1,2})?)\s*(?:€|EUR|Euro)", re.I)
RE_PRICE2 = re.compile(r"(?:€|EUR)\s*(\d{1,3}(?:[.,]\d{1,2})?)", re.I)

def norm_ascii(t):
    return (t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
             .replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue").replace("ß", "ss"))


RENTAL_TYPES = {
    "Mobilheim": r"mobilheim|mobile[\s-]?home|mobilhome",
    "Bungalow": r"bungalow",
    "Tinyhaus": r"tiny[\s-]?h(?:aus|äus|ouse)",
    "Hausboot": r"hausboot|houseboat|floating\s?home|schwimmend",
    "Ferienhaus": r"ferienhaus|ferienh(?:ä|ae)user|holiday\s?home",
    "Hütte": r"h(?:ü|ue)tte|cabin|blockhaus",
    "Schlaffass": r"schlaffass|campingfass|fass\b",
    "Glamping": r"glamping|safarizelt|lodge|pod\b",
    "Wohnwagen mietbar": r"(?:miet|leih)[\s-]?wohnwagen|caravan\s?(?:miet|rent)",
    "Zelt mietbar": r"(?:miet|leih)[\s-]?zelt|zelt\s?(?:miet|rent)|tipi",
}


def norm_url(u):
    if not u:
        return None
    u = u.strip()
    if u.startswith("mailto:") or u.startswith("tel:"):
        return None
    if not u.startswith("http"):
        u = "https://" + u
    return u


def page_text(url, cache_prefix):
    html = C.http_get(url, cache_key=None, max_age_h=24 * 14, polite=1.2,
                      retries=2, timeout=45)
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    text = soup.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return soup, text


BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
BROWSER_HDRS = {
    "User-Agent": BROWSER_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.6",
}


def _to_soup(html):
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    return soup, text


def wayback_text(url):
    """Letzter brauchbarer Wayback-Snapshot einer (toten/blockierten) Seite.
    oeffentliches Archiv, kein Bot-Schutz-Umgehen noetig."""
    try:
        raw = C.http_get("https://archive.org/wayback/available",
                         params={"url": url}, cache_key=None,
                         max_age_h=24 * 30, polite=1.0, retries=2, timeout=45)
        snap = json.loads(raw).get("archived_snapshots", {}).get("closest", {})
        if not snap.get("available"):
            return None
        wb_url = snap["url"].replace("http://", "https://")
        # 'id_'-Suffix = Original-HTML ohne Wayback-Rewriting/Banner
        wb_url = re.sub(r"/(\d{14})/", r"/\1id_/", wb_url, count=1)
        html = C.http_get(wb_url, cache_key=None, max_age_h=24 * 90,
                          polite=1.0, retries=2, timeout=60,
                          headers={"User-Agent": BROWSER_UA})
        soup, text = _to_soup(html)
        if len(text) < 200:
            return None
        return soup, text, snap.get("timestamp", "")[:8]
    except Exception:
        return None


def page_text_robust(url, cache_prefix, notes=None):
    """Aggressiver Seitenabruf mit Fallback-Kette:
    1) normal  2) Browser-UA + URL-Varianten (www/http/Slash)
    3) Wayback Machine (Original-HTML). Rueckgabe: soup, text, final_url, quelle."""
    try:
        soup, text = page_text(url, cache_prefix)
        return soup, text, url, None
    except Exception as ex:
        first_err = str(ex)[:80]
    # URL-Varianten mit Browser-Headers
    p = urlparse(url)
    variants = []
    host = p.netloc
    if host.startswith("www."):
        variants.append(url.replace("://www.", "://", 1))
    else:
        variants.append(url.replace("://", "://www.", 1))
    if url.startswith("https://"):
        variants.append("http://" + url[8:])
    if p.path in ("", "/"):
        for suffix in ("index.html", "index.php", "start.html", "home.html", "startseite.html"):
            variants.append(url.rstrip("/") + "/" + suffix)
    seen = {url}
    for v in variants:
        if v in seen:
            continue
        seen.add(v)
        try:
            html = C.http_get(v, cache_key=None, max_age_h=24 * 14, polite=0.8,
                              retries=1, timeout=30, headers=BROWSER_HDRS)
            soup, text = _to_soup(html)
            if len(text) > 150:
                if notes is not None:
                    notes.append("URL-Variante: " + v[:70])
                return soup, text, v, None
        except Exception:
            continue
    # Wayback-Fallback (auch bei duennem JS-only-Text der Originalseite)
    for wb_target in [url] + [v for v in variants if v not in (url,)][:2]:
        wb = wayback_text(wb_target)
        if wb:
            soup, text, ts = wb
            if notes is not None:
                notes.append("Wayback-Snapshot %s (Originalseite: %s)" % (ts, first_err[:50]))
            return soup, text, url, "wayback"
    raise RuntimeError(first_err)


def classify_links(soup, base):
    found = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].split("#")[0]
        if not href or href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        label = (a.get_text(" ", strip=True) + " " + href).lower()
        full = urljoin(base, href)
        if urlparse(full).netloc != urlparse(base).netloc:
            continue
        for cat, words in LINK_WORDS.items():
            variants = [v for w in words for v in umlaut_variants(w)]
            if cat not in found and any(w in label for w in variants):
                found[cat] = full
    # Fallback: nackte Domain -> /preise, /preise.html etc. probieren wir nicht
    # blind; aber Preis-PDFs werden separat gesammelt
    return found


def pdf_links(soup, base):
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"].split("#")[0]
        if href.lower().endswith(".pdf"):
            label = (a.get_text(" ", strip=True) + " " + href).lower()
            if any(w in label for w in ("preis", "tarif", "preisliste", "gebuehr", "kosten")):
                out.append(urljoin(base, href))
    return out[:2]


def extract_prices(text):
    prices = [float(m.replace(",", ".")) for m in RE_PRICE.findall(text)]
    prices += [float(m.replace(",", ".")) for m in RE_PRICE2.findall(text)]
    return [p for p in prices if 1 <= p <= 2000]


RE_BARE = re.compile(r"\b(\d{1,3},\d{2})\b")  # deutsche Preisnotation ohne €


def price_near(text, words, window=160):
    """Preise im Umfeld von Schluesselwoertern; Wochenpreise (/Woche, pro Woche,
    7 Naechte) werden ignoriert. Erkennt auch Tabellenpreise ohne €-Zeichen
    (deutsche Notation 51,20)."""
    out = []
    low = text.lower()
    week_pat = re.compile(r"woche|weekly|7\s*(?:n(?:a|ae)chte|uebernachtungen|tage)|pro\s+woche", re.I)
    for w in words:
        for m in re.finditer(w, low):
            seg = text[max(0, m.start() - 40): m.end() + window]
            if week_pat.search(seg):
                continue
            found = extract_prices(seg)
            if not found:
                # nackte deutsche Dezimalpreise (Tabellen)
                found = [float(x.replace(",", ".")) for x in RE_BARE.findall(seg)]
                found = [p for p in found if 3 <= p <= 500]
            out.extend(found)
    return out


def pick_price(vals, lo, hi):
    """Robuster Preis: nur plausible Werte, unteres Quartil (guenstigster
    Standardtarif statt Luxus-Suite)."""
    vals = sorted(v for v in vals if lo <= v <= hi)
    if not vals:
        return None
    return vals[len(vals) // 4]


def pdf_text(url):
    """Preis-PDF herunterladen und Text extrahieren."""
    try:
        data = C.http_get(url, binary=True, max_age_h=24 * 30, polite=1.0,
                          retries=2, timeout=60)
        if not data.startswith(b"%PDF"):
            return ""
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return " ".join((p.extract_text() or "") for p in reader.pages[:6])
    except Exception:
        return ""


def run(region_name, limit=None, workers=1, shard=0, shards=1, only_missing=False):
    conn = C.init_db()
    q = """SELECT s.* FROM sites s LEFT JOIN enrichment e ON s.id=e.site_id
        WHERE s.region=? AND s.website IS NOT NULL"""
    if only_missing:
        # noch nie versucht (updated NULL) oder letzter Versuch FEHLER
        q += " AND (e.updated IS NULL OR e.scrape_notes LIKE 'FEHLER%')"
    q += " ORDER BY s.id"
    sites = conn.execute(q, (region_name,)).fetchall()
    conn.close()
    if shards > 1:
        sites = sites[shard::shards]
    if limit:
        sites = sites[:limit]
    print("Plaetze mit Website:", len(sites), "| workers=%d shard=%d/%d" % (workers, shard, shards))
    import threading
    from concurrent.futures import ThreadPoolExecutor
    counter = {"ok": 0, "err": 0, "done": 0}
    lock = threading.Lock()

    def work(site):
        url = norm_url(site["website"])
        notes = []
        result = {}
        try:
            soup, text, url, quelle = page_text_robust(url, site["id"], notes)
            if quelle == "wayback":
                result["_wayback"] = True
            all_text = text
            links = classify_links(soup, url)
            sub_texts = {}
            for cat in ("preise", "unterkunft", "dauer", "kontakt"):
                if cat in links and links[cat] != url:
                    try:
                        if result.get("_wayback"):
                            # Wayback-Links aufs Original umbiegen, dann robust laden
                            orig = re.sub(r"https?://web\.archive\.org/web/\d+(?:id_)?/", "", links[cat])
                            s2, t2, _, q2 = page_text_robust(orig, site["id"] + cat, notes)
                        else:
                            s2, t2 = page_text(links[cat], site["id"] + cat)
                        sub_texts[cat] = t2
                        all_text += " " + t2
                        # zweite Ebene: 'preise'-Link auf der Preisseite (echte Tabelle)
                        if cat in ("preise", "unterkunft"):
                            l2 = classify_links(s2, links[cat])
                            for cat2 in ("preise", "unterkunft"):
                                u2 = l2.get(cat2)
                                if u2 and u2 not in (url, links[cat]) and cat2 not in sub_texts:
                                    try:
                                        _, t3 = page_text(u2, site["id"] + cat2 + "_2")
                                        sub_texts[cat2] = sub_texts.get(cat2, "") + " " + t3
                                        all_text += " " + t3
                                    except Exception:
                                        pass
                    except Exception as ex:
                        notes.append("%s: %s" % (cat, str(ex)[:80]))
            # Preis-PDFs, falls Preise fehlen
            pdf_urls = pdf_links(soup, url)
            if pdf_urls:
                for pu in pdf_urls:
                    pt = pdf_text(pu)
                    if pt:
                        all_text += " " + re.sub(r"\s+", " ", pt)
                        notes.append("Preis-PDF ausgewertet")
                        break
            #Ascii-normalisierte Kopie fuer Muster (Umlaute)
            all_text_n = norm_ascii(all_text)
            # Mietunterkunft-Typen
            types = []
            for label, pat in RENTAL_TYPES.items():
                if re.search(pat, all_text_n, re.I):
                    types.append(label)
            result["rentals"] = ", ".join(types) if types else None
            result["has_tinyhouse"] = int("Tinyhaus" in types)
            result["has_houseboat"] = int("Hausboot" in types)
            # Dauercamper
            seasonal = bool(re.search(r"dauercamp|dauerstellplatz|jahresstellplatz|saisonstellplatz|dauerplatz|standplatz\b|festplatz", all_text_n, re.I))
            result["seasonal"] = int(seasonal)
            # Preise (nur Text ab erster Preis-Erwaehnung, nicht Navigation)
            price_text = all_text_n
            pm = re.search(r"preis|tarif|kosten|gebuehr", all_text_n, re.I)
            if pm:
                price_text = all_text_n[pm.start():]
            pitch_prices = price_near(price_text, [r"stellplatz", r"standplatz", r"wohnmobil", r"wohnwagen", r"pitch"])
            tent_prices = price_near(price_text, [r"zeltplatz", r"\bzelt\b", r"\bzelte\b"])
            rental_prices = price_near(price_text, [r"bungalow", r"mobilheim", r"ferienhaus", r"tiny", r"huette", r"hausboot"])
            result["price_pitch"] = pick_price(pitch_prices, 10, 90)
            result["price_tent"] = pick_price(tent_prices, 3, 40)
            result["price_rental"] = pick_price(rental_prices, 40, 400)
            # Kontakt
            emails = set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", all_text))
            emails = {e for e in emails if not e.lower().endswith((".png", ".jpg", ".gif", ".webp"))}
            if not emails:
                for a in soup.find_all("a", href=True):
                    if a["href"].startswith("mailto:"):
                        emails.add(a["href"][7:].split("?")[0])
            result["contact_email"] = "; ".join(sorted(emails)[:3]) or None
            # Impressum-Betreiber (falls Kontaktseite geladen)
            kt = sub_texts.get("kontakt", "")
            m = re.search(r"(?:Inhaber|Betreiber|Geschäftsführer|Vertreten durch)[:\s]+([A-ZÄÖÜ][\wÄÖÜäöüß.\- ]{3,60})", kt or all_text)
            result["contact_name"] = m.group(1).strip() if m else None
            m2 = re.search(r"\b([A-ZÄÖÜ][\wÄÖÜäöüß&.\-]+(?: [A-ZÄÖÜ][\wÄÖÜäöüß&.\-]+){0,4} (?:GmbH(?: & Co\.? KG)?|GbR|e\.?\s?K\.?|e\.?\s?V\.?|KG|AG|UG))\b", kt or all_text)
            result["chain"] = m2.group(1).strip() if m2 else None
            # Saison (nur aus Kontaktseite oder Text um 'Saison:' mit Datum)
            kt = sub_texts.get("kontakt", "")
            m3 = re.search(r"(?:Saison|geöffnet|Öffnungszeiten)[:\s]+[^.!]{0,80}\d[^.!]{0,40}", kt or all_text, re.I)
            result["season"] = m3.group(0)[:100] if m3 else None
            # Anzahl Mietunterkuenfte ("12 Mobilheime", "8 Bungalows")
            counts = re.findall(r"(\d{1,3})\s*(?:moderne[nr]?|neue[nr]?|gem(?:ü|ue)tliche[nr]?|komfortable[nr]?)?\s*(mobilheime|bungalows|ferienh(?:ä|ae)user|tinyh(?:ä|ae)user|hausboote|h(?:ü|ue)tten|schlaff(?:ä|ae)sser)", all_text, re.I)
            if counts:
                result["rental_count"] = max(int(c) for c, _ in counts)
            result["scrape_notes"] = "; ".join(notes) or None
            result.pop("_wayback", None)  # internes Flag, keine DB-Spalte
            with lock:
                counter["ok"] += 1
        except Exception as ex:
            result["scrape_notes"] = "FEHLER: %s" % str(ex)[:200]
            with lock:
                counter["err"] += 1
        sets = ", ".join("%s=?" % k for k in result)
        vals = list(result.values())
        sid = site["id"]
        ts = datetime.now(timezone.utc).isoformat()
        def _write(c, sets=sets, vals=vals, ts=ts, sid=sid):
            c.execute("UPDATE enrichment SET %s, updated=? WHERE site_id=?" % sets,
                      vals + [ts, sid])
        C.db_write(_write)
        with lock:
            counter["done"] += 1
            if counter["done"] % 10 == 0:
                print("... %d/%d ok=%d err=%d" % (counter["done"], len(sites),
                      counter["ok"], counter["err"]), flush=True)

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, sites))
    else:
        for s in sites:
            work(s)
    print("Fertig: ok=%d err=%d" % (counter["ok"], counter["err"]), flush=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    limit = None
    workers, shard, shards = 1, 0, 1
    only_missing = False
    for a in sys.argv:
        if a.startswith("--limit"):
            limit = int(a.split("=")[1])
        elif a.startswith("--workers"):
            workers = int(a.split("=")[1])
        elif a.startswith("--shard"):
            shard, shards = (int(x) for x in a.split("=")[1].split("/"))
        elif a == "--only-missing":
            only_missing = True
    run(args[0] if args else "seenplatte", limit, workers, shard, shards, only_missing)
