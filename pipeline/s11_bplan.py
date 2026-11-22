"""Schritt 11: Bebauungspläne (B-Plan) je Platz – amtliche Bauleitplanung MV.

Quelle: WFS des Landkreises Mecklenburgische Seenplatte (bauleitplaene-mv.de),
deckungsgleich mit dem Geoportal LK MSE. Liefert:
  - Planname, Rechtsstand, Inkrafttreten
  - Links zu Plan-PDFs (Rechtsplan, Begründung, Anlagen)
  - OCR-Analyse des Rechtsplans: Sondergebiet-Typen (Camping/Ferienhaus...),
    max. Grundfläche je Gebäude, Firsthöhe, Dachneigung, GRZ
  -> daraus eine fundierte Bebaubarkeits-Einschätzung für ortsfeste Tinyhäuser.

Aufruf: python -m pipeline.s11_bplan seenplatte [--top=25] [--no-ocr]
"""
import io
import json
import re
import sys
from datetime import datetime, timezone

import requests

from . import common as C

WFS = "https://geoport-lk-mse.de/webservices/wfs/mp_b_plan_mv_mse"
FT = "bebauungsplaene_mse"


def fetch_plans(lat, lon, pad_km=1.2, source="mse"):
    """B-Pläne im Umkreis – Quelle je Bundesland (Regions-Config)."""
    if source == "bb_plis":
        return fetch_plans_bb(lat, lon, pad_km)
    if source == "sn_rapis":
        return fetch_plans_sn(lat, lon, pad_km)
    if source == "th_komm":
        return fetch_plans_th(lat, lon, pad_km)
    if source == "st_aris":
        return fetch_plans_st(lat, lon, pad_km)
    return fetch_plans_mse(lat, lon, pad_km)


def fetch_plans_mse(lat, lon, pad_km=1.2):
    """MV: WFS des LK Mecklenburgische Seenplatte (BBOX lat lon!)."""
    dlat = pad_km / 111.0
    dlon = pad_km / (111.0 * 0.6)  # ~53.3 deg Nord
    params = {
        "SERVICE": "WFS", "VERSION": "1.1.0", "REQUEST": "GetFeature",
        "TYPENAME": FT, "SRSNAME": "EPSG:4326", "MAXFEATURES": "50",
        "BBOX": "%f,%f,%f,%f,EPSG:4326" % (lat - dlat, lon - dlon, lat + dlat, lon + dlon),
    }
    key = "bplan_%s_%.4f_%.4f" % (FT, lat, lon)
    xml = C.http_get(WFS, params=params, cache_key=key, max_age_h=24 * 180,
                     polite=0.5, timeout=90)
    return parse_plans(xml)


BB_WFS = "https://plis-bb.de/plisproject/inspire/index.php/geoserver/wfs"
BB_FT = "bebauungsplaene_rechtswirksam_wfs:bp_rechtswirksam_flaechen"


def fetch_plans_bb(lat, lon, pad_km=1.2):
    """BB: GL Berlin-Brandenburg / PLIS (rechtswirksame B-Pläne, landesweit).
    WFS 2.0.0 (1.1.0 ignoriert den BBOX stillschweigend!), EPSG:25833.
    Liefert Planname, Gemeinde, Planart (z.B. 'Freizeit/ Tourismus'),
    Bekanntmachungsdatum, Flaeche + Geometrie. Keine PDFs -> Gemeinde."""
    from pyproj import Transformer
    import math
    T = Transformer.from_crs("EPSG:4326", "EPSG:25833", always_xy=True)
    x, y = T.transform(lon, lat)
    half = pad_km * 1000
    params = {
        "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
        "TYPENAMES": BB_FT, "SRSNAME": "EPSG:25833", "COUNT": "60",
        "BBOX": "%f,%f,%f,%f,urn:ogc:def:crs:EPSG::25833" % (
            x - half, y - half, x + half, y + half),
    }
    key = "bplan_bb_%.4f_%.4f" % (lat, lon)
    xml = C.http_get(BB_WFS, params=params, cache_key=key, max_age_h=24 * 180,
                     polite=0.5, timeout=120)
    from pyproj import Transformer as Tr
    T_INV = Tr.from_crs("EPSG:25833", "EPSG:4326", always_xy=True)
    plans = []
    # WFS 2.0 liefert <wfs:member>, 1.1 <gml:featureMember> – beides parsen
    for m in re.finditer(r"<(?:wfs:member|gml:featureMember)>(.*?)</(?:wfs:member|gml:featureMember)>", xml, re.S):
        frag = m.group(1)
        def attr(name):
            mm = re.search(r"<(?:\w+:)?%s[^>]*>([^<]*)</" % name, frag)
            return mm.group(1).strip() if mm else ""
        bek = attr("bp_dat_bek")  # "30.10.2008"
        iso = ""
        mm = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", bek)
        if mm:
            iso = "%s-%s-%s" % (mm.group(3), mm.group(2), mm.group(1))
        vart = attr("bp_t_vart")
        haupt = attr("bp_t_haupt")
        p = {
            "name": attr("bp_bez"),
            "nummer": attr("bp_id"),
            "rechtsstand": attr("bp_t_ent_g") or "Rechtswirksam",
            "planart": "%s / %s" % (vart, haupt) if vart else haupt,
            "inkrafttreten": iso,
            "gemeinde": attr("gemname"),
            "dokumente": [],
            "nutzung": vart,
            "flaeche_m2": attr("flaeche"),
        }
        rings = []
        for c in re.findall(r"<gml:posList[^>]*>([^<]+)</gml:posList>", frag):
            vals = [float(v) for v in c.split()]
            rings.append([list(T_INV.transform(vals[i], vals[i + 1]))
                          for i in range(0, len(vals) - 1, 2)])
        if rings:
            p["geometry"] = {"type": "Polygon", "coordinates": rings}
        plans.append(p)
    return plans


