"""Schritt 10: Wettbewerber-Radar – wer vermietet schon Tinyhäuser/Hausboote?

Listet alle Plätze der Region mit Tinyhaus/Hausboot-Angebot inkl. Preisen
als Marktvalidierung und Benchmark.

Aufruf:  python -m pipeline.s10_wettbewerb seenplatte
"""
import sys

from . import common as C


def run(region_name):
    conn = C.db()
    rows = conn.execute("""SELECT s.name, s.website, e.rentals, e.price_rental,
        e.water_name, e.lead_score FROM sites s JOIN enrichment e ON s.id=e.site_id
        WHERE s.region=? AND (e.has_tinyhouse=1 OR e.has_houseboat=1
              OR e.rentals LIKE '%Glamping%')
        ORDER BY e.lead_score DESC""", (region_name,)).fetchall()
    print("Wettbewerber / Marktvalidierung (%d):" % len(rows))
    for r in rows:
        print("  %-40s %-30s %s" % (r["name"][:40], (r["rentals"] or "")[:30],
                                    r["website"] or ""))
        if r["price_rental"]:
            print("      Preis Unterkunft: %.0f EUR" % r["price_rental"])
    conn.close()


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "seenplatte")
