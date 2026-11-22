"""Qualitaetsbericht: Datenabdeckung pro Feld und Region.

Aufruf:  python -m pipeline.s09_report seenplatte
"""
import sys

from . import common as C


def run(region_name):
    conn = C.db()
    total = conn.execute("SELECT COUNT(*) c FROM sites WHERE region=?",
                         (region_name,)).fetchone()["c"]
    print("Region: %s – %d Plaetze\n" % (region_name, total))
    checks = [
        ("Website", "s.website IS NOT NULL"),
        ("Geometrie (OSM)", "s.geometry IS NOT NULL"),
        ("Wasseranalyse", "e.water_distance_m IS NOT NULL"),
        ("direkt am Wasser <=50m", "e.water_distance_m<=50"),
        ("eigene Uferlaenge >30m", "e.shoreline_m>30"),
        ("Steg", "e.has_pier=1"),
        ("Flurstuecke", "e.parcels IS NOT NULL"),
        ("Website gescraped", "e.seasonal IS NOT NULL"),
        ("Mietunterkuenfte erkannt", "e.rentals IS NOT NULL AND e.rentals<>''"),
        ("Preis Stellplatz", "e.price_pitch IS NOT NULL"),
        ("Preis Unterkunft", "e.price_rental IS NOT NULL"),
        ("E-Mail", "e.contact_email IS NOT NULL OR s.email IS NOT NULL"),
        ("Dauercamper", "e.seasonal=1"),
        ("Tinyhaus vorh.", "e.has_tinyhouse=1"),
        ("Hausboot vorh.", "e.has_houseboat=1"),
        ("Score >= 50", "e.lead_score>=50"),
        ("Score >= 70", "e.lead_score>=70"),
    ]
    for label, cond in checks:
        n = conn.execute("SELECT COUNT(*) c FROM sites s JOIN enrichment e "
                         "ON s.id=e.site_id WHERE s.region=? AND (%s)" % cond,
                         (region_name,)).fetchone()["c"]
        print("  %-28s %4d  (%3.0f%%)" % (label, n, 100.0 * n / total))
    print("\nTop 10 nach Score:")
    for r in conn.execute("""SELECT s.name, e.lead_score, e.water_name,
        e.rentals, e.build_flag FROM sites s JOIN enrichment e ON s.id=e.site_id
        WHERE s.region=? ORDER BY e.lead_score DESC LIMIT 10""", (region_name,)):
        print("  %5.1f %-42s %-22s %s" % (r["lead_score"], r["name"][:42],
                                          (r["water_name"] or "")[:22],
                                          (r["rentals"] or "-")[:40]))
    conn.close()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "seenplatte")