SN_ARCGIS = "https://rapis.ipm-gis.de/arcgis/rest/services/WMS_BPLAN/MapServer"


TH_WFS = "https://www.geoproxy.geoportal-th.de/geoproxy/services/kommunal/komm_wfs"

ST_ARIS = ("https://www.geodatenportal.sachsen-anhalt.de/arcgis/rest/services/"
           "ARIS/bauleitplanung_siedlungsentwicklung_extern/FeatureServer")


def fetch_plans_st(lat, lon, pad_km=1.2):
    """ST: ARIS Bauleitplanung (landesweit, ArcGIS FeatureServer).
    Layer 2 = B-Plan rechtskraeftig/genehmigt MIT Nutzungsart (generalisiert),
    Layer 6 = Geltungsbereich. BBOX in EPSG:25832 x,y. Keine PDFs im Dienst
    (kommunale Portale separat). RK_DAT = Epoch-ms."""
    from pyproj import Transformer
    T32 = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)
    x, y = T32.transform(lon, lat)
    half = pad_km * 1000
    env = "%f,%f,%f,%f" % (x - half, y - half, x + half, y + half)
    def query(layer, geom=True):
        params = {"f": "json", "geometry": env, "geometryType": "esriGeometryEnvelope",
                  "inSR": "25832", "outSR": "4326", "spatialRel": "esriSpatialRelIntersects",
                  "outFields": "*", "returnGeometry": "true" if geom else "false"}
        key = "bplan_st_%d_%.4f_%.4f" % (layer, lat, lon)
        raw = C.http_get(ST_ARIS + "/%d/query" % layer, params=params,
                         cache_key=key, max_age_h=24 * 180, polite=0.5, timeout=120)
        return json.loads(raw).get("features", [])
    def ms_to_date(v):
        try:
            from datetime import datetime, timezone
            return datetime.fromtimestamp(int(v) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            return ""
    STATUS = {"RK": "Rechtskräftig", "GN": "Genehmigt"}
    plans = []
    for f in query(2):
        a = f.get("attributes", {})
        nutzung = (a.get("NUTZUNGSAR") or "").strip()
        p = {
            "name": (a.get("BEZEICHNUN") or "").strip(),
            "nummer": str(a.get("IFCID") or a.get("OBJECTID") or ""),
            "rechtsstand": STATUS.get(a.get("STATUS"), a.get("STATUS") or ""),
            "planart": (a.get("TH_NAME") or "Bebauungsplan").strip(),
            "inkrafttreten": ms_to_date(a.get("RK_DAT") or a.get("GEN_DAT")),
            "gemeinde": (a.get("GEMEINDE") or "").strip(),
            "dokumente": [],
            "nutzung": nutzung,
            "flaeche_m2": round(float(a.get("FLAE_HA") or 0) * 10000, 1) or None,
        }
        rings = (f.get("geometry") or {}).get("rings")
        if rings:
            p["geometry"] = {"type": "Polygon", "coordinates": rings}
        plans.append(p)
    # Layer 6: Geltungsbereiche ohne Nutzungsart ergaenzen (falls Layer 2 leer)
    if not plans:
        for f in query(6):
            a = f.get("attributes", {})
            p = {
                "name": (a.get("BEZEICHNUN") or "").strip(),
                "nummer": str(a.get("IFCID") or a.get("OBJECTID") or ""),
                "rechtsstand": STATUS.get(a.get("STATUS"), a.get("STATUS") or ""),
                "planart": (a.get("TH_NAME") or "Bebauungsplan").strip(),
                "inkrafttreten": ms_to_date(a.get("RK_DAT") or a.get("GEN_DAT")),
                "gemeinde": (a.get("GEMEINDE") or "").strip(),
                "dokumente": [],
                "nutzung": "",
            }
            rings = (f.get("geometry") or {}).get("rings")
            if rings:
                p["geometry"] = {"type": "Polygon", "coordinates": rings}
            plans.append(p)
    return plans


def fetch_plans_th(lat, lon, pad_km=1.2):
    """TH: kommunaler WFS (kommunal:komm_bp = B-Pläne + Satzungen, landesweit
    eingespeist). NUR WFS 2.0.0; BBOX IMMER in EPSG:25832 x,y (Suffix wird
    ignoriert!), Ausgabe via SRSNAME=25833. Liefert Planname, Planart,
    Rechtsstand, Rechtskraft-Datum + Planunterlagen-PDF-Link."""
    from pyproj import Transformer
    T32 = Transformer.from_crs("EPSG:4326", "EPSG:25832", always_xy=True)
    T_INV = Transformer.from_crs("EPSG:25833", "EPSG:4326", always_xy=True)
    x, y = T32.transform(lon, lat)
    half = pad_km * 1000
    params = {
        "SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature",
        "TYPENAMES": "kommunal:komm_bp", "SRSNAME": "EPSG:25833", "COUNT": "80",
        "BBOX": "%f,%f,%f,%f,urn:ogc:def:crs:EPSG::25832" % (
            x - half, y - half, x + half, y + half),
    }
    key = "bplan_th_%.4f_%.4f" % (lat, lon)
    xml = C.http_get(TH_WFS, params=params, cache_key=key, max_age_h=24 * 180,
                     polite=0.5, timeout=120)
    plans = []
    for m in re.finditer(r"<(?:wfs:member|gml:featureMember)>(.*?)</(?:wfs:member|gml:featureMember)>", xml, re.S):
        frag = m.group(1)
        def attr(name):
            mm = re.search(r"<(?:\w+:)?%s[^>]*>([^<]*)</" % name, frag)
            return mm.group(1).strip() if mm else ""
        name = attr("Name")
        aend = attr("Planaenderung")
        if aend:
            name = "%s, %s" % (name, aend)
        p = {
            "name": name,
            "nummer": "",
            "rechtsstand": attr("Rechtsstand_Beschreibung") or "Inkraftgetreten",
            "planart": attr("Planart_Beschreibung"),
            "inkrafttreten": attr("Datum_Rechtskraft")[:10],
            "gemeinde": attr("Gemeinde"),
            "dokumente": [],
            "nutzung": "",
        }
        pdf = attr("Planunterlagen")
        if pdf.startswith("http"):
            p["dokumente"].append({"typ": "Rechtsplan (Planunterlagen)", "url": pdf})
        rings = []
        for c in re.findall(r"<gml:posList[^>]*>([^<]+)</gml:posList>", frag):
            vals = [float(v) for v in c.split()]
            rings.append([list(T_INV.transform(vals[i], vals[i + 1]))
                          for i in range(0, len(vals) - 1, 2)])
        if rings:
            p["geometry"] = {"type": "Polygon", "coordinates": rings}
        plans.append(p)
    return plans


def fetch_plans_sn(lat, lon, pad_km=1.2):
    """SN: RAPIS der Landesdirektion (alle Kommunen, landesweit).
    ArcGIS-REST-Query, Layer 3 = Geltungsbereich in Kraft, 2 = Nutzungsarten.
    Nutzungsarten liefern THEMA_DET (z.B. 'Sondergebiet Erholung, Freizeit')."""
    import math
    x = lon * 20037508.34 / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180) * 20037508.34 / 180
    half = pad_km * 1400  # grober 3857-Puffer (Breitengrad-abhaengig)
    env = json.dumps({"xmin": x - half, "ymin": y - half, "xmax": x + half,
                      "ymax": y + half, "spatialReference": {"wkid": 3857}})
    def query(layer):
        params = {"f": "json", "geometry": env, "geometryType": "esriGeometryEnvelope",
                  "inSR": "3857", "outSR": "4326", "spatialRel": "esriSpatialRelIntersects",
                  "outFields": "*", "returnGeometry": "true"}
        key = "bplan_sn_%d_%.4f_%.4f" % (layer, lat, lon)
        raw = C.http_get(SN_ARCGIS + "/%d/query" % layer, params=params,
                         cache_key=key, max_age_h=24 * 180, polite=0.5, timeout=120)
        return json.loads(raw).get("features", [])
    def ms_to_date(v):
        try:
            from datetime import datetime, timezone
            return datetime.fromtimestamp(int(v) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        except Exception:
            return ""
    plans = []
    for f in query(3):
        a = f.get("attributes", {})
        p = {
            "name": (a.get("NAME") or "").strip(),
            "nummer": a.get("ROK_NR") or "",
            "rechtsstand": (a.get("STATUS") or "").strip(),
            "planart": "",
            "inkrafttreten": ms_to_date(a.get("DAT_SATZ") or a.get("DAT_BEKANN")),
            "gemeinde": (a.get("GEMEINDE") or "").strip(),
            "dokumente": [],
        }
        rings = (f.get("geometry") or {}).get("rings")
        if rings:
            p["geometry"] = {"type": "Polygon", "coordinates": rings}
        plans.append(p)
    # Nutzungsarten (Layer 2): THEMA_DET je Plan -> Planart/Nutzung
    try:
        for f in query(2):
            a = f.get("attributes", {})
            name = (a.get("NAME") or "").strip()
            det = (a.get("THEMA_DET") or "").strip()
            for p in plans:
                if p["name"] == name and det:
                    p["planart"] = (p["planart"] + "; " + det).strip("; ")
                    if re.search(r"erholung|freizeit|camp|ferien|touris|sondergebiet",
                                 det, re.I):
                        p["nutzung"] = det
    except Exception:
        pass
    return plans


def parse_plans(xml):
    plans = []
    for m in re.finditer(r"<gml:featureMember>(.*?)</gml:featureMember>", xml, re.S):
        frag = m.group(1)
        def attr(name):
            mm = re.search(r"<(?:\w+:)?%s[^>]*>([^<]*)</" % name, frag)
            return mm.group(1).strip() if mm else ""
        p = {
            "name": attr("anzeigename"),
            "nummer": attr("nummer"),
            "rechtsstand": attr("rechtsstand_text"),
            "planart": attr("planart_text"),
            "inkrafttreten": attr("inkrafttretensdatum"),
            "gemeinde": attr("gemeinde_gemeindename"),
            "dokumente": [],
        }
        for i in range(1, 16):
            url = attr("externereferenz_url_%d" % i)
            desc = attr("dok_%d_beschreibung" % i)
            if url and url.startswith("http"):
                p["dokumente"].append({"typ": desc, "url": url})
        # Geometrie (MultiSurface, lat lon)
        coords = re.findall(r"<gml:posList[^>]*>([^<]+)</gml:posList>", frag)
        rings = []
        for c in coords:
            vals = [float(v) for v in c.split()]
            rings.append([[vals[i + 1], vals[i]] for i in range(0, len(vals) - 1, 2)])
        if rings:
            p["geometry"] = {"type": "Polygon", "coordinates": rings}
        plans.append(p)
    return plans


def pdf_text_cached(url, key):
    """PDF laden, Text extrahieren; gescannte Pläne per Tesseract-OCR."""
    ckey = "bplan_pdf_" + key
    txt_path = C.CACHE / (ckey + ".ocr.txt")
    if txt_path.exists():
        return txt_path.read_text(encoding="utf-8")
    data = C.http_get(url, binary=True, cache_key=ckey, max_age_h=24 * 365,
                      polite=1.0, timeout=180)
    if not data or data[:4] != b"%PDF":
        return ""
    text = ""
    try:
        from pypdf import PdfReader
        rd = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in rd.pages[:6])
    except Exception:
        pass
    if len(text.strip()) < 300:
        # Scan -> OCR (Tesseract, deutsch)
        try:
            import fitz
            import pytesseract
            from PIL import Image
            Image.MAX_IMAGE_PIXELS = 300_000_000  # grosse Planzeichnungen
            doc = fitz.open(stream=data, filetype="pdf")
            parts = []
            for page in doc[:3]:
                # dpi so waehlen, dass max. ~8000 px Kantenlaenge (Speicher)
                longest_pt = max(page.rect.width, page.rect.height)
                dpi = min(200, max(100, int(8000 * 72 / longest_pt)))
                pix = page.get_pixmap(dpi=dpi)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                parts.append(pytesseract.image_to_string(img, lang="deu"))
            text = "\n".join(parts)
        except Exception as e:
            text += "\n[OCR fehlgeschlagen: %s]" % str(e)[:80]
    txt_path.write_text(text, encoding="utf-8")
    return text


