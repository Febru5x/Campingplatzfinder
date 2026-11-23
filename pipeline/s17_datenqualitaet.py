"""Schritt 17: Datenqualitaet / Lead-Klassifizierung.

Klassifiziert jeden Platz nach Eignung als Vermietungs-Partner und
bewertet die Hausboot-Eignung des Gewaessers. Schreibt neue Felder in
enrichment (site_class, class_reason, online_status, waterbody_class,
houseboat_water, default_hidden).

site_class:
  camping        echter Campingplatz (camp_site oder caravan_site mit
                 Camping-Struktur: Mietunterkuenfte/Dauercamper/Zelte)
  stellplatz     reiner Wohnmobilstellplatz (verifiziert: keine Zelte,
                 keine Mietunterkuenfte, keine Dauercamper) -> Default AUS
  verein         Sport-/Kanu-Verein etc. (Vereinsheim -> uninteressant)
  sonstiges      Parkplatz, Fahrerlager, Biwak/Rast, Gewerbeflaeche ...
  unbenannt      ohne Namen -> Default AUS

online_status: website (gescraped ok) / nur_verzeichnis (Tourismus-POI,
  kein eigener Auftritt) / keine -> 'keine' = Default AUS

houseboat_water: ja / nein / unklar  (See/Stausee >= ~5 ha bzw. benannter
  grosser See; Teich/Fluss/Bach/Kanal/Becken = nein)

Aufruf:  python -m pipeline.s17_datenqualitaet <region|alle>
"""
import json
import re
import sys
from datetime import datetime, timezone

from . import common as C

REGIONS = ["seenplatte", "brandenburg", "sachsen", "sachsen_anhalt", "thueringen"]

# Namensmuster fuer Nicht-Camping-Objekte (OSM-Fehltaggings)
SONSTIGES_PAT = re.compile(
    r"parkplatz|fahrerlager|biwak|rastplatz|wasserwander|kanurast|kanustation|"
    r"stellplatz f[üu]r|wohnmobilstellplatz|reisemobilhafen|reisemobil-stellplatz",
    re.I)
VEREIN_PAT = re.compile(
    r"\be\.?\s?V\.?\b|verein|kanu-?club|kanuclub|segelclub|seglerverein|"
    r"sportverein|paddelgemeinschaft|angelverein|fischereiverein|"
    r"sch[üu]tzenverein|freizeitgemeinschaft", re.I)
VERZEICHNIS_PAT = re.compile(
    r"tourismus|erzgebirge-tourismus|outdooractive|komoot|bergfex|"
    r"alpenvereinaktiv|camping\.info|pitchup|campercontact|park4night|"
    r"stellplatz\.info|promobil|adac|booking\.com|airbnb|facebook|"
    r"google\.[a-z.]+/maps|maps\.google|tripadvisor|holidaycheck|"
    r"campingplatz-verzeichnis|eurocampings|alanrogers|top-of-the-world",
    re.I)
# Gewaesser, die als Hausboot-Standort NICHT taugen ( unabhaengig vom Typ-Tag)
KLEIN_PAT = re.compile(
    r"teich|schwemme|pf[üu]tze|becken|graben|bach|flie[ßs]|kanal|graben", re.I)
GROSS_PAT = re.compile(
    r"see|stausee|talsperre|platte|fl[üu]ss?e?gro[ßs]|hafen|bucht|haff|bodden", re.I)


def classify(site, enr):
    """(site_class, reason, default_hidden)"""
    name = site["name"] or ""
    tags = json.loads(site["raw_tags"] or "{}")
    rentals = enr["rentals"] or ""
    has_camp_structure = bool(rentals) or bool(enr["seasonal"]) \
        or tags.get("tents") == "yes"
    low = name.lower()

    if not name or name == "(unbenannt)":
        # anonymer Platz: nur interessant, wenn Website UND Kontakt vorhanden
        if site["website"] and (site["email"] or enr["contact_email"] or site["phone"]):
            return "camping", "unbenannt, aber Website+Kontakt vorhanden", False
        return "unbenannt", "kein Name – Identitaet unklar", True
    if SONSTIGES_PAT.search(low):
        return "sonstiges", "Name deutet auf Parkplatz/Rast/Biwak/Stellplatz", True
    if VEREIN_PAT.search(low) or low.endswith(" e.v.") or "e.v." in low:
        # Verein: nur interessant ohne Vereinsheim -> ALKIS-Gebaeude pruefen
        # (Freizeitgebäude = Bungalows zaehlen NICHT als Vereinsheim;
        #  Wohn-/Wirtschafts-/oeffentliche Gebaeude schon)
        gb = None
        try:
            gb = json.loads(enr["buildings"] or "null")
        except Exception:
            pass
        heim = False
        if gb:
            for typ, n in gb.get("typen", {}).items():
                if any(w in typ for w in ("Wohn", "Wirtschaft", "Gewerbe",
                                          "öffentliche", "oeffentliche", "Handel",
                                          "kulturelle")):
                    heim = True
        if heim:
            return "verein", "Verein mit Vereinsheim-Gebaeuden (ALKIS)", True
        return "verein", "Verein ohne erfasstes Vereinsheim – Einzelfall pruefen", False
    if site["category"] == "caravan_site" and not has_camp_structure:
        return "stellplatz", "reiner Wohnmobilstellplatz (keine Zelte/Mietunterkuenfte/Dauer)", True
    if site["category"] == "caravan_site" and has_camp_structure:
        return "camping", "caravan_site, aber Camping-Struktur vorhanden", False
    return "camping", "Campingplatz", False


