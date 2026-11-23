"""Ein-Kommando-Runner: alle Schritte fuer eine Region.

Aufruf:  python -m pipeline.run_all seenplatte [--skip=3,5]
"""
import sys
import time

from . import (s01_grundliste, s02_wasser, s03_grundstueck, s04_luftbild,
               s05_website, s06_bewertung, s07_export, s08_dossiers,
               s11_bplan, s12_bestandsalter, s13_marktpreise, s14_gebaeude,
               s17_datenqualitaet, s18_gewaesserflaeche, s19_website_modern,
               s20_namen)

STEPS = [
    ("1", "Grundliste (OSM)", s01_grundliste.run),
    ("2", "Wasserlage", s02_wasser.run),
    ("3", "Flurstuecke (ALKIS)", lambda r: s03_grundstueck.run(r, workers=4)),
    ("4", "Luftbilder (DOP20)", lambda r: s04_luftbild.run(r, workers=4)),
    ("5", "Websites", lambda r: s05_website.run(r, workers=6)),
    ("6", "Bewertung", s06_bewertung.run),
    ("11", "Bebauungsplaene (Top-30)", lambda r: s11_bplan.run(r, top=30)),
    ("12", "Bestandsalter (Top-30)", lambda r: s12_bestandsalter.run(r, top=30)),
    ("14", "Gebaeude ALKIS (Top-40, nur BB/SN)", lambda r: s14_gebaeude.run(r, top=40)),
    ("13", "Marktpreise/Benchmarks", s13_marktpreise.run),
    ("6b", "Bewertung (final)", s06_bewertung.run),
    ("18", "Gewaesserflaechen", s18_gewaesserflaeche.run),
    ("20", "Namen aus Websites (unbenannte)", s20_namen.run),
    ("17", "Datenqualitaet/Klassifizierung", s17_datenqualitaet.run),
    ("19", "Website-Modernitaet", s19_website_modern.run),
    ("6c", "Bewertung (Modernitaet+lokale Preise)", s06_bewertung.run),
    ("7", "Export Excel+Karte", s07_export.run),
    ("8", "Top-Dossiers", s08_dossiers.run),
]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    region = args[0] if args else "seenplatte"
    skip = set()
    for a in sys.argv:
        if a.startswith("--skip"):
            skip = set(a.split("=")[1].split(","))
        elif a.startswith("--only"):
            only = set(a.split("=")[1].split(","))
            skip = {num for num, _, _ in STEPS} - only
    for num, label, fn in STEPS:
        if num in skip:
            print("== Schritt %s (%s) uebersprungen ==" % (num, label))
            continue
        print("\n== Schritt %s: %s ==" % (num, label))
        t = time.time()
        fn(region)
        print("   (%.1f min)" % ((time.time() - t) / 60))


if __name__ == "__main__":
    main()