RE_QM = re.compile(r"(?:max\.?|maximal(?:e)?|bis(?:\s+zu)?)\s*(?:\w+\s+){0,3}?"
                   r"(?:Grundfl(?:ä|ae)che|Grundst(?:ü|ue)cksfl(?:ä|ae)che)[^\d]{0,40}"
                   r"(\d{2,4})\s*(?:qm|q m|m²|m2|m\?)", re.I)
RE_QM2 = re.compile(r"Grundfl(?:ä|ae)che\s+von\s+(?:max\.?\s*)?(\d{2,4})\s*(?:qm|m²|m2)", re.I)
RE_FIRST = re.compile(r"Firsth(?:ö|oe)he[^\d]{0,40}(\d{1,2}[.,]\d{1,2})\s*m", re.I)
RE_DACH = re.compile(r"Dachneigung[^\d]{0,30}(\d{1,2})\s*(?:°|Grad|bis)", re.I)
RE_GRZ = re.compile(r"GRZ[^\d]{0,20}(\d[.,]\d{1,2})", re.I)


def analyze_plan(text):
    """Baurechtliche Kennwerte aus dem (OCR-)Text des Rechtsplans."""
    a = {}
    low = text.lower()
    so = []
    for m in re.finditer(r"so\s*\d+(?:\s*[-–]\s*\d+)?\s*([^\n.;]{0,70})", low):
        so.append(m.group(0).strip()[:80])
    a["sondergebiete"] = so[:8]
    a["camping_erlaubt"] = bool(re.search(r"camping|stellpl(?:ä|ae)tze|zeltpl(?:ä|ae)tze", low))
    a["ferienhaus_gebiet"] = bool(re.search(r"ferienh(?:ä|ae)user|ferienhausgebiet", low))
    a["mobilheim_erlaubt"] = "mobilheim" in low
    a["dauerwohnen_verboten"] = bool(re.search(
        r"(?:dauerwohnen|ständiger wohnsitz|dauerhafter aufenthalt)[^\n]{0,80}(?:nicht|ausgeschlossen|unzul)", low))
    qms = [float(x) for x in RE_QM.findall(text)] + [float(x) for x in RE_QM2.findall(text)]
    qms = [q for q in qms if 15 <= q <= 500]
    a["max_grundflaeche_qm"] = sorted(set(qms)) or None
    fh = [float(x.replace(",", ".")) for x in RE_FIRST.findall(text)]
    a["firsthoehe_m"] = min(fh) if fh else None
    dn = [int(x) for x in RE_DACH.findall(text)]
    a["dachneigung_grad"] = sorted(set(dn)) or None
    grz = [float(x.replace(",", ".")) for x in RE_GRZ.findall(text)]
    a["grz"] = max(grz) if grz else None
    return a