def online_status(site, enr):
    web = site["website"] or ""
    if not web:
        return "keine"
    if VERZEICHNIS_PAT.search(web):
        # Tourismus-POI/Verzeichnis zaehlt nicht als eigene Online-Praesenz
        notes = enr["scrape_notes"] or ""
        if "FEHLER" in notes:
            return "keine"
        return "nur_verzeichnis"
    notes = enr["scrape_notes"] or ""
    if "FEHLER" in notes and not enr["price_pitch"] and not enr["rentals"]:
        return "keine"   # Seite tot, nichts gerettet
    return "website"


def waterbody(enr):
    """(waterbody_class, houseboat_water)"""
    wt = (enr["water_type"] or "").lower()
    wn = enr["water_name"] or ""
    dist = enr["water_distance_m"]
    if wt in ("", "none") or (dist is not None and dist > 300):
        return "kein/fern", "nein"
    if wt in ("stream", "ditch", "wastewater", "drain"):
        return "bach/graben", "nein"
    if wt in ("river", "canal"):
        return "fluss/kanal", "nein"
    if wt in ("pond", "fishpond", "basin") or KLEIN_PAT.search(wn):
        return "teich/becken", "nein"
    if wt in ("lake", "reservoir", "oxbow", "harbour") or GROSS_PAT.search(wn):
        # benannte Seen/Stauseen: Grundannahme >= 5 ha; kleine Ausnahmen
        # koennen per Sichtung korrigiert werden
        return "see/stausee", "ja"
    if wt == "water":
        # OSM water= ohne Untertyp: Name entscheidet
        if KLEIN_PAT.search(wn):
            return "teich/becken", "nein"
        if GROSS_PAT.search(wn):
            return "see/stausee (Name)", "unklar"
        return "untypisiert", "unklar"
    return "sonstiges", "unklar"


# Manuelle Korrekturen aus KI-Bildsichtungen (DOP): Gewaesser-Groesse,
# die aus OSM-Tags nicht hervorgeht. Keys = site_id.
WATER_OVERRIDE = {
    # Kelbra: Hochwasserschutzbecken, extrem schwankender Wasserstand
    # (Sichtung 2026-11-22: breite Schlickflaechen) -> kein Hausboot
    "way/304488517": ("see/stausee", "nein"),
    "way/136762524": ("see/stausee", "nein"),
    # Thueries: Kiessee mit Strand+Steg, laut DOP mehrere ha -> Hausboot
    # grundsaetzlich moeglich (Rechte beim Kieswerk klaeren)
    "way/970453694": ("see/stausee (Kiessee)", "ja"),
    # Erfurt am See: zwei grosse Baggerseen (DOP), kein Teich
    "way/52333980": ("see/stausee (Baggersee)", "ja"),
}


def run(region_name):
    regions = REGIONS if region_name in ("alle", "all") else [region_name]
    conn = C.init_db()
    for reg in regions:
        sites = conn.execute("""SELECT s.*, e.* FROM sites s
            JOIN enrichment e ON s.id=e.site_id WHERE s.region=?""", (reg,)).fetchall()
        counts = {}
        for site in sites:
            cls, reason, hidden = classify(site, site)
            online = online_status(site, site)
            if online == "keine" and cls == "camping":
                hidden = True
                reason += "; keine Online-Praesenz"
            elif online == "nur_verzeichnis" and cls == "camping":
                reason += "; nur Verzeichnis-Link"
            wb, hb = waterbody(site)
            if site["id"] in WATER_OVERRIDE:
                wb, hb = WATER_OVERRIDE[site["id"]]
            conn.execute("""UPDATE enrichment SET site_class=?, class_reason=?,
                online_status=?, waterbody_class=?, houseboat_water=?,
                default_hidden=? WHERE site_id=?""",
                (cls, reason, online, wb, hb, int(bool(hidden)), site["id"]))
            counts[cls] = counts.get(cls, 0) + 1
        conn.commit()
        n_hidden = conn.execute("""SELECT COUNT(*) c FROM sites s JOIN enrichment e
            ON s.id=e.site_id WHERE s.region=? AND e.default_hidden=1""", (reg,)).fetchone()["c"]
        n_hidden0 = conn.execute("""SELECT COUNT(*) c FROM sites s JOIN enrichment e
            ON s.id=e.site_id WHERE s.region=? AND (e.default_hidden=0 OR e.default_hidden IS NULL)""",
            (reg,)).fetchone()["c"]
        print("%s: %d Plaetze | %s | Default ausgeblendet: %d | sichtbar: %d"
              % (reg, len(sites), counts, n_hidden, n_hidden0))
    conn.close()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "alle")
