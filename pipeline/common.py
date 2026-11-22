"""Gemeinsame Helfer: Konfiguration, Datenbank, HTTP-Cache, Geo-Mathe."""
import hashlib
import json
import math
import os
import sqlite3
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent


def _writable_dir(preferred, fallback):
    """Documents kann durch Windows-Ransomware-Schutz schreibgeschuetzt sein;
    dann weichen wir nach %LOCALAPPDATA% aus."""
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".write_probe"
        probe.write_text("ok")
        probe.unlink()
        return preferred
    except OSError:
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


_APPDATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Campingplatzfinder"
# Daten-Home: bestehende Daten in %LOCALAPPDATA% bevorzugen (Code kann aus
# einer Kopie laufen, z.B. %LOCALAPPDATA%\Campingplatzfinder\code)
DATA = _APPDATA / "data" if (_APPDATA / "data" / "camping.db").exists() \
    else _writable_dir(ROOT / "data", _APPDATA / "data")
OUTPUT = _APPDATA / "output" if (_APPDATA / "output").exists() \
    else _writable_dir(ROOT / "output", _APPDATA / "output")
CACHE = DATA / "cache"
DB_PATH = DATA / "camping.db"

for d in (CACHE,):
    d.mkdir(parents=True, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def load_region(name):
    # beschreibbare Kopie in %LOCALAPPDATA% hat Vorrang (Documents kann
    # durch Windows-Schutz/Sandbox gesperrt sein), sonst Projekt-config
    for base in (_APPDATA / "config", ROOT / "config"):
        p = base / "regions.json"
        if p.exists():
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            if name in data:
                return data[name]
    raise KeyError("Region %s nicht in regions.json" % name)


def db():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=60000")
    # Migration: neue Spalten fuer bestehende DBs (nur wenn Tabelle existiert)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(enrichment)")}
    if cols:
        for col in ("buildings", "bildsichtung"):
            if col not in cols:
                conn.execute("ALTER TABLE enrichment ADD COLUMN %s TEXT" % col)
        conn.commit()
    return conn


def db_write(fn, retries=8):
    """Schreibtransaktion mit Retry (parallele Pipeline-Schritte)."""
    for attempt in range(retries):
        conn = sqlite3.connect(DB_PATH, timeout=30)
        try:
            conn.execute("BEGIN IMMEDIATE")
            fn(conn)
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            conn.rollback()
            if "locked" in str(e) and attempt < retries - 1:
                time.sleep(3 * (attempt + 1))
                continue
            raise
        finally:
            conn.close()


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS sites (
        id TEXT PRIMARY KEY,
        osm_type TEXT, osm_id INTEGER,
        name TEXT, category TEXT,
        lat REAL, lon REAL,
        geometry TEXT,            -- GeoJSON Polygon/MultiPolygon oder null
        area_m2 REAL,
        website TEXT, phone TEXT, email TEXT,
        operator TEXT,
        stars INTEGER, capacity TEXT,
        raw_tags TEXT,
        region TEXT,
        source TEXT
    );
    CREATE TABLE IF NOT EXISTS enrichment (
        site_id TEXT PRIMARY KEY REFERENCES sites(id),
        -- Wasser
        water_distance_m REAL, water_name TEXT, water_type TEXT,
        shoreline_m REAL, has_pier INTEGER, marina_distance_m REAL,
        protected_area TEXT, motorboat_flag TEXT,
        water_score REAL,
        -- Grundstück
        parcels TEXT, parcel_area_m2 REAL, free_water_area_m2 REAL,
        bplan_info TEXT, build_flag TEXT,
        -- Bestand (Luftbild/Website)
        seasonal INTEGER, seasonal_share REAL,
        rentals TEXT, rental_count INTEGER, rental_age_est TEXT,
        has_tinyhouse INTEGER, has_houseboat INTEGER,
        buildings TEXT,             -- ALKIS-Gebaeude (BB/SN), JSON
        bildsichtung TEXT,          -- KI-Luftbild-Sichtung, JSON
        -- Website / Markt
        price_pitch REAL, price_tent REAL, price_rental REAL,
        season TEXT, chain TEXT, contact_name TEXT, contact_email TEXT,
        scrape_notes TEXT,
        -- Bewertung
        lead_score REAL, top_argument TEXT,
        revenue_example TEXT,
        updated TEXT
    );
    """)
    conn.commit()
    return conn


def http_get(url, params=None, binary=False, cache_key=None, max_age_h=72,
             timeout=60, retries=3, headers=None, polite=1.0):
    """GET mit Datei-Cache. cache_key=None -> aus URL+params abgeleitet."""
    if cache_key is None:
        raw = url + json.dumps(params or {}, sort_keys=True)
        cache_key = hashlib.sha1(raw.encode()).hexdigest()
    ext = ".bin" if binary else ".txt"
    cpath = CACHE / (cache_key + ext)
    mpath = CACHE / (cache_key + ".meta")
    if cpath.exists() and mpath.exists():
        meta = json.loads(mpath.read_text(encoding="utf-8"))
        if time.time() - meta["ts"] < max_age_h * 3600:
            return cpath.read_bytes() if binary else cpath.read_text(encoding="utf-8")
    hdrs = {"User-Agent": UA}
    if headers:
        hdrs.update(headers)
    last_err = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=hdrs, timeout=timeout)
            if r.status_code == 200:
                content = r.content if binary else r.text
                if binary:
                    cpath.write_bytes(r.content)
                else:
                    cpath.write_text(r.text, encoding="utf-8")
                mpath.write_text(json.dumps({"ts": time.time(), "url": r.url}),
                                 encoding="utf-8")
                time.sleep(polite)
                return content
            if r.status_code in (429, 502, 503, 504):
                wait = int(r.headers.get("Retry-After", 0)) or (10 * (attempt + 1))
                time.sleep(min(wait, 60))
                last_err = "HTTP %s" % r.status_code
                continue
            raise RuntimeError("HTTP %s for %s" % (r.status_code, r.url))
        except requests.RequestException as e:
            last_err = str(e)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("GET failed after retries: %s (%s)" % (url, last_err))


def http_post(url, data=None, timeout=120, headers=None):
    hdrs = {"User-Agent": UA}
    if headers:
        hdrs.update(headers)
    r = requests.post(url, data=data, headers=hdrs, timeout=timeout)
    r.raise_for_status()
    return r.text


def haversine(lat1, lon1, lat2, lon2):
    R = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# lokale metrische Projektion um einen Referenzpunkt (fuer Flaechen/Distanzen)
def make_projector(lat0, lon0):
    from pyproj import Transformer
    t = Transformer.from_crs(
        "EPSG:4326",
        "+proj=aeqd +lat_0=%f +lon_0=%f +units=m +datum=WGS84" % (lat0, lon0),
        always_xy=True)
    return lambda lon, lat: t.transform(lon, lat)