def build_verdict(site, enr, plans, analysis):
    """Bebaubarkeits-Ampel aus B-Plan-Fakten (überschreibt Heuristik aus s06)."""
    if not plans:
        return None, None
    active = [p for p in plans if "kraft" in (p.get("rechtsstand") or "").lower()
              or "rechtsplan" in str(p.get("dokumente")).lower()]
    a = analysis or {}
    bits = []
    if a.get("camping_erlaubt"):
        bits.append("B-Plan: Camping zugelassen")
    if a.get("ferienhaus_gebiet"):
        bits.append("Sondergebiet Ferienhaus vorhanden")
    if a.get("max_grundflaeche_qm"):
        bits.append("max. Grundfläche %s qm" % "/".join(str(int(q)) for q in a["max_grundflaeche_qm"]))
    if a.get("firsthoehe_m"):
        bits.append("Firsthöhe max. %.2f m" % a["firsthoehe_m"])
    if a.get("dauerwohnen_verboten"):
        bits.append("Dauerwohnen ausgeschlossen (Ferienvermietung ok)")
    if not bits:
        return None, None
    verdict = "; ".join(bits)
    # Ampel
    if a.get("ferienhaus_gebiet") or a.get("mobilheim_erlaubt"):
        flag = "grün-gelb: B-Plan mit Ferienhaus-/Campinggebiet – Tinyhäuser prüfen (Details: %s)" % verdict
    elif a.get("camping_erlaubt"):
        flag = "gelb: B-Plan Camping – feste Tinyhäuser nur mit Änderung/ Befreiung (%s)" % verdict
    else:
        flag = "gelb: B-Plan vorhanden, Camping nicht erkennbar – Bauamt fragen"
    return flag, verdict


