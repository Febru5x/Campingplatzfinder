"""Bereinigt Saison-Feld: Navigationstext-Müll raus, nur echte Saisonangaben.

Aufruf: python -m pipeline.fix_season seenplatte
"""
import re
import sys

from . import common as C


def run(region_name):
    conn = C.init_db()
    rows = conn.execute("""SELECT e.site_id, e.season FROM enrichment e
        JOIN sites s ON s.id=e.site_id WHERE s.region=? AND e.season IS NOT NULL""",
        (region_name,)).fetchall()
    n_clean = 0
    for r in rows:
        s = r["season"]
        # echtes Datum oder Monatsname enthalten?
        ok = re.search(r"\d{1,2}\.\s*\d{1,2}\.|\d{1,2}\.\s*(?:März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|Januar|Februar)|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|Januar|Februar|ganzjährig|durchgehend", s, re.I)
        if not ok:
            sid = r["site_id"]
            def _write(c):
                c.execute("UPDATE enrichment SET season=NULL WHERE site_id=?", (sid,))
            C.db_write(_write)
            n_clean += 1
    print("Bereinigt:", n_clean)
    conn.close()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "seenplatte")