def build_verdict_meta(chosen):
    """Ampel aus Plan-Metadaten (BB/SN: keine PDFs im Portal, aber Planart).
    'Freizeit/ Tourismus' bzw. 'Sondergebiet Erholung' = starkes Signal."""
    for p in chosen:
        txt = "%s %s %s" % (p.get("name") or "", p.get("planart") or "",
                            p.get("nutzung") or "")
        if re.search(r"camping|zeltplatz", txt, re.I):
            return ("gelb: B-Plan '%s' (%s) – Camping ausgewiesen; feste Tinyhäuser "
                    "nur mit Änderung/Befreiung – Bauamt anfragen"
                    % (p["name"][:60], p.get("planart") or "Camping"), None)
        if re.search(r"freizeit|erholung|touris|ferien", txt, re.I):
            return ("grün-gelb: B-Plan '%s' – %s –Tinyhäuser gut möglich; "
                    "Festsetzungen bei Gemeinde/Bauamt erfragen (keine PDFs im Portal)"
                    % (p["name"][:60], (p.get("nutzung") or p.get("planart") or "Freizeit/Tourismus")[:60]), None)
    if chosen:
        return ("gelb: B-Plan '%s' (%s) vorhanden, Camping nicht erkennbar – Bauamt fragen"
                % (chosen[0]["name"][:60], chosen[0].get("planart") or "?"), None)
    return None, None


def run(region_name, top=None, do_ocr=True):
    from shapely.geometry import shape, Point
    region = C.load_region(region_name)
    source = region.get("bplan_source", "mse")
    portal_name = {"mse": "LK-MSE-Portal", "bb_plis": "GL/PLIS-Portal Brandenburg",
                   "sn_rapis": "RAPIS Sachsen", "th_komm": "GDI-Th Kommunal-WFS",
                   "st_aris": "ARIS Sachsen-Anhalt"}.get(source, source)
    conn = C.init_db()
    q = """SELECT s.id, s.name, s.lat, s.lon, s.geometry, e.build_flag FROM sites s
        JOIN enrichment e ON s.id=e.site_id WHERE s.region=?
        ORDER BY e.lead_score DESC NULLS LAST"""
    sites = conn.execute(q, (region_name,)).fetchall()
    if top:
        sites = sites[:top]
    print("Plätze:", len(sites), "| Quelle:", portal_name)
    conn.close()
    import threading
    from concurrent.futures import ThreadPoolExecutor
    counters = {"plan": 0, "ocr": 0, "done": 0}
    lock = threading.Lock()

    def work(site):
        sid = site["id"]
        try:
            plans = fetch_plans(site["lat"], site["lon"], source=source)
        except Exception as e:
            with lock:
                counters["done"] += 1
                print("  !", site["name"][:40], str(e)[:80], flush=True)
            return
        if not plans:
            # Kein B-Plan im Portal -> dokumentieren statt "unbekannt"
            info = {"plans": [], "analysis": {}, "kein_bplan": True}
            flag = ("gelb: kein B-Plan im %s (1,2-km-Umkreis) – "
                    "wahrscheinlich Außenbereich (§35 BauGB); Bauamt anfragen" % portal_name)
            pj = json.dumps(info, ensure_ascii=False)
            ts = datetime.now(timezone.utc).isoformat()
            def _write_np(c, sid=sid, pj=pj, ts=ts, flag=flag):
                c.execute("UPDATE enrichment SET bplan_info=?, build_flag=?, updated=? WHERE site_id=?",
                          (pj, flag, ts, sid))
            C.db_write(_write_np)
            with lock:
                counters["done"] += 1
                print("  %2d/%d %-40s kein B-Plan (Außenbereich?)" % (
                    counters["done"], len(sites), site["name"][:40]), flush=True)
            return
        # raeumlicher Filter: nur Plaene, die den Platz wirklich beruehren
        try:
            g_site = shape(json.loads(site["geometry"])) if site["geometry"] \
                else Point(site["lon"], site["lat"]).buffer(0.002)
            touching = []
            for p in plans:
                if p.get("geometry"):
                    try:
                        if shape(p["geometry"]).intersects(g_site.buffer(0.0015)):
                            touching.append(p)
                    except Exception:
                        touching.append(p)
                else:
                    touching.append(p)
            if touching:
                plans = touching
        except Exception:
            pass
        # relevanteste Pläne: Name/Nutzungsart enthält camping/ferien/erholung...
        REL_RE = r"camp|ferien|erholung|freizeit|see|ufer|hafen|bungalow|touris|zelt"
        def _relevant(p):
            return re.search(REL_RE, p["name"] + " " + (p.get("planart") or "")
                             + " " + (p.get("nutzung") or ""), re.I)
        rel = [p for p in plans if _relevant(p)]
        chosen = rel or plans
        # neuester Rechtsplan zuerst (konsolidierte Festsetzungen)
        def _jahr(p):
            d = p.get("inkrafttreten") or ""
            return d[:4] if d[:4].isdigit() else "0000"
        chosen = sorted(rel or chosen, key=_jahr, reverse=True)
        analysis = {}
        n_ocr = 0
        if do_ocr:
            for p in chosen[:3]:
                rp = next((d for d in p["dokumente"]
                           if "rechtsplan" in d["typ"].lower()), None)
                if not rp:
                    rp = next((d for d in p["dokumente"] if d["url"].endswith(".pdf")), None)
                if rp:
                    try:
                        key = re.sub(r"[^\w]", "_", rp["url"])[-60:]
                        text = pdf_text_cached(rp["url"], key)
                        if len(text) > 200:
                            a = analyze_plan(text)
                            for k, v in a.items():
                                if v and not analysis.get(k):
                                    analysis[k] = v
                            n_ocr += 1
                            break
                    except Exception as e:
                        print("  ! PDF", site["name"][:30], str(e)[:60])
        # Ampel: OCR-Fakten (MV) oder Planart/Nutzungsart (BB/SN, ohne PDFs)
        flag, verdict = build_verdict(site, None, plans, analysis)
        if not flag and source in ("bb_plis", "sn_rapis", "st_aris", "th_komm"):
            flag, verdict = build_verdict_meta(chosen)
        info = {"plans": [{k: p.get(k) for k in ("name", "nummer", "rechtsstand",
                                               "planart", "nutzung",
                                               "inkrafttreten", "gemeinde", "dokumente")}
                          for p in chosen[:6]],
                "analysis": analysis}
        pj = json.dumps(info, ensure_ascii=False)
        ts = datetime.now(timezone.utc).isoformat()
        def _write(c, sid=sid, pj=pj, ts=ts, flag=flag):
            if flag:
                c.execute("UPDATE enrichment SET bplan_info=?, build_flag=?, updated=? WHERE site_id=?",
                          (pj, flag, ts, sid))
            else:
                c.execute("UPDATE enrichment SET bplan_info=?, updated=? WHERE site_id=?",
                          (pj, ts, sid))
        C.db_write(_write)
        with lock:
            counters["plan"] += 1
            counters["ocr"] += n_ocr
            counters["done"] += 1
            print("  %2d/%d %-40s %d Pläne%s" % (counters["done"], len(sites),
                  site["name"][:40], len(plans), " +OCR" if analysis else ""), flush=True)

    workers = 4
    for a in sys.argv:
        if a.startswith("--workers"):
            workers = int(a.split("=")[1])
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            list(ex.map(work, sites))
    else:
        for s in sites:
            work(s)
    print("Fertig: mit B-Plan=%d, OCR-Analysen=%d" % (counters["plan"], counters["ocr"]), flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    region = args[0] if args else "seenplatte"
    top = None
    ocr = True
    for a in args[1:]:
        if a.startswith("--top="):
            top = int(a.split("=")[1])
        if a == "--no-ocr":
            ocr = False
    run(region, top=top, do_ocr=ocr)